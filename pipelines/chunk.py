"""Karar metinlerini RAG için chunk'lara böl.

Input:  data/final/all_decisions.parquet
Output: data/final/chunks.parquet

Strateji:
- 1000 karakter chunk, 150 overlap
- Türk hukuk metinlerinde paragraf/madde sınırları öncelikli
- Her chunk parent kararın metadata'sını taşır
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

ROOT = Path(__file__).resolve().parent.parent


def _simple_splitter(text: str, chunk_size: int = 1000,
                     overlap: int = 150) -> list[str]:
    """Langchain yoksa fallback: paragraf/cümle bazlı bölme."""
    if not text:
        return []
    chunks = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            # Eğer paragraf tek başına chunk_size'dan büyükse, böl
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size - overlap):
                    chunks.append(para[i:i + chunk_size])
                current = ""
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks


def _langchain_splitter(text: str, chunk_size: int = 1000,
                        overlap: int = 150) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    return splitter.split_text(text or "")


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if HAS_LANGCHAIN:
        return _langchain_splitter(text, chunk_size, overlap)
    return _simple_splitter(text, chunk_size, overlap)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/final/all_decisions.parquet")
    p.add_argument("--output", default="data/final/chunks.parquet")
    p.add_argument("--chunk-size", type=int, default=1000)
    p.add_argument("--overlap", type=int, default=150)
    p.add_argument("--min-chunk", type=int, default=100,
                   help="Bu boyutun altında chunk'lar atılır")
    args = p.parse_args()

    input_path = ROOT / args.input
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[CHUNK] reading {input_path}", file=sys.stderr)
    print(f"[CHUNK] langchain mevcut: {HAS_LANGCHAIN}", file=sys.stderr)

    # DuckDB ile sadece gerekli alanları yükle
    df = duckdb.sql(f"""
        SELECT id, source, court_chamber, case_no, decision_no,
               decision_date, cleaned_text, topic_tags, source_url,
               char_count
        FROM '{input_path}'
        WHERE char_count > 200
    """).df()
    print(f"[CHUNK] {len(df)} karar yüklendi", file=sys.stderr)

    def _s(v) -> str:
        """NaN/None → '', diğerleri str."""
        if v is None:
            return ""
        # pandas NaN float kontrolü
        try:
            import math
            if isinstance(v, float) and math.isnan(v):
                return ""
        except Exception:
            pass
        return str(v)

    def _tags(v) -> list[str]:
        """topic_tags listesini güvenli yap."""
        if v is None:
            return []
        if hasattr(v, "tolist"):
            return [str(x) for x in v.tolist() if x is not None]
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        return []

    rows = []
    skipped = 0
    for _, rec in tqdm(df.iterrows(), total=len(df), desc="chunk"):
        text = rec["cleaned_text"]
        if not text or not isinstance(text, str):
            skipped += 1
            continue
        chunks = split_text(text, args.chunk_size, args.overlap)
        for i, ch in enumerate(chunks):
            if len(ch) < args.min_chunk:
                continue
            rows.append({
                "chunk_id": f"{_s(rec['id'])}_c{i:03d}",
                "decision_id": _s(rec["id"]),
                "chunk_index": i,
                "chunk_text": ch,
                "chunk_char_count": len(ch),
                "source": _s(rec["source"]),
                "court_chamber": _s(rec["court_chamber"]),
                "case_no": _s(rec["case_no"]),
                "decision_no": _s(rec["decision_no"]),
                "decision_date": _s(rec["decision_date"]),
                "topic_tags": _tags(rec["topic_tags"]),
                "source_url": _s(rec["source_url"]),
            })

    print(f"[CHUNK] {len(rows)} chunk üretildi ({skipped} karar atlandı)",
          file=sys.stderr)
    if not rows:
        print("[CHUNK] hiç chunk üretilemedi", file=sys.stderr)
        return

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, output_path, compression="zstd")

    # Özet
    avg_chunks_per_decision = len(rows) / len(df)
    avg_chunk_size = sum(r["chunk_char_count"] for r in rows) / len(rows)
    print(f"[CHUNK] yazıldı: {output_path}", file=sys.stderr)
    print(f"[CHUNK] karar başına ort {avg_chunks_per_decision:.1f} chunk",
          file=sys.stderr)
    print(f"[CHUNK] ort chunk boyutu {avg_chunk_size:.0f} char", file=sys.stderr)


if __name__ == "__main__":
    main()
