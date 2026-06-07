"""JSONL kayıtlarını okumak için inspector — cmd/PowerShell agnostic.

Kullanım:
  python scripts/inspect_jsonl.py data/cleaned/danistay.jsonl
  python scripts/inspect_jsonl.py data/cleaned/danistay.jsonl --n 3
  python scripts/inspect_jsonl.py data/cleaned/danistay.jsonl --tail --n 2
  python scripts/inspect_jsonl.py data/cleaned/danistay.jsonl --stats
  python scripts/inspect_jsonl.py data/cleaned/danistay.jsonl --field topic_tags
"""
import argparse
import json
import sys
from pathlib import Path


def show_record(rec: dict, idx: int, preview_len: int, only_field: str | None):
    if only_field:
        print(f"--- Kayıt {idx} ---")
        print(f"{only_field}: {rec.get(only_field)}")
        return

    summary = {
        "id": rec.get("id"),
        "court_chamber": rec.get("court_chamber"),
        "case_no": rec.get("case_no"),
        "decision_no": rec.get("decision_no"),
        "decision_date": rec.get("decision_date"),
        "char_count": rec.get("char_count"),
        "topic_tags": rec.get("topic_tags"),
        "found_via_query": rec.get("subject_keywords_query"),
        "anonymization": rec.get("anonymization_check"),
    }
    print(f"\n{'='*70}")
    print(f"  KAYIT {idx}")
    print('='*70)
    for k, v in summary.items():
        print(f"  {k:25s} {v}")

    text = rec.get("cleaned_text") or ""
    preview = text[:preview_len]
    print(f"\n  cleaned_text (ilk {len(preview)} karakter):")
    print(f"  {'-'*50}")
    for ln in preview.split("\n"):
        print(f"  {ln}")
    if len(text) > preview_len:
        print(f"  ... ({len(text) - preview_len} karakter daha)")


def show_stats(all_records: list[dict], path: Path):
    total = len(all_records)
    with_text = 0
    empty = 0
    char_counts = []
    chambers: dict[str, int] = {}
    for r in all_records:
        cc = r.get("char_count", 0) or 0
        char_counts.append(cc)
        if cc > 500:
            with_text += 1
        elif cc == 0:
            empty += 1
        ch = r.get("court_chamber") or "?"
        chambers[ch] = chambers.get(ch, 0) + 1

    print(f"\n{'='*60}")
    print(f"  İSTATİSTİK — {path}")
    print('='*60)
    print(f"Toplam kayıt:        {total}")
    print(f"Tam metinli (>500):  {with_text}")
    print(f"Orta (1-500):        {total - with_text - empty}")
    print(f"Boş metin (0):       {empty}")
    if char_counts:
        avg = sum(char_counts) // max(len(char_counts), 1)
        print(f"Avg char_count:      {avg}")
        print(f"Max char_count:      {max(char_counts)}")
    print("Mahkeme/daire (top 10):")
    for ch, n in sorted(chambers.items(), key=lambda x: -x[1])[:10]:
        print(f"  {(ch or '?')[:50]:50s} {n}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path", help="JSONL dosya yolu")
    p.add_argument("--n", type=int, default=1)
    p.add_argument("--preview", type=int, default=500)
    p.add_argument("--field", help="Sadece bu field'ı göster")
    p.add_argument("--tail", action="store_true",
                   help="Dosyanın sonundan N kayıt göster")
    p.add_argument("--stats", action="store_true",
                   help="İstatistik özet — kaç kayıtta tam metin var?")
    args = p.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"DOSYA YOK: {path}")
        sys.exit(1)

    # Tüm satırları parse et
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception as e:
                print(f"satır {i}: parse hatası: {e}")

    if args.stats:
        show_stats(records, path)
        return

    if args.tail:
        slice_ = records[-args.n:]
        start = len(records) - len(slice_) + 1
    else:
        slice_ = records[:args.n]
        start = 1

    for offset, rec in enumerate(slice_):
        show_record(rec, start + offset, args.preview, args.field)

    print(f"\n{'='*70}")
    print(f"  Dosyada toplam {len(records)} kayıt var")


if __name__ == "__main__":
    main()
