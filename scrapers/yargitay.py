"""Yargıtay karararama scraper — cURL keşfinden doğru payload yapısıyla.

Endpoint:  POST https://karararama.yargitay.gov.tr/aramadetaylist
Schema:    {"data": {
              "arananKelime": "icra",       // string, Danıştay'dan farklı
              "hukuk": "12. Hukuk Dairesi",
              "birimYrgHukukDaire": "12. Hukuk Dairesi",
              "birimYrgKurulDaire": "",
              "birimYrgCezaDaire": "",
              "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
              "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
              "baslangicTarihi": "", "bitisTarihi": "",
              "siralama": "1", "siralamaDirection": "desc",
              "pageSize": N, "pageNumber": M
           }}

Detay endpoint:
  GET https://karararama.yargitay.gov.tr/getDokuman?id=...
  (Danıştay'la aynı pattern tahmin ediliyor — gerçek cURL ile doğrulanacak)
"""
from __future__ import annotations
import asyncio
import json
import random
import sys
from pathlib import Path
from typing import AsyncIterator

import httpx
import yaml
from selectolax.parser import HTMLParser

from common.normalize import (
    normalize_text, extract_case_no, extract_decision_no,
    extract_decision_date, detect_keywords, tr_fold,
)
from common.anonymize import audit
from common.job_queue import JobQueue
from scrapers.base import BaseScraper

BASE = "https://karararama.yargitay.gov.tr"
SEARCH = f"{BASE}/aramadetaylist"
# Tahmin — detay cURL ile doğrulanacak
DETAIL = f"{BASE}/getDokuman"

# İcra hukukunda kritik daireler
CHAMBERS = [
    "12. Hukuk Dairesi",
    "8. Hukuk Dairesi",
    "13. Hukuk Dairesi",
    "19. Hukuk Dairesi",
    "3. Hukuk Dairesi",
]

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Content-Type": "application/json; charset=UTF-8",
    "Origin": BASE,
    "Referer": f"{BASE}/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

RATE_LIMIT_PATTERNS = [
    "Erişim Sınırı Aşıldı",
    "erişiminiz geçici olarak kısıtlanmıştır",
    "yoğun istek trafiği",
    "Güvenlik politikalarımız",
]

# Search rate limiting
SEARCH_BASE_DELAY = 5.0
SEARCH_JITTER = 3.0
SEARCH_BAN_BACKOFF = 120.0   # search ban'i daha uzun bekle
SEARCH_BAN_MAX_RETRIES = 3

# Detail rate limiting
DETAIL_BASE_DELAY = 6.0
DETAIL_JITTER = 4.0
DETAIL_BAN_BACKOFF = 120.0
DETAIL_BAN_MAX_RETRIES = 3


def _build_search_payload(keyword: str, chamber: str,
                          page_size: int, page_number: int) -> dict:
    return {
        "data": {
            "arananKelime": keyword,
            "hukuk": chamber,
            "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
            "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
            "baslangicTarihi": "", "bitisTarihi": "",
            "siralama": "1", "siralamaDirection": "desc",
            "birimYrgKurulDaire": "",
            "birimYrgHukukDaire": chamber,
            "birimYrgCezaDaire": "",
            "pageSize": page_size,
            "pageNumber": page_number,
        }
    }


