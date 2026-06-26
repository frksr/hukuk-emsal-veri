"""Chunk'lara embedding üret ve Postgres (pgvector) 'rag_chunks' tablosuna yaz.

Input:  data/final/chunks.parquet
Output: Cloud SQL / Postgres  ->  rag_chunks  (vector(768))

Embedding sağlayıcısı services.embeddings üzerinden seçilir:
    EMBEDDING_PROVIDER=google  (vars.)  ->  text-embedding-004 (768-dim)
    EMBEDDING_PROVIDER=local            ->  intfloat/multilingual-e5-base

Kullanım:
    python -m pipelines.embed --input data/final/chunks.parquet
    python -m pipelines.embed --recreate            # tabloyu boşalt, sıfırdan
    python -m pipelines.embed --max-chunks 100      # test

Önkoşul: infra/db/19_pgvector.sql çalıştırılmış olmalı; RAG_DATABASE_URL/DATABASE_URL set.
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

import duckdb
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _tags_to_str(tags) -> str:
    if tags is None:
        return ""
    if hasattr(tags, "tolist"):
        tags = tags.tolist()
    if isinstance(tags, (list, tuple)):
        return ",".join(str(t) for t in tags)
    return str(tags)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/final/chunks.parquet")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--max-chunks", type=int, default=None,
                   help="Sadece N chunk için (test)")
    p.add_argument("--recreate", action="store_true",
                   help="rag_chunks tablosunu TRUNCATE et, sıfırdan yaz")
    p.add_argument("--dsn", default=None,
                   help="Override DSN (yoksa RAG_DATABASE_URL/DATABASE_URL)")
    args = p.parse_args()

    from services import embeddings
    import psycopg
    from pgvector.psycopg import register_vector

    dsn = args.dsn or os.environ.get("RAG_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        print("[EMBED] RAG_DATABASE_URL / DATABASE_URL yok", file=sys.stderr)
        sys.exit(1)

    input_path = ROOT / args.input
    print(f"[EMBED] provider={embeddings.PROVIDER} model="
          f"{embeddings.API_MODEL if embeddings.PROVIDER=='google' else embeddings.LOCAL_MODEL} "
          f"dim={embeddings.EMBEDDING_DIM}", file=sys.stderr)

    print(f"[EMBED] chunk'lar yükleniyor: {input_path}", file=sys.stderr)
    sql = f"SELECT * FROM '{input_path}'"
    if args.max_chunks:
        sql += f" LIMIT {args.max_chunks}"
    df = duckdb.sql(sql).df()
    total = len(df)
    print(f"[EMBED] {total} chunk yüklendi", file=sys.stderr)

    conn = psycopg.connect(dsn, autocommit=False)
    register_vector(conn)

    if args.recreate:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE rag_chunks")
        conn.commit()
        print("[EMBED] rag_chunks TRUNCATE edildi", file=sys.stderr)
    else:
        # RESUME: zaten gömülü chunk'ları atla (timeout sonrası kaldığı yerden devam).
        with conn.cursor() as cur:
            cur.execute("SELECT chunk_id FROM rag_chunks")
            existing = {r[0] for r in cur.fetchall()}
        if existing:
            before = len(df)
            df = df[~df["chunk_id"].astype(str).isin(existing)].reset_index(drop=True)
            total = len(df)
            print(f"[EMBED] {len(existing)} chunk zaten var, atlanıyor. "
                  f"Kalan: {total}/{before}", file=sys.stderr)

    upsert_sql = """
        INSERT INTO rag_chunks
            (chunk_id, decision_id, chunk_index, document, source, court_chamber,
             case_no, decision_no, decision_date, topic_tags, source_url, embedding)
        VALUES
            (%(chunk_id)s, %(decision_id)s, %(chunk_index)s, %(document)s, %(source)s,
             %(court_chamber)s, %(case_no)s, %(decision_no)s, %(decision_date)s,
             %(topic_tags)s, %(source_url)s, %(embedding)s)
        ON CONFLICT (chunk_id) DO UPDATE SET
            document      = EXCLUDED.document,
            decision_id   = EXCLUDED.decision_id,
            chunk_index   = EXCLUDED.chunk_index,
            source        = EXCLUDED.source,
            court_chamber = EXCLUDED.court_chamber,
            case_no       = EXCLUDED.case_no,
            decision_no   = EXCLUDED.decision_no,
            decision_date = EXCLUDED.decision_date,
            topic_tags    = EXCLUDED.topic_tags,
            source_url    = EXCLUDED.source_url,
            embedding     = EXCLUDED.embedding
    """

    bs = args.batch_size
    written = 0
    for start in tqdm(range(0, total, bs), desc="embed"):
        end = min(start + bs, total)
        batch = df.iloc[start:end]

        texts = batch["chunk_text"].tolist()
        vectors = embeddings.embed_passages(texts)

        rows = []
        for (_, r), vec in zip(batch.iterrows(), vectors):
            rows.append({
                "chunk_id": str(r["chunk_id"]),
                "decision_id": str(r.get("decision_id") or ""),
                "chunk_index": int(r.get("chunk_index", 0) or 0),
                "document": str(r["chunk_text"]),
                "source": str(r.get("source") or ""),
                "court_chamber": str(r.get("court_chamber") or ""),
                "case_no": str(r.get("case_no") or ""),
                "decision_no": str(r.get("decision_no") or ""),
                "decision_date": str(r.get("decision_date") or ""),
                "topic_tags": _tags_to_str(r.get("topic_tags")),
                "source_url": str(r.get("source_url") or ""),
                "embedding": vec,
            })

        with conn.cursor() as cur:
            cur.executemany(upsert_sql, rows)
        conn.commit()
        written += len(rows)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM rag_chunks")
        final_count = cur.fetchone()[0]
    conn.close()
    print(f"[EMBED] tamamlandı. Bu çalışmada {written} chunk yazıldı. "
          f"Toplam rag_chunks={final_count}", file=sys.stderr)


if __name__ == "__main__":
    main()
