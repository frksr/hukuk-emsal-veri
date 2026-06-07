"""Chunk'lara embedding üret ve Chroma'ya yaz.

Input:  data/final/chunks.parquet
Output: data/chroma_db/  (Chroma persist directory)

Model:  intfloat/multilingual-e5-base (varsayılan)
- 768-dim
- Türkçe + İngilizce
- HUDOC İngilizce kararlar için de uygun

Daha küçük/hızlı isteyenler için: intfloat/multilingual-e5-small (384-dim)
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import duckdb
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/final/chunks.parquet")
    p.add_argument("--chroma-dir", default="data/chroma_db")
    p.add_argument("--collection", default="hukuk_kararlari")
    p.add_argument("--model", default="intfloat/multilingual-e5-base",
                   help="HF model id veya local path")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--device", default="cpu",
                   help="cpu | cuda | mps")
    p.add_argument("--max-chunks", type=int, default=None,
                   help="Sadece N chunk için (test için)")
    p.add_argument("--recreate", action="store_true",
                   help="Mevcut collection'ı sil, sıfırdan oluştur")
    args = p.parse_args()

    input_path = ROOT / args.input
    chroma_dir = ROOT / args.chroma_dir
    chroma_dir.mkdir(parents=True, exist_ok=True)

    print(f"[EMBED] model yükleniyor: {args.model}", file=sys.stderr)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(args.model, device=args.device)
    dim = model.get_sentence_embedding_dimension()
    print(f"[EMBED] model yüklendi (dim={dim})", file=sys.stderr)

    print(f"[EMBED] chunk'lar yükleniyor: {input_path}", file=sys.stderr)
    sql = f"SELECT * FROM '{input_path}'"
    if args.max_chunks:
        sql += f" LIMIT {args.max_chunks}"
    df = duckdb.sql(sql).df()
    print(f"[EMBED] {len(df)} chunk yüklendi", file=sys.stderr)

    import chromadb
    client = chromadb.PersistentClient(path=str(chroma_dir))

    if args.recreate:
        try:
            client.delete_collection(name=args.collection)
            print(f"[EMBED] eski '{args.collection}' silindi", file=sys.stderr)
        except Exception:
            pass

    col = client.get_or_create_collection(
        name=args.collection,
        metadata={"hnsw:space": "cosine"},
    )

    # E5 model prefix gereksinimi:
    # - Sorgu: "query: ..."
    # - Doküman: "passage: ..."
    use_e5_prefix = "e5" in args.model.lower()

    batch_size = args.batch_size
    total = len(df)

    # Mevcut chunk_id'leri kontrol et — idempotent yazma
    try:
        existing_count = col.count()
        print(f"[EMBED] mevcut collection: {existing_count} kayıt",
              file=sys.stderr)
    except Exception:
        existing_count = 0

    pbar = tqdm(range(0, total, batch_size), desc="embed")
    for start in pbar:
        end = min(start + batch_size, total)
        batch = df.iloc[start:end]

        texts = batch["chunk_text"].tolist()
        if use_e5_prefix:
            texts = [f"passage: {t}" for t in texts]

        embeddings = model.encode(
            texts, batch_size=batch_size,
            convert_to_numpy=True, normalize_embeddings=True,
            show_progress_bar=False,
        )

        # Chroma'da metadata None kabul etmiyor; convert
        def _meta(row):
            tags = row.get("topic_tags")
            if hasattr(tags, "tolist"):
                tags = tags.tolist()
            return {
                "decision_id": row.get("decision_id") or "",
                "chunk_index": int(row.get("chunk_index", 0)),
                "source": row.get("source") or "",
                "court_chamber": row.get("court_chamber") or "",
                "case_no": row.get("case_no") or "",
                "decision_no": row.get("decision_no") or "",
                "decision_date": row.get("decision_date") or "",
                "topic_tags": ",".join(tags) if tags else "",
                "source_url": row.get("source_url") or "",
            }

        col.upsert(
            ids=batch["chunk_id"].tolist(),
            embeddings=embeddings.tolist(),
            documents=batch["chunk_text"].tolist(),
            metadatas=[_meta(r) for _, r in batch.iterrows()],
        )

    final_count = col.count()
    print(f"[EMBED] tamamlandı. Toplam {final_count} chunk Chroma'da",
          file=sys.stderr)


if __name__ == "__main__":
    main()