class YargitayScraper(BaseScraper):
    source_name = "yargitay"

    def __init__(self, root: str | Path = "data",
                 chambers: list[str] | None = None,
                 keywords_path: str | Path = "queries/keywords.yaml"):
        super().__init__(root)
        self.chambers = chambers or CHAMBERS
        kw = yaml.safe_load(Path(keywords_path).read_text(encoding="utf-8"))
        self.keywords = kw["primary"]
        self.queue = JobQueue(self.output_root / "queue.db")

    async def _fetch_session(self, client: httpx.AsyncClient):
        r = await client.get(f"{BASE}/", timeout=20.0)
        print(f"[YRG] session init: HTTP {r.status_code}, "
              f"cookies={len(client.cookies)}", file=sys.stderr)

    async def discover(self, client: httpx.AsyncClient,
                       limit: int | None = None) -> AsyncIterator[dict]:
        page_size = 50
        yielded_total = 0
        consecutive_rate_limits = 0

        for chamber in self.chambers:
            for keyword in self.keywords:
                page_number = 1
                yielded_for_query = 0
                while True:
                    payload = _build_search_payload(
                        keyword, chamber, page_size, page_number)
                    j = None
                    for attempt in range(SEARCH_BAN_MAX_RETRIES):
                        delay = SEARCH_BASE_DELAY + random.uniform(0, SEARCH_JITTER)
                        await asyncio.sleep(delay)
                        try:
                            r = await client.post(SEARCH, json=payload, timeout=30.0)
                            body = r.text
                        except Exception as e:
                            print(f"[YRG] search '{chamber}/{keyword}' p{page_number} "
                                  f"(att {attempt+1}): {e}", file=sys.stderr)
                            body = ""

                        # Rate limit kontrol — HTML sayfa dönmüşse
                        if self._is_rate_limited(body):
                            consecutive_rate_limits += 1
                            wait = SEARCH_BAN_BACKOFF * (attempt + 1)
                            print(f"[YRG] SEARCH RATE LIMIT — {wait:.0f}sn "
                                  f"bekleniyor (consecutive: {consecutive_rate_limits})",
                                  file=sys.stderr)
                            await asyncio.sleep(wait)
                            continue

                        # JSON parse dene
                        try:
                            j = json.loads(body) if body else None
                            consecutive_rate_limits = 0
                            break
                        except Exception:
                            print(f"[YRG] search JSON parse hatası "
                                  f"'{chamber}/{keyword}' p{page_number}: "
                                  f"body[:200]={body[:200]!r}", file=sys.stderr)
                            j = None
                            break

                    if j is None:
                        break  # giderildi mi giderildi, sonraki keyword'e geç

                    # Çok fazla art arda rate-limit varsa run'ı durdur
                    if consecutive_rate_limits >= 5:
                        print(f"[YRG] 5 ardışık rate-limit — durduruluyor",
                              file=sys.stderr)
                        return

                    meta = j.get("metadata") or {}
                    if meta.get("FMTY") == "ERROR":
                        err = meta.get('FMTE') or ""
                        print(f"[YRG] '{chamber}/{keyword}' API err: {err}",
                              file=sys.stderr)
                        # Captcha tetiklendiyse tüm run'ı durdur — manuel
                        # müdahale gerekli
                        if "Captcha" in err or "captcha" in err:
                            print(f"[YRG] CAPTCHA TETİKLENDİ — search durduruldu. "
                                  f"Şu an kuyrukta {self.queue.stats('yargitay')} "
                                  f"job var, detail fetch'e geçilecek.",
                                  file=sys.stderr)
                            return
                        break

                    data = j.get("data") or {}
                    rows = (data.get("data") or data.get("emsalKararList") or
                            data.get("kararList") or data.get("rows") or
                            data.get("list") or [])
                    total_records = (data.get("recordsTotal") or
                                     data.get("toplam") or
                                     data.get("totalCount") or 0)

                    if page_number == 1:
                        print(f"[YRG] '{chamber}/{keyword}': toplam "
                              f"{total_records} kayıt", file=sys.stderr)

                    if not rows:
                        break

                    for row in rows:
                        iid = (row.get("id") or row.get("kararId") or
                               row.get("dokumanId"))
                        if not iid:
                            continue
                        yield {
                            "id": str(iid),
                            "chamber": (row.get("daire") or
                                        row.get("birimAdi") or chamber),
                            "case_no": (row.get("esasNo") or row.get("esas")),
                            "decision_no": (row.get("kararNo") or row.get("karar")),
                            "decision_date": (row.get("kararTarihi") or
                                              row.get("tarih")),
                            "found_via": keyword,
                            "raw_row": row,
                        }
                        yielded_for_query += 1
                        yielded_total += 1
                        if limit and yielded_total >= limit:
                            return

                    page_number += 1
                    if len(rows) < page_size:
                        break

                print(f"[YRG] '{chamber}/{keyword}' tamam: "
                      f"{yielded_for_query} kayıt", file=sys.stderr)

    def _is_rate_limited(self, body: str) -> bool:
        if not body:
            return False
        return any(p in body for p in RATE_LIMIT_PATTERNS)

    async def fetch_detail(self, client: httpx.AsyncClient,
                            item: dict) -> dict | None:
        row = item.get("raw_row") or {}
        text = ""
        raw_response = None

        for attempt in range(DETAIL_BAN_MAX_RETRIES):
            delay = DETAIL_BASE_DELAY + random.uniform(0, DETAIL_JITTER)
            await asyncio.sleep(delay)
            try:
                r = await client.get(
                    DETAIL,
                    params={"id": item["id"],
                            "arananKelime": item.get("found_via", "")},
                    timeout=30.0,
                )
                raw_response = r.text
            except Exception as e:
                print(f"[YRG] detay {item['id']} (att {attempt+1}): {e}",
                      file=sys.stderr)
                raw_response = None

            if self._is_rate_limited(raw_response or ""):
                wait = DETAIL_BAN_BACKOFF * (attempt + 1)
                print(f"[YRG] RATE LIMIT — {wait:.0f}sn bekleniyor",
                      file=sys.stderr)
                await asyncio.sleep(wait)
                continue
            break

        if raw_response:
            ct = "json" if raw_response.lstrip().startswith("{") else "html"
            if ct == "json":
                try:
                    j = json.loads(raw_response)
                    candidate = None
                    d = j.get("data") if isinstance(j, dict) else None
                    # Yargıtay: data doğrudan string HTML. Danıştay: dict olabilir.
                    if isinstance(d, str) and len(d) > 50:
                        candidate = d
                    elif isinstance(d, dict):
                        for key in ("kararHtml", "html", "icerik",
                                    "kararIcerigi", "metin", "dokuman"):
                            v = d.get(key)
                            if v and isinstance(v, str) and len(v) > 50:
                                candidate = v
                                break
                    if candidate:
                        text = normalize_text(
                            HTMLParser(candidate).text(separator="\n")
                            if "<" in candidate else candidate
                        )
                except Exception as e:
                    print(f"[YRG] JSON parse {item['id']}: {e}", file=sys.stderr)
            else:
                text = normalize_text(HTMLParser(raw_response).text(separator="\n"))

            if text:
                self.write_raw(item["id"], raw_response, ext="html")

        return {
            "id": f"yargitay_{item['id']}",
            "source": "yargitay",
            "court_chamber": item.get("chamber"),
            "court_level": "yuksek_mahkeme",
            "case_no": item.get("case_no") or extract_case_no(text or ""),
            "decision_no": item.get("decision_no") or extract_decision_no(text or ""),
            "decision_date": item.get("decision_date") or extract_decision_date(text or ""),
            "subject_keywords_query": [item.get("found_via")],
            "topic_tags": detect_keywords(text or "", self.keywords),
            "referenced_laws": [],
            "raw_html_path": str(self.raw_dir / f"{item['id']}.html") if text else None,
            "raw_text": text,
            "cleaned_text": text,
            "anonymization_check": audit(text) if text else {"contains_pii": False, "types": []},
            "scraped_at": self._now(),
            "scraper_version": self.scraper_version,
            "source_url": f"{BASE}/?id={item['id']}",
            "language": "tr",
            "char_count": len(text),
            "metadata": {"raw_row_keys": list(row.keys())},
        }

    async def run(self, max_items: int = 1000, reset: bool = False,
                  clear: bool = False, skip_discover: bool = False):
        if clear:
            self.queue.clear_source("yargitay")
            print("[YRG] kuyruk tamamen temizlendi", file=sys.stderr)
        elif reset:
            self.queue.reset_source("yargitay")
            print("[YRG] in_progress/failed pending'e dönüldü", file=sys.stderr)

        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True,
                                      timeout=30.0) as client:
            await self._fetch_session(client)

            indexed = 0
            if skip_discover:
                print("[YRG] --skip-discover: indeks atlandı, "
                      "kuyruktaki job'lara odaklan", file=sys.stderr)
                indexed = self.queue.stats("yargitay").get("pending", 0)
            else:
                async for item in self.discover(client, limit=max_items):
                    self.queue.add(f"yrg_{item['id']}", "yargitay", item)
                    indexed += 1
                print(f"[YRG] indeks bitti: {indexed}", file=sys.stderr)
            print(f"[YRG] kuyruk: {self.queue.stats('yargitay')}", file=sys.stderr)

            processed = 0
            full_text = 0
            partial = 0
            empty_text = 0
            while processed < max_items:
                batch = self.queue.claim_batch("yargitay", n=5)
                if not batch:
                    break
                for job in batch:
                    rec = await self.fetch_detail(client, job["payload"])
                    if rec:
                        self.append_cleaned(rec)
                        cc = rec.get("char_count", 0)
                        if cc == 0:
                            empty_text += 1
                            self.queue.mark_failed(job["id"], "empty", retry=True)
                        elif cc < 500:
                            partial += 1
                            self.queue.mark_failed(job["id"], "rate-limit",
                                                    retry=True)
                        else:
                            full_text += 1
                            self.queue.mark_done(job["id"])
                        processed += 1
                    else:
                        self.queue.mark_failed(job["id"], "no detail")
                if processed % 10 == 0 and processed > 0:
                    print(f"[YRG] {processed}/{indexed} "
                          f"(tam: {full_text}, kısmi: {partial}, boş: {empty_text})",
                          file=sys.stderr)
            print(f"[YRG] tamamlandı: tam {full_text}, kısmi {partial}, "
                  f"boş {empty_text}", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--max", type=int, default=500)
    p.add_argument("--chambers", nargs="*", default=None)
    p.add_argument("--root", default="data")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--clear", action="store_true")
    p.add_argument("--skip-discover", action="store_true",
                   help="Search'i atla, sadece kuyruktaki job'ların detail'ini çek")
    args = p.parse_args()

    s = YargitayScraper(root=args.root, chambers=args.chambers)
    asyncio.run(s.run(max_items=args.max, reset=args.reset, clear=args.clear,
                       skip_discover=args.skip_discover))
