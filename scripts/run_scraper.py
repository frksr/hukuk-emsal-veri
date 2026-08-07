"""CLI: yeni emsal karar çekme.

TAM TARAMA (ilk kurulum):
    python scripts/run_scraper.py --source danistay --max 5000

ARTIMLI TAZELEME (düzenli koşu — ÖNERİLEN):
    python scripts/run_scraper.py --source yargitay --since-auto

`--since-auto`, `data/scrape_state.json` içindeki imleci kullanır: en son
görülen karar tarihinden (30 gün güvenlik payıyla) sonrasını ister.
Kaynak destekliyorsa filtre SUNUCU tarafında uygulanır (Yargıtay), yoksa
liste geldikten sonra istemci tarafında süzülür (Danıştay) — her iki durumda
da eski kararlar için pahalı detay isteği yapılmaz.

İmleç koşu SONUNDA, yalnızca ileri yönde güncellenir; yarım kalan bir koşu
imleci geri çekip sonraki koşuları bozmaz.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import scrape_state
from scrapers.aym import AymScraper
from scrapers.danistay import DanistayScraper
from scrapers.hudoc import HudocScraper
from scrapers.yargitay import YargitayScraper

REGISTRY = {
    "hudoc": HudocScraper,
    "yargitay": YargitayScraper,
    "danistay": DanistayScraper,
    "aym": AymScraper,
}

#: `since` parametresini kabul eden scraper'lar. HUDOC/AYM henüz desteklemiyor —
#: eklendiğinde buraya yazılmalı (sessizce yok sayılmasın).
SINCE_DESTEKLI = {"yargitay", "danistay"}


def main() -> int:
    p = argparse.ArgumentParser(description="Emsal karar scraper'ı")
    p.add_argument("--source", choices=list(REGISTRY), required=True)
    p.add_argument("--max", type=int, default=1000)
    p.add_argument("--root", default="data")
    p.add_argument("--since", default=None, metavar="YYYY-MM-DD",
                   help="yalnızca bu tarihten sonraki kararlar")
    p.add_argument("--since-auto", action="store_true",
                   help="son koşudan bu yana olanlar (data/scrape_state.json)")
    p.add_argument("--durum", action="store_true",
                   help="kayıtlı imleçleri göster ve çık")
    args = p.parse_args()

    if args.durum:
        durum = scrape_state.yukle(args.root)
        if not durum:
            print("Henüz kayıtlı koşu yok (data/scrape_state.json bulunamadı).")
            return 0
        print(f"{'kaynak':<12} {'son karar':<12} {'toplam':>9}  son koşu")
        for kaynak, d in sorted(durum.items()):
            print(f"{kaynak:<12} {d.get('son_karar_tarihi', '-'):<12} "
                  f"{d.get('toplam_kayit', 0):>9,}  {d.get('son_kosu', '-')}")
        return 0

    if args.since and args.since_auto:
        p.error("--since ile --since-auto birlikte verilemez.")

    since = args.since
    if args.since_auto:
        since = scrape_state.since_hesapla(args.root, args.source)
        if since is None:
            print(f"[{args.source}] kayıtlı imleç yok → TAM TARAMA yapılacak.",
                  file=sys.stderr)
        else:
            print(f"[{args.source}] artımlı tazeleme: {since} tarihinden itibaren "
                  f"({scrape_state.GUVENLIK_PAYI_GUN} gün güvenlik payı dahil)",
                  file=sys.stderr)

    if since and args.source not in SINCE_DESTEKLI:
        print(f"[{args.source}] UYARI: bu kaynak tarih filtresini desteklemiyor, "
              f"--since yok sayılıyor. Tam tarama yapılacak.", file=sys.stderr)
        since = None

    cls = REGISTRY[args.source]
    if args.source == "hudoc":
        s = cls(root=args.root, limit=args.max)
        asyncio.run(s.run())
    elif since is not None:
        s = cls(root=args.root, since=since)
        asyncio.run(s.run(max_items=args.max))
    else:
        s = cls(root=args.root)
        asyncio.run(s.run(max_items=args.max))

    # İmleci kalıcı hale getir — yalnızca ileri yönde.
    if hasattr(s, "durumu_kaydet"):
        s.durumu_kaydet()
        print(f"[{args.source}] {s.eklenen_kayit} yeni kayıt, "
              f"imleç: {s.en_yeni_tarih or 'değişmedi'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
