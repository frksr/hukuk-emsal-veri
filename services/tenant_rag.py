"""Per-tenant RAG — her tenant kendi Chroma collection'ına sahip.

Tenant izolasyonu:
- Collection name: tenant_{tenant_id}
- Document → chunk → embed → her chunk'a doc_id metadata
- Arama: her zaman tenant'ın kendi collection'ında

Public RAG (10K emsal karar) ile aynı embedding modeli kullanılır — sorgu
hem public emsallerde hem kendi dosyalarında çalıştırılabilir.
"""
from __future__ import annotations
import functools
import logging
import os
from pathlib import Path

log = logging.getLogger("services.tenant_rag")

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
TENANT_CHROMA_DIR = Path(os.environ.get("TENANT_CHROMA_DIR", "data/tenant_chroma"))
TENANT_CHROMA_DIR.mkdir(parents=True, exist_ok=True)


@functools.lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL, device="cpu")


@functools.lru_cache(maxsize=64)
def _client():
    import chromadb
    return chromadb.PersistentClient(path=str(TENANT_CHROMA_DIR))


def _collection_name(tenant_id: str) -> str:
    # Chroma collection name: 3-63 char, ascii
    safe = tenant_id.replace("-", "")[:60]
    return f"t_{safe}"


def get_or_create_collection(tenant_id: str):
    return _client().get_or_create_collection(
        name=_collection_name(tenant_id),
        metadata={"tenant_id": tenant_id, "hnsw:space": "cosine"},
    )


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
        # Fallback
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size - overlap)]


def index_document(
    tenant_id: str,
    document_id: str,
    text: str,
    metadata: dict | None = None,
) -> int:
    """Dokümanı chunk'la, embed et, tenant collection'a yaz. Chunk sayısı döner."""
    if not text or len(text) < 50:
        return 0

    chunks = chunk_text(text)
    if not chunks:
        return 0

    model = _model()
    embeddings = model.encode(
        [f"passage: {c}" for c in chunks],
        normalize_embeddings=True, show_progress_bar=False,
    ).tolist()

    col = get_or_create_collection(tenant_id)
    base_meta = metadata or {}
    base_meta["document_id"] = document_id

    ids = [f"{document_id}_c{i:04d}" for i in range(len(chunks))]
    metas = [{**base_meta, "chunk_index": i} for i in range(len(chunks))]

    col.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metas)
    return len(chunks)


def search_tenant(
    tenant_id: str,
    query: str,
    k: int = 5,
    document_ids: list[str] | None = None,
) -> list[dict]:
    """Tenant'ın dosyalarında arama."""
    model = _model()
    q_emb = model.encode([f"query: {query}"], normalize_embeddings=True).tolist()

    col = get_or_create_collection(tenant_id)
    where: dict | None = None
    if document_ids:
        where = {"document_id": {"$in": document_ids}}

    results = col.query(
        query_embeddings=q_emb, n_results=k,
        where=where,
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    ids = results.get("ids", [[]])[0]

    return [
        {
            "chunk_id": cid,
            "text": doc,
            "meta": meta,
            "similarity": 1 - dist,
        }
        for cid, doc, meta, dist in zip(ids, docs, metas, dists)
    ]


def delete_document(tenant_id: str, document_id: str):
    """Dokümanın tüm chunk'larını collection'dan sil."""
    col = get_or_create_collection(tenant_id)
    col.delete(where={"document_id": document_id})


def delete_tenant_collection(tenant_id: str):
    """Tüm tenant collection'ını sil (KVKK)."""
    try:
        _client().delete_collection(name=_collection_name(tenant_id))
    except Exception as e:
        log.warning(f"Collection silme hatası: {e}")


def get_tenant_stats(tenant_id: str) -> dict:
    """Tenant'ın vector store istatistiği."""
    try:
        col = get_or_create_collection(tenant_id)
        return {"chunk_count": col.count(), "available": True}
    except Exception:
        return {"chunk_count": 0, "available": False}
