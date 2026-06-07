"""Canlı toplama istatistikleri — cleaned/*.jsonl dosyalarını analiz eder.

Kullanım:
  python3 analytics/coverage.py                # tek seferlik özet
  python3 analytics/coverage.py --watch        # 10sn'de bir yeniler
  python3 analytics/coverage.py --watch --interval 5
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def _extract_year(date_str: str | None) -> str:
    """DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY formatlarından 4 haneli yılı çıkar."""
    if not date_str:
        return "?"
    m = _YEAR_RE.search(date_str)
    return m.group(1) if m else "?"

ROOT = Path(__file__).resolve().parent.parent
CLEANED = ROOT / "data" / "cleaned"


def _read_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def summarize():
    if not CLEANED.exists():
        print("data/cleaned dizini yok. Henüz hiç scraper çalışmamış.")
        return

    files = sorted(CLEANED.glob("*.jsonl"))
    if not files:
        print("data/cleaned/*.jsonl yok.")
        return

    total = 0
    per_source: Counter[str] = Counter()
    per_chamber: Counter[str] = Counter()
    per_year: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    topic_relevant = 0
    pii_dirty = 0
    char_counts: list[int] = []

    for path in files:
        for rec in _read_jsonl(path):
            total += 1
            per_source[rec.get("source", "?")] += 1
            ch = rec.get("court_chamber") or "?"
            per_chamber[ch] += 1
            year = _extract_year(rec.get("decision_date"))
            per_year[year] += 1
            tags = rec.get("topic_tags") or []
            for t in tags:
                topic_counts[t] += 1
            if rec.get("is_topic_relevant") or tags:
                topic_relevant += 1
            cc = rec.get("anonymization_check") or {}
            if cc.get("contains_pii"):
                pii_dirty += 1
            cc_count = rec.get("char_count") or 0
            if cc_count:
                char_counts.append(cc_count)

    print(f"\n{'='*60}")
    print(f"  TOPLAMA İSTATİSTİĞİ — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"Toplam kayıt:           {total}")
    print(f"Konu-ilgili (tag dolu): {topic_relevant} ({topic_relevant*100//max(total,1)}%)")
    print(f"PII içeren:             {pii_dirty}")
    if char_counts:
        avg = sum(char_counts) // len(char_counts)
        mn, mx = min(char_counts), max(char_counts)
        print(f"Karakter sayısı:        avg={avg}, min={mn}, max={mx}")

    print("\nKaynak başına:")
    for src, n in per_source.most_common():
        print(f"  {src:12s} {n:>6d}")

    if topic_counts:
        print("\nEn sık topic tag'leri:")
        for tag, n in topic_counts.most_common(15):
            print(f"  {tag:25s} {n:>6d}")

    if per_year and len(per_year) > 1:
        print("\nYıllara göre dağılım (top 10):")
        for y, n in sorted(per_year.items(), key=lambda x: -x[1])[:10]:
            print(f"  {y}  {n:>6d}")

    if per_chamber and len(per_chamber) > 1:
        print("\nMahkeme/daire (top 10):")
        for ch, n in per_chamber.most_common(10):
            ch_short = ch[:40] + "..." if len(ch) > 40 else ch
            print(f"  {ch_short:43s} {n:>6d}")

    # Disk kullanımı
    raw_dir = ROOT / "data" / "raw"
    if raw_dir.exists():
        total_bytes = sum(p.stat().st_size for p in raw_dir.rglob("*") if p.is_file())
        mb = total_bytes / (1024 * 1024)
        print(f"\nHam HTML disk:          {mb:.1f} MB")


def watch(interval: float):
    try:
        while True:
            # Terminal'i temizle (Win + Unix)
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()
            summarize()
            print(f"\n[Ctrl+C ile çık. {interval}sn'de bir yenileniyor.]")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nÇıkış.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=float, default=10.0)
    args = p.parse_args()

    if args.watch:
        watch(args.interval)
    else:
        summarize()
