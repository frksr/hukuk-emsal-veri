"""Tüm cleaned/*.jsonl dosyalarını birleştirip parquet üret + dedup + chunk."""
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent


def export(root: str | Path = "data"):
    root = Path(root)
    cleaned_dir = root / "cleaned"
    final_dir = root / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    files = list(cleaned_dir.glob("*.jsonl"))
    if not files:
        print("[EXPORT] cleaned/*.jsonl bulunamadı, çıktı yok.", file=sys.stderr)
        return

    glob = str(cleaned_dir / "*.jsonl")
    final = final_dir / "all_decisions.parquet"

    duckdb.sql(f"""
        COPY (
            SELECT DISTINCT ON (id) *
            FROM read_json_auto('{glob}', format='newline_delimited',
                                ignore_errors=true)
            WHERE char_count > 200
        )
        TO '{final}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    n = duckdb.sql(f"SELECT COUNT(*) FROM '{final}'").fetchone()[0]
    print(f"[EXPORT] {final} -> {n} kayıt")

    # Kaynak başına döküm
    breakdown = duckdb.sql(
        f"SELECT source, COUNT(*) c FROM '{final}' GROUP BY source ORDER BY c DESC"
    ).fetchall()
    for src, cnt in breakdown:
        print(f"  {src}: {cnt}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="data")
    args = p.parse_args()
    export(args.root)
