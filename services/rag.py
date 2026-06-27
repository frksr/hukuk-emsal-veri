"""Ortak RAG arama servisi — pgvector (Cloud SQL) + API embedding.

Tüm özelliklerin (dilekçe, atıf önerici, karşı argüman) kullandığı temel.

Mimari (bkz. PGVECTOR_GOC_PLANI.md):
- Embedding: services.embeddings (Google API / lokal e5; sorgu cache'li)
- Vektör deposu: Postgres 'rag_chunks' tablosu, cosine HNSW indeksli
- Tam karar metni + listeleme: hâlâ parquet üzerinden (DuckDB, düşük bellek)

Public fonksiyon imzaları ESKİSİYLE AYNI (search/get_collection_stats/...);
router ve servis caller'ları değişmez.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path

log = logging.getLogger("services.rag")

ROOT = Path(__file__).resolve().parent.parent
DECISIONS_PARQUET = Path(os.environ.get(
    "DECISIONS_PARQUET", str(ROOT / "data" / "final" / "all_decisions.parquet")))

# Chroma where-dict'inden çıkarılabilen filtre alanları (yalnızca bunlar kullanılıyor).
_FILTER_COLS = {"source", "court_chamber"}


def _extract_filters(where: dict | None) -> dict:
    """Eski Chroma where formatını {kolon: değer} sözlüğüne indirger.

    Desteklenen biçimler:
      {"source": "yargitay"}
      {"$and": [{"source": "yargitay"}, {"court_chamber": "12. HD"}]}
    """
    out: dict = {}
    if not where:
        return out
    if "$and" in where:
        for sub in where["$and"]:
            out.update(_extract_filters(sub))
        return out
    for key, val in where.items():
        if key in _FILTER_COLS and not isinstance(val, dict):
            out[key] = val
    return out


def search(query: str, k: int = 5, where: dict | None = None) -> list[dict]:
    """RAG araması yap — top-k sonuç döndür.

    Returns:
      [{'text': str, 'meta': dict, 'similarity': float, 'chunk_id': str}, ...]
    """
    from services import embeddings
    from services import pg

    try:
        q_emb = embeddings.embed_query(query)
    except Exception as e:
        log.warning("Embedding üretilemedi: %s", e)
        return []

    filters = _extract_filters(where)
    sql = """
        SELECT chunk_id, decision_id, chunk_index, document, source, court_chamber,
               case_no, decision_no, decision_date, topic_tags, source_url,
               1 - (embedding <=> %(q)s::vector) AS similarity
        FROM rag_chunks
        WHERE (%(source)s::text IS NULL OR source = %(source)s)
          AND (%(court)s::text IS NULL OR court_chamber = %(court)s)
        ORDER BY embedding <=> %(q)s::vector
        LIMIT %(k)s
    """
    params = {
        "q": q_emb,
        "source": filters.get("source"),
        "court": filters.get("court_chamber"),
        "k": int(k),
    }

    try:
        with pg.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
    except Exception as e:
        log.warning("pgvector araması başarısız: %s — şema/seed gerekli?", e)
        return []

    out = []
    for row in rows:
        rec = dict(zip(cols, row))
        out.append({
            "chunk_id": rec["chunk_id"],
            "text": rec["document"],
            "similarity": float(rec["similarity"]) if rec["similarity"] is not None else 0.0,
            "meta": {
                "decision_id": rec["decision_id"],
                "chunk_index": rec["chunk_index"],
                "source": rec["source"],
                "court_chamber": rec["court_chamber"],
                "case_no": rec["case_no"],
                "decision_no": rec["decision_no"],
                "decision_date": rec["decision_date"],
                "topic_tags": rec["topic_tags"],
                "source_url": rec["source_url"],
            },
        })
    return out


def get_collection_stats() -> dict:
    from services import pg
    try:
        with pg.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM rag_chunks")
                count = cur.fetchone()[0]
        return {"chunk_count": int(count), "available": True}
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


def related_decisions(decision_id: str, limit: int = 6) -> list[dict]:
    """Verilen karara 'ilgili' kararları döndür (aynı daire, sonra aynı kaynak).

    İç linkleme/topical authority için (SEO_ANALIZ B3): karar detay sayfaları
    izole kalmasın. Maliyetsiz — parquet/DuckDB metadata filtresi, LLM yok.
    Yalnızca anonymization_check'i geçen kararlar; kendisi hariç tutulur.
    """
    import duckdb
    if not DECISIONS_PARQUET.exists():
        return []
    try:
        con = duckdb.connect()
        src = str(DECISIONS_PARQUET)
        # Önce mevcut kararın daire/kaynağını al.
        ref = con.execute(
            "SELECT source, court_chamber FROM read_parquet(?) WHERE id = ? LIMIT 1",
            [src, decision_id],
        ).fetchall()
        if not ref:
            con.close()
            return []
        source, court_chamber = ref[0][0], ref[0][1]

        anon_ok = (
            "COALESCE(CAST(anonymization_check AS VARCHAR), '') "
            "NOT IN ('failed', 'false', '0')"
        )
        base_cols = (
            "id, source, court_chamber, case_no, decision_no, "
            "decision_date, topic_tags"
        )

        rows: list = []
        cols: list = []
        # 1) Aynı daire (en alakalı).
        if court_chamber:
            cur = con.execute(
                f"SELECT {base_cols} FROM read_parquet(?) "
                f"WHERE court_chamber = ? AND id <> ? AND {anon_ok} "
                f"ORDER BY decision_date DESC NULLS LAST LIMIT ?",
                [src, court_chamber, decision_id, int(limit)],
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        # 2) Yetersizse aynı kaynaktan tamamla.
        if len(rows) < limit and source:
            haric = [decision_id] + [r[0] for r in rows]
            ph = ", ".join("?" for _ in haric)
            cur = con.execute(
                f"SELECT {base_cols} FROM read_parquet(?) "
                f"WHERE source = ? AND id NOT IN ({ph}) AND {anon_ok} "
                f"ORDER BY decision_date DESC NULLS LAST LIMIT ?",
                [src, source, *haric, int(limit - len(rows))],
            )
            if not cols:
                cols = [d[0] for d in cur.description]
            rows += cur.fetchall()
        con.close()
        return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []
