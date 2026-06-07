"""Anayasa Mahkemesi Kararlar Bilgi Bankası scraper.

Site: https://kararlarbilgibankasi.anayasa.gov.tr/
Bireysel başvuru kararlarında mülkiyet hakkı / adil yargılanma kapsamında
icra-tahsilat içerikli zengin veri.
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from typing import Iterable

import yaml
from selectolax.parser import HTMLParser

from common.normalize import (
    normalize_text, extract_case_no, extract_decision_no,
    extract_decision_date, detect_keywords,
)
from common.anonymize import audit
from common.http_client import RespectfulClient
from common.job_queue import JobQueue
from scrapers.base import BaseScraper

BASE = "https://kararlarbilgibankasi.anayasa.gov.tr"
SEARCH = f"{BASE}/Ara"


class AymScraper(BaseScraper):
    source_name = "aym"

    def __init__(self, root: str | Path = "data",
                 keywords_path: str | Path = "queries/keywords.yaml"):
        super().__init__(root)
        kw = yaml.safe_load(Path(keywords_path).read_text(encoding="utf-8"))
        self.keywords = kw["primary"]
        self.queue = JobQueue(self.output_root / "queue.db")

    async def discover(self) -> Iterable[dict]:
        async with RespectfulClient(min_delay=2.0, max_delay=4.0) as client:
            for keyword in self.keywords:
                page = 1
                while True:
                    try:
                        r = await client.get(SEARCH, params={
                            "AranacakIfade": keyword,
                            "AranacakYer": "TUM",
                            "Page": page,
                        })
                    except Exception as e:
                        print(f"[AYM] arama hatası ({keyword}@{page}): {e}", file=sys.stderr)
                        break

                    tree = HTMLParser(r.text)
                    cards = tree.css(".karar-listesi-item, .search-result-item, article")
                    if not cards:
                        break

                    for c in cards:
                        link = c.css_first("a[href*='/Karar/']")
                        if not link:
                            continue
                        href = link.attributes.get("href", "")
                        kid = href.rsplit("/", 1)[-1]
                        yield {
                            "id": kid,
                            "url": BASE + href if href.startswith("/") else href,
                            "title": link.text(strip=True),
                            "found_via": keyword,
                        }
                    page += 1
                    if page > 100:  # sayfa cap
                        break

    async def fetch_detail(self, item: dict) -> dict | None:
        async with RespectfulClient(min_delay=2.0, max_delay=4.0) as client:
            try:
                r = await client.get(item["url"])
            except Exception as e:
                print(f"[AYM] detay hatası ({item['id']}): {e}", file=sys.stderr)
                return None

        html = r.text
        self.write_raw(item["id"], html, ext="html")

        tree = HTMLParser(html)
        body = tree.css_first(".karar-icerik, .content, main") or tree.body
        text = normalize_text(body.text(separator="\n") if body else "")

        return {
            "id": f"aym_{item['id']}",
            "source": "aym",
            "court_chamber": "Anayasa Mahkemesi",
            "court_level": "yuksek_mahkeme",
            "case_no": extract_case_no(text),
            "decision_no": extract_decision_no(text),
            "decision_date": extract_decision_date(text),
            "subject_keywords_query": [item.get("found_via")],
            "topic_tags": detect_keywords(text, self.keywords),
            "referenced_laws": [],
            "raw_html_path": str(self.raw_dir / f"{item['id']}.html"),
            "raw_text": text,
            "cleaned_text": text,
            "anonymization_check": audit(text),
            "scraped_at": self._now(),
            "scraper_version": self.scraper_version,
            "source_url": item["url"],
            "language": "tr",
            "char_count": len(text),
        }

    async def run(self, max_items: int = 1000):
        async for item in self.discover():
            self.queue.add(f"aym_{item['id']}", "aym", item)

        processed = 0
        while processed < max_items:
            batch = self.queue.claim_batch("aym", n=5)
            if not batch:
                break
            for job in batch:
                rec = await self.fetch_detail(job["payload"])
                if rec:
                    self.append_cleaned(rec)
                    self.queue.mark_done(job["id"])
                    processed += 1
                else:
                    self.queue.mark_failed(job["id"], "no detail")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--max", type=int, default=500)
    p.add_argument("--root", default="data")
    args = p.parse_args()

    s = AymScraper(root=args.root)
    asyncio.run(s.run(max_items=args.max))
