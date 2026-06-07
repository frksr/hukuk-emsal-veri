"""UYAP dosyalarımı yönet — upload, list, get, delete, AI sorgu."""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from api.audit import audit
from api.auth import CurrentUser, require_uyap
from api.db import db_session
from api.rate_limit import rate_limit_for
from api.schemas import APIResponse

log = logging.getLogger("api.uyap")
router = APIRouter()

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXT = {"pdf", "docx", "txt", "md"}


@router.post("/upload", response_model=APIResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    folder_id: str | None = Form(None),
    title: str | None = Form(None),
    tags: str | None = Form(None),  # JSON string
    user: CurrentUser = Depends(require_uyap),
):
    """UYAP belgesi yükle. Şifrelenir, parse edilir, vector store'a eklenir."""
    from services.uyap_parser import parse_file, extract_metadata, guess_document_type
    from services.tenant_storage import store as storage_store
    from services.tenant_rag import index_document
    from services.pii_redaction import audit_pii

    if not user.tenant_id:
        raise HTTPException(400, "Tenant gerekli.")

    # Dosya boyut kontrol
    filename = file.filename or "dosya"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Desteklenmeyen format. İzinli: {ALLOWED_EXT}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"Dosya {MAX_FILE_SIZE // (1024*1024)} MB'dan büyük.")
    if len(content) < 100:
        raise HTTPException(400, "Dosya çok küçük veya boş.")

    # Kota kontrolü
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        usage = await conn.fetchrow(
            """SELECT COUNT(*) c, t.max_uyap_documents
               FROM tenant_documents td
               RIGHT JOIN tenants t ON t.id = td.tenant_id
               WHERE t.id = $1
               GROUP BY t.max_uyap_documents""",
            user.tenant_id,
        )
        current = usage["c"] if usage else 0
        max_docs = (usage["max_uyap_documents"] if usage else 0) or 0
        if max_docs > 0 and current >= max_docs:
            raise HTTPException(
                402,
                f"UYAP dosya kotanız doldu ({current}/{max_docs}). Planı yükseltin.",
            )

    # Parse
    try:
        text = parse_file(content, ext)
    except Exception as e:
        raise HTTPException(400, f"Dosya okunamadı: {e}")

    if not text or len(text) < 50:
        raise HTTPException(400, "Dosyadan yeterli metin çıkarılamadı.")

    metadata = extract_metadata(text)
    doc_type = guess_document_type(text, filename)
    pii_info = audit_pii(text)

    document_id = str(uuid.uuid4())

    # Şifreli sakla
    try:
        storage = await storage_store(user.tenant_id, document_id, content)
    except Exception as e:
        log.exception("Storage hatası")
        raise HTTPException(500, f"Dosya saklanamadı: {e}")

    # DB kaydı
    parsed_tags = []
    if tags:
        try:
            parsed_tags = json.loads(tags)
        except Exception:
            parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        await conn.execute(
            """INSERT INTO tenant_documents
               (id, tenant_id, uploaded_by, title, case_no, decision_no, court,
                document_type, file_name, file_size, file_mime, storage_key,
                cleaned_text, status, encryption_iv, encrypted, folder_id,
                tags, pii_audit, document_date)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                       'processing', $14, TRUE,
                       $15::uuid, $16::jsonb, $17::jsonb, $18::date)""",
            document_id, user.tenant_id, user.user_id,
            title or filename, metadata.get("case_no"), metadata.get("decision_no"),
            metadata.get("court"), doc_type, filename,
            storage["file_size"], file.content_type or "application/octet-stream",
            storage["storage_key"], text,
            storage["encryption_iv"],
            folder_id,
            json.dumps(parsed_tags),
            json.dumps(pii_info),
            metadata.get("decision_date"),
        )

    # Vector store'a ekle (PII redact ETMİYORUZ — bu kullanıcının kendi verisi,
    # local Chroma'da kalıyor, LLM'e gönderirken redact ederiz)
    try:
        chunk_count = index_document(
            user.tenant_id, document_id, text,
            metadata={
                "title": title or filename,
                "doc_type": doc_type,
                "case_no": metadata.get("case_no") or "",
                "court": metadata.get("court") or "",
            },
        )
        async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
            await conn.execute(
                """UPDATE tenant_documents
                   SET status = 'ready', chunk_count = $1, updated_at = NOW()
                   WHERE id = $2""",
                chunk_count, document_id,
            )
    except Exception as e:
        log.exception("Indexing hatası")
        async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
            await conn.execute(
                """UPDATE tenant_documents
                   SET status = 'error', error_message = $1, updated_at = NOW()
                   WHERE id = $2""",
                str(e)[:500], document_id,
            )

    await audit(
        action="document.uploaded",
        user_id=user.user_id, tenant_id=user.tenant_id,
        resource=f"document:{document_id}",
        request=request,
        metadata={
            "filename": filename, "size": len(content),
            "doc_type": doc_type, "pii_detected": pii_info["contains_pii"],
        },
    )

    return APIResponse(ok=True, data={
        "id": document_id,
        "title": title or filename,
        "filename": filename,
        "size": len(content),
        "doc_type": doc_type,
        "metadata": metadata,
        "pii_audit": pii_info,
        "status": "ready",
    })


