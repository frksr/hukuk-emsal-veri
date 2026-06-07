"""HUDOC (AİHM) scraper — Türkiye aleyhine kararlar.

Strateji (probe + ampirik gözleme göre):
 - HUDOC kompleks Lucene AND query'lerinde 404 veriyor
 - `respondent:"TUR"` tek başına çalışır → 27K+ Türk kararı
 - docname konuyu içermiyor (sadece "CASE OF X v. TÜRKİYE")
 - Asıl filtre `article` alanı: Madde 6 (adil yargılanma) + P1-1 (mülkiyet)
   icra/tahsilat/ihtar davalarının büyük çoğunluğunu kapsar
 - Detay fetch sonrası ek post-filter: tam metinde keyword

Mode seçenekleri:
 --prefilter article  (default) — Madde 6 / P1-1 / 13 olanları al
 --prefilter docname  — docname'de keyword arar (genelde başarısız)
 --prefilter none     — her şeyi çek, sadece post-filter
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator

import httpx
from selectolax.parser import HTMLParser

from common.normalize import (
    normalize_text, extract_case_no, extract_decision_no,
    extract_decision_date, detect_keywords, tr_fold,
)
from common.anonymize import audit
from common.http_client import RespectfulClient
from scrapers.base import BaseScraper

BASE = "https://hudoc.echr.coe.int"
API = f"{BASE}/app/query/results"
DETAIL = f"{BASE}/app/conversion/docx/html/body"

TOPIC_KEYWORDS = [
    "execution", "enforcement", "debt", "bailiff", "judicial sale",
    "non-enforcement", "writ", "seizure", "attachment",
    "icra", "tahsilat", "ihtar", "haciz", "ödeme emri", "ihtarname",
]

# İcra/tahsilat davaları için en yaygın ECHR madde tag'leri
# 6 = adil yargılanma süresi (icra gecikmeleri burada)
# P1-1 = mülkiyet hakkı (haciz, müsadere)
# 13 = etkili başvuru hakkı (icra hatalarına itiraz)
RELEVANT_ARTICLES = {"6", "P1-1", "13", "6-1", "P1", "1-of-protocol-no-1"}

HUDOC_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    "Referer": "https://hudoc.echr.coe.int/",
}


def _article_matches(article_field: str | None) -> bool:
    """`article` alanı ';' veya ',' ile ayrılmış maddeler; ilgili olanı içeriyor mu?"""
    if not article_field:
        return False
    parts = [p.strip() for p in article_field.replace(",", ";").split(";") if p.strip()]
    return any(p in RELEVANT_ARTICLES or
               p.startswith("6-") or
               p.startswith("P1-") for p in parts)


class HudocScraper(BaseScraper):
    source_name = "hudoc"

    def __init__(self, root: str | Path = "data", limit: int = 30000,
                 verbose: bool = True, prefilter: str = "article"):
        super().__init__(root)
        self.limit = limit
        self.verbose = verbose
        self.prefilter = prefilter  # 'article', 'docname', 'none'
        self._folded_keywords = [tr_fold(k) for k in TOPIC_KEYWORDS]

    def _docname_matches(self, docname: str) -> bool:
        if not docname:
            return False
        folded = tr_fold(docname)
        return any(k in folded for k in self._folded_keywords)

    def _accept(self, cols: dict) -> bool:
        if self.prefilter == "none":
            return True
        if self.prefilter == "docname":
            return self._docname_matches(cols.get("docname") or "")
        if self.prefilter == "article":
            return _article_matches(cols.get("article"))
        return True

    async def discover(self) -> AsyncIterator[dict]:
        page_size = 100
        start = 0
        seen_ids: set[str] = set()
        yielded = 0
        total_scanned = 0

        async with RespectfulClient(min_delay=1.0, max_delay=2.5) as client:
            while yielded < self.limit:
                params = {
                    "query": 'respondent:"TUR"',
                    "select": ("itemid,appno,docname,judgementdate,kpdate,"
                               "doctypebranch,documentcollectionid,article,"
                               "importance,respondent,languagenumber,ecli,"
                               "conclusion"),
                    "sort": "kpdate Descending",
                    "start": start,
                    "length": page_size,
                }
                try:
                    r = await client.get(API, params=params, headers=HUDOC_HEADERS)
                    data = r.json()
                except Exception as e:
                    print(f"[HUDOC] sayfa @ {start}: {e}", file=sys.stderr)
                    break

                total = data.get("resultcount") or 0
                results = data.get("results") or []

                if self.verbose and start == 0:
                    print(f"[HUDOC] toplam Türk kararı: {total}, "
                          f"prefilter mode: {self.prefilter}", file=sys.stderr)

                if not results:
                    break

                page_relevant = 0
                for it in results:
                    cols = it.get("columns") or {}
                    item_id = cols.get("itemid")
                    total_scanned += 1
                    if not item_id or item_id in seen_ids:
                        continue
                    if not self._accept(cols):
                        continue

                    seen_ids.add(item_id)
                    page_relevant += 1
                    yield {
                        "itemid": item_id,
                        "appno": cols.get("appno"),
                        "docname": cols.get("docname"),
                        "judgementdate": cols.get("judgementdate") or cols.get("kpdate"),
                        "doctype": cols.get("doctypebranch"),
                        "importance": cols.get("importance"),
                        "ecli": cols.get("ecli"),
                        "article": cols.get("article"),
                        "conclusion": cols.get("conclusion"),
                        "respondent": cols.get("respondent"),
                    }
                    yielded += 1
                    if yielded >= self.limit:
                        return

                if self.verbose:
                    print(f"[HUDOC] sayfa @ {start}: {len(results)} sonuç, "
                          f"{page_relevant} ilgili (toplam: {yielded}/{total_scanned})",
                          file=sys.stderr)

                start += page_size
                if start >= int(total):
                    break

    async def fetch_detail(self, item: dict) -> dict | None:
        item_id = item.get("itemid")
        if not item_id:
            return None

        async with RespectfulClient(min_delay=1.5, max_delay=3.0) as client:
            try:
                r = await client.get(
                    DETAIL,
                    params={"library": "ECHR", "id": item_id},
                    headers=HUDOC_HEADERS,
                )
                html = r.text
            except Exception as e:
                print(f"[HUDOC] detay ({item_id}): {e}", file=sys.stderr)
                return None

        if not html or len(html) < 200:
            return None

        self.write_raw(item_id, html, ext="html")
        tree = HTMLParser(html)
        body = tree.body
        text = normalize_text(body.text(separator="\n") if body else "")

        topic_tags = detect_keywords(text, TOPIC_KEYWORDS)

        return {
            "id": f"hudoc_{item_id}",
            "source": "hudoc",
            "court_chamber": item.get("doctype"),
            "court_level": "international",
            "case_no": item.get("appno"),
            "decision_no": item.get("ecli"),
            "decision_date": item.get("judgementdate"),
            "docname": item.get("docname"),
            "subject_keywords_query": ["respondent:TUR"],
            "topic_tags": topic_tags,
            "is_topic_relevant": bool(topic_tags),
            "referenced_laws": [a.strip() for a in (item.get("article") or "").split(";") if a.strip()],
            "raw_html_path": str(self.raw_dir / f"{item_id}.html"),
            "raw_text": text,
            "cleaned_text": text,
            "anonymization_check": audit(text),
            "scraped_at": self._now(),
            "scraper_version": self.scraper_version,
            "source_url": f"{BASE}/eng?i={item_id}",
            "language": "en",
            "char_count": len(text),
            "metadata": {
                "importance": item.get("importance"),
                "doctype": item.get("doctype"),
                "conclusion": item.get("conclusion"),
            },
        }

    async def run(self):
        index = []
        async for item in self.discover():
            index.append(item)
        print(f"[HUDOC] indeks tamamlandı: {len(index)} karar", file=sys.stderr)

        if not index:
            print("[HUDOC] hiç sonuç yok. --prefilter none deneyebilirsin.",
                  file=sys.stderr)
            return

        saved = 0
        with_topic = 0
        for i, item in enumerate(index):
            rec = await self.fetch_detail(item)
            if rec:
                self.append_cleaned(rec)
                saved += 1
                if rec.get("is_topic_relevant"):
                    with_topic += 1
            if (i + 1) % 25 == 0:
                print(f"[HUDOC] detay {i+1}/{len(index)} "
                      f"(saved: {saved}, topic-relevant: {with_topic})",
                      file=sys.stderr)
        print(f"[HUDOC] tamamlandı: {saved} kayıt, {with_topic} tanesi "
              f"icra/tahsilat/ihtar içeriyor", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--root", default="data")
    p.add_argument("--prefilter", choices=["article", "docname", "none"],
                   default="article",
                   help="Filtre stratejisi: article (default) = Madde 6/P1-1/13; "
                        "docname = başlıkta keyword; none = filtre yok")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    s = HudocScraper(
        root=args.root, limit=args.limit,
        verbose=not args.quiet, prefilter=args.prefilter,
    )
    asyncio.run(s.run())
