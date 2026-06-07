"""Ortak RAG arama servisi — Chroma + multilingual-e5-base.

Tüm özelliklerin (dilekçe, atıf önerici, karşı argüman) kullandığı temel.
"""
from __future__ import annotations
import functools
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "data" / "chroma_db"
COLLECTION_NAME = "hukuk_kararlari"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL",
                                  "intfloat/multilingual-e5-base")


@functools.lru_cache(maxsize=1)
def _load_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL, device="cpu")


@functools.lru_cache(maxsize=1)
def _load_collection():
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(name=COLLECTION_NAME)


def search(query: str, k: int = 5, where: dict | None = None) -> list[dict]:
    """RAG araması yap — top-k sonuç döndür.

    Returns:
      [{'text': str, 'meta': dict, 'similarity': float, 'chunk_id': str}, ...]
    """
    model = _load_model()
    col = _load_collection()

    q_emb = model.encode([f"query: {query}"],
                         normalize_embeddings=True).tolist()

    results = col.query(
        query_embeddings=q_emb,
        n_results=k,
        where=where if where else None,
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


def get_collection_stats() -> dict:
    try:
        col = _load_collection()
        return {"chunk_count": col.count(), "available": True}
    except Exception as e:
        return {"chunk_count": 0, "available": False, "error": str(e)}


def get_full_decision(decision_id: str) -> dict | None:
    """Parquet'ten tam karar metnini çek."""
    import duckdb
    parquet = ROOT / "data" / "final" / "all_decisions.parquet"
    if not parquet.exists():
        return None
    try:
        rows = duckdb.sql(
            f"SELECT * FROM '{parquet}' WHERE id = '{decision_id}' LIMIT 1"
        ).fetchall()
        cols = duckdb.sql(f"SELECT * FROM '{parquet}' LIMIT 0").columns
        if not rows:
            return None
        return dict(zip(cols, rows[0]))
    except Exception:
        return None
