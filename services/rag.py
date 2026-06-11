"""Ortak RAG arama servisi — Chroma + multilingual-e5-base.

Tüm özelliklerin (dilekçe, atıf önerici, karşı argüman) kullandığı temel.
"""
from __future__ import annotations
import functools
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Vektör DB ve parquet konumları env ile override edilebilir → cloud'da kalıcı
# volume'a (ör. /data/chroma_db) yönlendirilir. Git'te tutulmaz (bkz. .gitignore).
CHROMA_DIR = Path(os.environ.get("CHROMA_DIR", str(ROOT / "data" / "chroma_db")))
DECISIONS_PARQUET = Path(os.environ.get(
    "DECISIONS_PARQUET", str(ROOT / "data" / "final" / "all_decisions.parquet")))
COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION", "hukuk_kararlari")
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
    try:
        col = _load_collection()
    except Exception as e:
        # Volume henüz seed edilmemiş olabilir → 500 yerine boş sonuç + uyarı.
        import logging
        logging.getLogger("services.rag").warning(
            "Chroma collection '%s' yüklenemedi (CHROMA_DIR=%s): %s — seed gerekli?",
            COLLECTION_NAME, CHROMA_DIR, e)
        return []

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
    parquet = DECISIONS_PARQUET
    if not parquet.exists():
        return None
    try:
        con = duckdb.connect()
        cur = con.execute(
            "SELECT * FROM read_parquet(?) WHERE id = ? LIMIT 1",
            [str(parquet), decision_id],
        )
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        con.close()
        if not rows:
            return None
        return dict(zip(cols, rows[0]))
    except Exception:
        return None


def list_decisions(limit: int = 100, offset: int = 0,
                   source: str | None = None) -> list[dict]:
    """Karar detay sayfaları için sayfalı liste (parquet'ten).

    Yalnızca anonymization_check'i geçen kayıtlar döner — KVKK: kişisel veri
    içerme şüphesi olan karar public sayfada yayımlanmaz.
    """
    import duckdb
    if not DECISIONS_PARQUET.exists():
        return []
    try:
        con = duckdb.connect()
        sql = (
            "SELECT id, source, court_chamber, case_no, decision_no, "
            "decision_date, topic_tags, char_count "
            "FROM read_parquet(?) "
            "WHERE COALESCE(CAST(anonymization_check AS VARCHAR), '') "
            "  NOT IN ('failed', 'false', '0') "
        )
        params: list = [str(DECISIONS_PARQUET)]
        if source:
            sql += "AND source = ? "
            params.append(source)
        sql += "ORDER BY decision_date DESC NULLS LAST LIMIT ? OFFSET ?"
        params += [int(limit), int(offset)]
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        con.close()
        return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []
