"""CLI: python scripts/run_scraper.py --source hudoc --max 500"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.hudoc import HudocScraper
from scrapers.yargitay import YargitayScraper
from scrapers.danistay import DanistayScraper
from scrapers.aym import AymScraper

REGISTRY = {
    "hudoc": HudocScraper,
    "yargitay": YargitayScraper,
    "danistay": DanistayScraper,
    "aym": AymScraper,
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=list(REGISTRY), required=True)
    p.add_argument("--max", type=int, default=1000)
    p.add_argument("--root", default="data")
    args = p.parse_args()

    cls = REGISTRY[args.source]
    if args.source == "hudoc":
        s = cls(root=args.root, limit=args.max)
        asyncio.run(s.run())
    else:
        s = cls(root=args.root)
        asyncio.run(s.run(max_items=args.max))


if __name__ == "__main__":
    main()
