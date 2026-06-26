"""Per-tenant RAG — pgvector 'tenant_rag_chunks' tablosu.

Tenant izolasyonu:
- Her satırda tenant_id (UUID) tutulur.
- Her sorgu/silme işlemi explicit `WHERE tenant_id = $1` ile filtrelenir
  (kod tenant_id'yi her zaman geçirir). Ek savunma için RLS opsiyonu:
  bkz. infra/db/19_pgvector.sql.
- Embedding: public RAG ile AYNI model (services.embeddings) — sorgu hem public
  emsallerde hem kendi dosyalarında aynı uzayda çalışır.

Public fonksiyon imzaları ESKİSİYLE AYNI; uyap router'ı değişmez.
"""
from __future__ import annotations
import json
import logging
import uuid

log = logging.getLogger("services.tenant_rag")


def _tid(tenant_id: str) -> str:
    """tenant_id'yi UUID string'e doğrula/normalize et."""
    return str(uuid.UUID(str(tenant_id)))


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """Basit cümle bazlı chunking."""
    if not text:
        return []
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_text(text)
    except ImportError:
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]


def index_document(
    tenant_id: str,
    document_id: str,
    text: str,
    metadata: dict | None = None,
) -> int:
    """Dokümanı chunk'la, embed et, tenant_rag_chunks'a yaz. Chunk sayısı döner."""
    if not text or len(text) < 50:
        return 0

    chunks = chunk_text(text)
    if not chunks:
        return 0

    from services import embeddings
    from services import pg

    tid = _tid(tenant_id)
    vectors = embeddings.embed_passages(chunks)

    base_meta = dict(metadata or {})
    base_meta["document_id"] = document_id

    rows = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        meta = {**base_meta, "chunk_index": i}
        rows.append({
            "chunk_id": f"{document_id}_c{i:04d}",
            "tenant_id": tid,
            "document_id": document_id,
            "chunk_index": i,
            "document": chunk,
            "meta": json.dumps(meta),
            "embedding": vec,
        })

    upsert_sql = """
        INSERT INTO tenant_rag_chunks
            (chunk_id, tenant_id, document_id, chunk_index, document, meta, embedding)
        VALUES
            (%(chunk_id)s, %(tenant_id)s, %(document_id)s, %(chunk_index)s,
             %(document)s, %(meta)s, %(embedding)s)
        ON CONFLICT (chunk_id) DO UPDATE SET
            document    = EXCLUDED.document,
            chunk_index = EXCLUDED.chunk_index,
            meta        = EXCLUDED.meta,
            embedding   = EXCLUDED.embedding
    """
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(upsert_sql, rows)
    return len(chunks)


def search_tenant(
    tenant_id: str,
    query: str,
    k: int = 5,
    document_ids: list[str] | None = None,
) -> list[dict]:
    """Tenant'ın dosyalarında arama (yalnızca kendi tenant_id'si)."""
    from services import embeddings
    from services import pg

    tid = _tid(tenant_id)
    try:
        q_emb = embeddings.embed_query(query)
    except Exception as e:
        log.warning("Embedding üretilemedi: %s", e)
        return []

    sql = """
        SELECT chunk_id, document_id, chunk_index, document, meta,
               1 - (embedding <=> %(q)s) AS similarity
        FROM tenant_rag_chunks
        WHERE tenant_id = %(tid)s
          AND (%(docs)s::text[] IS NULL OR document_id = ANY(%(docs)s))
        ORDER BY embedding <=> %(q)s
        LIMIT %(k)s
    """
    params = {
        "q": q_emb,
        "tid": tid,
        "docs": list(document_ids) if document_ids else None,
        "k": int(k),
    }

    try:
        with pg.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
    except Exception as e:
        log.warning("tenant pgvector araması başarısız: %s", e)
        return []

    out = []
    for row in rows:
        rec = dict(zip(cols, row))
        meta = rec["meta"] or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        out.append({
            "chunk_id": rec["chunk_id"],
            "text": rec["document"],
            "similarity": float(rec["similarity"]) if rec["similarity"] is not None else 0.0,
            "meta": meta,
        })
    return out


def delete_document(tenant_id: str, document_id: str):
    """Dokümanın tüm chunk'larını sil (tenant kapsamında)."""
    from services import pg
    tid = _tid(tenant_id)
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tenant_rag_chunks WHERE tenant_id = %s AND document_id = %s",
                (tid, document_id),
            )


def delete_tenant_collection(tenant_id: str):
    """Tüm tenant verisini sil (KVKK)."""
    from services import pg
    tid = _tid(tenant_id)
    try:
        with pg.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tenant_rag_chunks WHERE tenant_id = %s", (tid,))
    except Exception as e:
        log.warning(f"Tenant veri silme hatası: {e}")


def get_tenant_stats(tenant_id: str) -> dict:
    """Tenant'ın vector store istatistiği."""
    from services import pg
    try:
        tid = _tid(tenant_id)
        with pg.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM tenant_rag_chunks WHERE tenant_id = %s",
                    (tid,))
                count = cur.fetchone()[0]
        return {"chunk_count": int(count), "available": True}
    except Exception:
        return {"chunk_count": 0, "available": False}
