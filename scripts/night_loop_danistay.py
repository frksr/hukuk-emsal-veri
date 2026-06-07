"""Danıştay için gece koşusu — keyword'leri sırayla işle, aralarda bekle.

Mantık:
  1. Sıradaki keyword için scraper'ı --max 500 ile başlat
  2. Bitince N dakika bekle (captcha cool-down)
  3. Bir sonraki keyword'e geç
  4. Tüm keyword'ler bittiğinde döngüye geri dön (sürekli daha çok veri)

Kullanım:
  python scripts/night_loop_danistay.py
  python scripts/night_loop_danistay.py --pause-minutes 30 --max-per-keyword 500
  python scripts/night_loop_danistay.py --one-pass    # tek geçişten sonra dur
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

KEYWORDS = [
    "icra", "icra takibi", "icra emri", "ödeme emri",
    "tahsilat", "ihtar", "ihtarname", "haciz",
    "amme alacağı", "vergi tahsilatı", "6183 sayılı",
]


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_keyword(keyword: str, max_per_keyword: int) -> int:
    """Tek keyword için scraper'ı çağır. Exit code döndür."""
    log(f">>> '{keyword}' çekiliyor (max {max_per_keyword})")
    cmd = [
        sys.executable, "-m", "scrapers.danistay",
        "--max", str(max_per_keyword),
        "--keyword", keyword,
        # NOT: --clear YOK; queue persist
    ]
    try:
        proc = subprocess.run(cmd, cwd=ROOT)
        return proc.returncode
    except KeyboardInterrupt:
        log("Ctrl+C — döngü durduruluyor")
        sys.exit(0)


def sleep_with_countdown(minutes: float):
    end = datetime.now() + timedelta(minutes=minutes)
    log(f"--- {minutes:.1f}dk bekleniyor (bitiş: {end:%H:%M:%S}) ---")
    total = int(minutes * 60)
    step = min(60, total)
    elapsed = 0
    while elapsed < total:
        time.sleep(step)
        elapsed += step
        remaining = (total - elapsed) // 60
        if remaining > 0 and remaining % 5 == 0:
            log(f"    {remaining}dk kaldı")
    log("--- bekleme tamam ---")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pause-minutes", type=float, default=25.0,
                   help="Her keyword sonrası bekleme (default 25)")
    p.add_argument("--max-per-keyword", type=int, default=500,
                   help="Bir keyword runda max kaç kayıt (default 500)")
    p.add_argument("--one-pass", action="store_true",
                   help="Tüm keyword'ler bir kere işlenince dur")
    p.add_argument("--keywords", nargs="*", default=None,
                   help="Sadece bu keyword'leri çalıştır (default: hepsi)")
    args = p.parse_args()

    keywords = args.keywords or KEYWORDS
    log(f"Gece koşusu başlıyor. Keyword'ler: {keywords}")
    log(f"Her keyword max {args.max_per_keyword}, aralar {args.pause_minutes}dk")

    pass_num = 0
    while True:
        pass_num += 1
        log(f"\n{'='*60}")
        log(f"  GEÇİŞ #{pass_num}")
        log('='*60)

        for i, kw in enumerate(keywords):
            run_keyword(kw, args.max_per_keyword)
            # Son keyword değilse bekle
            if i < len(keywords) - 1:
                sleep_with_countdown(args.pause_minutes)

        log(f"\nGeçiş #{pass_num} tamamlandı.")

        if args.one_pass:
            log("--one-pass — durulruluyor")
            break

        # Geçişler arası uzun bekleme — IP banı düşmesi için
        log("Geçişler arası 60dk bekleme...")
        sleep_with_countdown(60)


if __name__ == "__main__":
    main()