@router.get("/", response_model=APIResponse)
async def list_documents(
    user: CurrentUser = Depends(require_uyap),
    folder_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    if not user.tenant_id:
        return APIResponse(ok=True, data={"documents": [], "total": 0})

    where = "WHERE tenant_id = $1"
    args: list = [user.tenant_id]
    if folder_id:
        where += " AND folder_id = $2::uuid"
        args.append(folder_id)
    args.extend([limit, offset])
    limit_clause = f"LIMIT ${len(args) - 1} OFFSET ${len(args)}"

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            f"""SELECT id, title, case_no, decision_no, court, document_type,
                       file_name, file_size, status, chunk_count, tags,
                       document_date, created_at, updated_at
                FROM tenant_documents {where}
                ORDER BY created_at DESC {limit_clause}""",
            *args,
        )
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM tenant_documents {where.replace(' LIMIT ', ' ')}",
            *args[:-2],
        ) if folder_id else await conn.fetchval(
            "SELECT COUNT(*) FROM tenant_documents WHERE tenant_id = $1",
            user.tenant_id,
        )

    return APIResponse(ok=True, data={
        "documents": [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "case_no": r["case_no"],
                "decision_no": r["decision_no"],
                "court": r["court"],
                "doc_type": r["document_type"],
                "file_name": r["file_name"],
                "file_size": r["file_size"],
                "status": r["status"],
                "chunk_count": r["chunk_count"],
                "tags": r["tags"],
                "document_date": r["document_date"].isoformat() if r["document_date"] else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "total": int(total or 0),
    })


@router.get("/{doc_id}", response_model=APIResponse)
async def get_document(
    doc_id: str,
    user: CurrentUser = Depends(require_uyap),
):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        r = await conn.fetchrow(
            """SELECT * FROM tenant_documents
               WHERE id = $1::uuid AND tenant_id = $2""",
            doc_id, user.tenant_id,
        )
    if not r:
        raise HTTPException(404, "Doküman bulunamadı.")

    return APIResponse(ok=True, data={
        "id": str(r["id"]),
        "title": r["title"],
        "case_no": r["case_no"],
        "decision_no": r["decision_no"],
        "court": r["court"],
        "doc_type": r["document_type"],
        "file_name": r["file_name"],
        "file_size": r["file_size"],
        "status": r["status"],
        "chunk_count": r["chunk_count"],
        "tags": r["tags"],
        "topic_tags": r["topic_tags"],
        "pii_audit": r["pii_audit"],
        "summary": r["summary"],
        "cleaned_text": r["cleaned_text"],
        "document_date": r["document_date"].isoformat() if r["document_date"] else None,
        "created_at": r["created_at"].isoformat(),
    })


@router.delete("/{doc_id}", response_model=APIResponse)
async def delete_document_endpoint(
    doc_id: str,
    request: Request,
    user: CurrentUser = Depends(require_uyap),
):
    from services.tenant_storage import delete as storage_delete
    from services.tenant_rag import delete_document as rag_delete

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        r = await conn.fetchrow(
            "SELECT id FROM tenant_documents WHERE id = $1::uuid AND tenant_id = $2",
            doc_id, user.tenant_id,
        )
        if not r:
            raise HTTPException(404, "Doküman bulunamadı.")

        async with conn.transaction():
            await conn.execute(
                "DELETE FROM tenant_documents WHERE id = $1::uuid",
                doc_id,
            )

    # Storage + vector store sil
    try:
        storage_delete(user.tenant_id, doc_id)
    except Exception as e:
        log.warning(f"Storage silme hatası: {e}")
    try:
        rag_delete(user.tenant_id, doc_id)
    except Exception as e:
        log.warning(f"RAG silme hatası: {e}")

    await audit(
        action="document.deleted",
        user_id=user.user_id, tenant_id=user.tenant_id,
        resource=f"document:{doc_id}", request=request,
    )
    return APIResponse(ok=True, message="Doküman silindi.")


# ---- AI Sorgu ----

from pydantic import BaseModel

class SorguReq(BaseModel):
    query: str
    document_ids: list[str] | None = None  # None ise tüm dosyalarda
    k: int = 5
    include_emsal: bool = True  # public emsallerden de getir


@router.post("/sorgu", response_model=APIResponse, dependencies=[Depends(rate_limit_for("sorgu"))])
async def ai_sorgu(
    payload: SorguReq,
    request: Request,
    user: CurrentUser = Depends(require_uyap),
):
    """Kendi dosyalarımda + opsiyonel emsallerde AI sorgu.

    Akış:
    1. Tenant'ın dosyalarında RAG arama
    2. (Opsiyonel) Public emsal RAG'inde de arama
    3. Tüm context'i PII redact et
    4. LLM ile yanıt üret
    5. Yanıttan placeholder'ları geri koy
    """
    from services.tenant_rag import search_tenant
    from services.rag import search as public_search
    from services.pii_redaction import redact, unredact, audit_pii, ner_available, name_layer
    from llm.provider import generate, is_available
    import os
    import time

    # KVKK m.9: NER (isim/adres) katmanı kapalıyken context yurt dışı LLM'e
    # kişisel ad/adres içerebilir. PII_BLOCK_FOREIGN_LLM_WITHOUT_NER=1 ise bu
    # durumda LLM çağrısı YAPILMAZ (yalnızca kaynaklar döner).
    _block_without_ner = os.environ.get("PII_BLOCK_FOREIGN_LLM_WITHOUT_NER") == "1"

    start = time.perf_counter()

    # 1) Tenant dosyalarında arama
    tenant_results = search_tenant(
        user.tenant_id, payload.query, k=payload.k,
        document_ids=payload.document_ids,
    )

    # 2) Public emsal (opsiyonel)
    emsal_results = []
    if payload.include_emsal:
        try:
            emsal_results = public_search(payload.query, k=3)
        except Exception:
            pass

    if not tenant_results and not emsal_results:
        return APIResponse(ok=True, data={
            "answer": "Bu sorguya uygun bilgi dosyalarınızda veya emsal kararlarda bulunamadı.",
            "tenant_sources": [],
            "emsal_sources": [],
        })

    # 3) Context oluştur (PII redact'li)
    context_blocks = []
    for i, r in enumerate(tenant_results, 1):
        m = r.get("meta", {})
        context_blocks.append(
            f"[KENDI DOSYAM_{i}] {m.get('title', '?')} ({m.get('doc_type', '?')})\n"
            f"{r.get('text', '')[:1500]}"
        )
    for i, r in enumerate(emsal_results, 1):
        m = r.get("meta", {})
        context_blocks.append(
            f"[EMSAL_{i}] {m.get('court_chamber', '?')} - "
            f"E.{m.get('case_no', '?')}/K.{m.get('decision_no', '?')}\n"
            f"{r.get('text', '')[:1000]}"
        )
    full_context = "\n\n---\n\n".join(context_blocks)

    # PII koruması — context'i redact et
    redacted_context, redaction_map = redact(full_context)
    redacted_query, query_map = redact(payload.query)
    # Map'leri birleştir
    for ph, orig in query_map.forward.items():
        redaction_map.forward[ph] = orig

    # İsim/adres maskeleme şeffaflığı (KVKK)
    names_redacted = redaction_map.names_redacted
    active_layer = name_layer()  # "ner" | "heuristic"
    pii_warning = None
    if active_layer == "heuristic":
        pii_warning = (
            "İsim/adres maskeleme kural tabanlı (heuristik) katmanla yapıldı; en "
            "geniş kapsam için NER modeli (PII_NER_MODEL) önerilir. Bazı kişi "
            "adları/adresler maskelenmemiş olabilir."
        )

    # 4) LLM çağrısı
    answer = ""
    llm_provider_used = "none"
    tokens_used = 0
    # Strict KVKK modu: güçlü NER katmanı yoksa yurt dışı LLM çağrısını engelle.
    if _block_without_ner and not ner_available() and is_available():
        log.warning("KVKK strict: NER yok, yurt dışı LLM çağrısı engellendi (tenant=%s).", user.tenant_id)
        answer = (
            "KVKK koruması (strict mod): güçlü isim/adres maskeleme (NER) katmanı "
            "etkin olmadığından AI yanıtı üretilmedi. Aşağıdaki kaynakları "
            "inceleyebilirsiniz."
        )
        llm_provider_used = "blocked_pii"
    elif is_available():
        sys_prompt = (
            "Sen Türk hukukunda uzman bir avukat asistanısın. Kullanıcının kendi "
            "dava dosyalarını ve emsal Yargıtay/Danıştay kararlarını inceleyerek "
            "soruları yanıtla. Kaynak göster: 'Kendi dosyam X uyarınca...' veya "
            "'Yargıtay 12. HD'nin Y kararında belirtildiği üzere...'. "
            "Sade Türkçe kullan, hukuki terimleri parantez içinde açıkla."
        )
        user_prompt = (
            f"SORU: {redacted_query}\n\n"
            f"KAYNAK İÇERİK:\n{redacted_context[:12000]}\n\n"
            "Yukarıdaki kaynaklara dayanarak soruyu yanıtla."
        )
        try:
            raw_answer = generate(
                system=sys_prompt, user=user_prompt,
                max_tokens=1500, temperature=0.3,
            )
            # 5) PII placeholder'ları geri koy
            answer = unredact(raw_answer, redaction_map)
            llm_provider_used = "anthropic_or_gemini"
            tokens_used = len(user_prompt) // 4 + len(raw_answer) // 4  # yaklaşık
        except Exception as e:
            log.exception("LLM hatası")
            answer = f"LLM yanıt üretemedi: {e}"
    else:
        answer = (
            "LLM şu an erişilemez. Aşağıda en uyumlu kaynakları görebilirsiniz, "
            "ancak AI yanıt üretemiyor."
        )

    duration_ms = int((time.perf_counter() - start) * 1000)

    # Geçmişe kaydet
    try:
        async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
            await conn.execute(
                """INSERT INTO tenant_queries
                   (tenant_id, user_id, query_text, answer_text, document_ids,
                    chunk_count, llm_provider, tokens_used, duration_ms)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                user.tenant_id, user.user_id, payload.query, answer,
                payload.document_ids,
                len(tenant_results) + len(emsal_results),
                llm_provider_used, tokens_used, duration_ms,
            )
    except Exception as e:
        log.warning(f"Sorgu kaydı hatası: {e}")

    return APIResponse(ok=True, data={
        "answer": answer,
        "tenant_sources": [
            {
                "chunk_id": r["chunk_id"],
                "document_id": r.get("meta", {}).get("document_id"),
                "title": r.get("meta", {}).get("title"),
                "snippet": r["text"][:300],
                "similarity": r["similarity"],
            }
            for r in tenant_results
        ],
        "emsal_sources": [
            {
                "chunk_id": r["chunk_id"],
                "court_chamber": r.get("meta", {}).get("court_chamber"),
                "case_no": r.get("meta", {}).get("case_no"),
                "decision_no": r.get("meta", {}).get("decision_no"),
                "snippet": r["text"][:300],
                "similarity": r["similarity"],
            }
            for r in emsal_results
        ],
        "duration_ms": duration_ms,
        "pii": {
            "name_layer": active_layer,
            "names_redacted": names_redacted,
            "warning": pii_warning,
        },
    })


@router.get("/sorgu/gecmis", response_model=APIResponse)
async def query_history(
    user: CurrentUser = Depends(require_uyap),
    limit: int = 50,
):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT id, query_text, answer_text, chunk_count, duration_ms, created_at
               FROM tenant_queries
               WHERE tenant_id = $1
               ORDER BY created_at DESC LIMIT $2""",
            user.tenant_id, min(limit, 200),
        )
    return APIResponse(ok=True, data={
        "queries": [
            {
                "id": str(r["id"]),
                "query": r["query_text"],
                "answer": r["answer_text"],
                "chunk_count": r["chunk_count"],
                "duration_ms": r["duration_ms"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    })
