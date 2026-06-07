"""Danıştay karararama scraper — cURL keşfinden doğru payload yapısıyla.

Endpoint:  POST https://karararama.danistay.gov.tr/aramalist
Schema:    {"data": {
              "andKelimeler": ["\"icra\""],   // liste, her terim tırnak içinde
              "orKelimeler": [],
              "notAndKelimeler": [],
              "notOrKelimeler": [],
              "pageSize": N, "pageNumber": M  // data'nın İÇİNDE
           }}

Detay endpoint: muhtemelen /aramadetaylist veya /getDokumanIcerik — onu da
ayrıca probe etmek gerekirse curl_to_config ile keşfedilebilir.
"""
from __future__ import annotations
import asyncio
import json
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
from common.http_client import RespectfulClient
from common.job_queue import JobQueue
from scrapers.base import BaseScraper

BASE = "https://karararama.danistay.gov.tr"
SEARCH = f"{BASE}/aramalist"
DETAIL = f"{BASE}/getDokuman"  # GET, query params: id, arananKelime

# Rate limit göstergeleri — bu pattern'lar görünürse sistem geçici ban'ladı
RATE_LIMIT_PATTERNS = [
    "Erişim Sınırı Aşıldı",
    "erişiminiz geçici olarak kısıtlanmıştır",
    "yoğun istek trafiği",
    "Güvenlik politikalarımız",
]

# Search rate config
SEARCH_BASE_DELAY = 5.0
SEARCH_JITTER = 3.0
SEARCH_BAN_BACKOFF = 120.0
SEARCH_BAN_MAX_RETRIES = 3

# Detay endpoint için rate config — Danıştay sıkı: 20 req/dk civarı sınır
DETAIL_BASE_DELAY = 6.0      # baz bekleme (saniye)
DETAIL_JITTER = 4.0          # 0-4sn rastgele ek
DETAIL_BAN_BACKOFF = 120.0   # ban tespit edilirse beklenecek saniye
DETAIL_BAN_MAX_RETRIES = 3   # bir job için kaç kez retry

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


def _build_payload(keyword: str, page_size: int, page_number: int) -> dict:
    """Danıştay'ın beklediği payload — keyword tırnak içinde liste elemanı."""
    return {
        "data": {
            "andKelimeler": [f'"{keyword}"'],
            "orKelimeler": [],
            "notAndKelimeler": [],
            "notOrKelimeler": [],
            "pageSize": page_size,
            "pageNumber": page_number,
        }
    }


class DanistayScraper(BaseScraper):
    source_name = "danistay"

    def __init__(self, root: str | Path = "data",
                 keywords_path: str | Path = "queries/keywords.yaml",
                 keywords: list[str] | None = None):
        super().__init__(root)
        if keywords is not None:
            self.keywords = keywords
        else:
            kw = yaml.safe_load(Path(keywords_path).read_text(encoding="utf-8"))
            self.keywords = (kw["primary"] +
                             ["amme alacağı", "vergi tahsilatı", "6183 sayılı"])
        self.queue = JobQueue(self.output_root / "queue.db")

    async def _fetch_session(self, client: httpx.AsyncClient):
        """Anasayfayı çek, JSESSIONID + TS* cookie'lerini al."""
        r = await client.get(f"{BASE}/", timeout=20.0)
        print(f"[DAN] session init: HTTP {r.status_code}, "
              f"cookies={len(client.cookies)}", file=sys.stderr)

    async def discover(self, client: httpx.AsyncClient,
                       limit: int | None = None) -> AsyncIterator[dict]:
        page_size = 50
        yielded_total = 0

        if True:  # client dışarıdan geliyor — session zaten init'li
            import random
            consecutive_rate_limits = 0
            for keyword in self.keywords:
                page_number = 1
                total_pages = None
                yielded_for_kw = 0

                while True:
                    payload = _build_payload(keyword, page_size, page_number)
                    j = None
                    for attempt in range(SEARCH_BAN_MAX_RETRIES):
                        delay = SEARCH_BASE_DELAY + random.uniform(0, SEARCH_JITTER)
                        await asyncio.sleep(delay)
                        try:
                            r = await client.post(SEARCH, json=payload, timeout=30.0)
                            body = r.text
                        except Exception as e:
                            print(f"[DAN] search '{keyword}' p{page_number} "
                                  f"(att {attempt+1}): {e}", file=sys.stderr)
                            body = ""

                        if self._is_rate_limited(body):
                            consecutive_rate_limits += 1
                            wait = SEARCH_BAN_BACKOFF * (attempt + 1)
                            print(f"[DAN] SEARCH RATE LIMIT — {wait:.0f}sn bekleniyor",
                                  file=sys.stderr)
                            await asyncio.sleep(wait)
                            continue
                        try:
                            j = json.loads(body) if body else None
                            consecutive_rate_limits = 0
                            break
                        except Exception:
                            print(f"[DAN] search JSON parse hatası "
                                  f"'{keyword}' p{page_number}: "
                                  f"body[:200]={body[:200]!r}", file=sys.stderr)
                            j = None
                            break
                    if j is None:
                        break
                    if consecutive_rate_limits >= 5:
                        print("[DAN] 5 ardışık rate-limit — durduruluyor",
                              file=sys.stderr)
                        return

                    meta = j.get("metadata") or {}
                    if meta.get("FMTY") == "ERROR":
                        err = meta.get('FMTE') or ""
                        print(f"[DAN] '{keyword}' p{page_number} API err: {err}",
                              file=sys.stderr)
                        if "Captcha" in err or "captcha" in err:
                            print(f"[DAN] CAPTCHA TETİKLENDİ — search durduruldu. "
                                  f"Detail fetch'e geçilecek.", file=sys.stderr)
                            return
                        break

                    data = j.get("data") or {}
                    # Schema tahminleri — gerçek alan isimlerini çıktıdan
                    # doğrulayacağız
                    rows = (data.get("data") or data.get("emsalKararList") or
                            data.get("kararList") or data.get("rows") or
                            data.get("list") or [])
                    total_records = (data.get("recordsTotal") or
                                     data.get("toplam") or
                                     data.get("totalCount") or 0)

                    if page_number == 1:
                        total_pages = -(-int(total_records) // page_size) if total_records else None
                        print(f"[DAN] '{keyword}': toplam {total_records} kayıt",
                              file=sys.stderr)

                    if not rows:
                        break

                    for row in rows:
                        iid = (row.get("id") or row.get("kararId") or
                               row.get("dokumanId") or row.get("itemId"))
                        if not iid:
                            continue
                        yield {
                            "id": str(iid),
                            "chamber": (row.get("daireKurul") or
                                        row.get("birimAdi") or
                                        row.get("daire") or
                                        row.get("birim")),
                            "case_no": (row.get("esasNo") or
                                        row.get("esas")),
                            "decision_no": (row.get("kararNo") or
                                            row.get("karar")),
                            "decision_date": (row.get("kararTarihi") or
                                              row.get("tarih")),
                            "found_via": keyword,
                            "raw_row": row,
                        }
                        yielded_for_kw += 1
                        yielded_total += 1
                        if limit and yielded_total >= limit:
                            print(f"[DAN] indeks limit ({limit}) ulaşıldı",
                                  file=sys.stderr)
                            return

                    page_number += 1
                    if total_pages and page_number > total_pages:
                        break
                    if len(rows) < page_size:
                        break

                print(f"[DAN] '{keyword}' tamam: {yielded_for_kw} kayıt indekslendi",
                      file=sys.stderr)

    def _is_rate_limited(self, body: str) -> bool:
        if not body:
            return False
        return any(p in body for p in RATE_LIMIT_PATTERNS)

    async def fetch_detail(self, client: httpx.AsyncClient,
                            item: dict) -> dict | None:
        """Detay endpoint: GET /getDokuman?id=...&arananKelime=...
        Rate-limit tespit edilirse N kez backoff ile retry."""
        import random
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
                print(f"[DAN] detay {item['id']} (att {attempt+1}): {e}",
                      file=sys.stderr)
                raw_response = None

            if self._is_rate_limited(raw_response or ""):
                wait = DETAIL_BAN_BACKOFF * (attempt + 1)
                print(f"[DAN] RATE LIMIT TESPİT — {wait:.0f}sn bekleniyor "
                      f"(retry {attempt+1}/{DETAIL_BAN_MAX_RETRIES})",
                      file=sys.stderr)
                await asyncio.sleep(wait)
                continue  # retry
            break  # başarılı veya kalıcı hata

        if raw_response:
            ct = "json" if raw_response.lstrip().startswith("{") else "html"
            if ct == "json":
                try:
                    j = json.loads(raw_response)
                    candidate = None
                    d = j.get("data") if isinstance(j, dict) else None
                    # data string ise direkt kullan, dict ise içinden key seç
                    if isinstance(d, str) and len(d) > 50:
                        candidate = d
                    elif isinstance(d, dict):
                        for key in ("kararHtml", "html", "icerik", "kararIcerigi",
                                    "metin", "dokuman"):
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
                    print(f"[DAN] detay JSON parse {item['id']}: {e}",
                          file=sys.stderr)
            else:
                text = normalize_text(HTMLParser(raw_response).text(separator="\n"))

            if text:
                self.write_raw(item["id"], raw_response, ext="html")

        return {
            "id": f"danistay_{item['id']}",
            "source": "danistay",
            "court_chamber": item.get("chamber"),
            "court_level": "yuksek_mahkeme",
            "case_no": item.get("case_no") or extract_case_no(text or ""),
            "decision_no": item.get("decision_no") or extract_decision_no(text or ""),
            "decision_date": item.get("decision_date") or extract_decision_date(text or ""),
            "subject_keywords_query": [item.get("found_via")],
            "topic_tags": detect_keywords(text or "", self.keywords),
            "referenced_laws": [],
            "raw_html_path": str(self.raw_dir / f"{item['id']}.txt") if text else None,
            "raw_text": text,
            "cleaned_text": text,
            "anonymization_check": audit(text) if text else {"contains_pii": False, "types": []},
            "scraped_at": self._now(),
            "scraper_version": self.scraper_version,
            "source_url": f"{BASE}/#karar/{item['id']}",
            "language": "tr",
            "char_count": len(text),
            "metadata": {"raw_row_keys": list(row.keys())},
        }

    async def run(self, max_items: int = 1000, reset: bool = False,
                  clear: bool = False):
        # Önceki run kalıntılarını yönet
        if clear:
            self.queue.clear_source("danistay")
            print("[DAN] kuyruk tamamen temizlendi", file=sys.stderr)
        elif reset:
            self.queue.reset_source("danistay")
            print("[DAN] in_progress/failed job'lar pending'e dönüldü",
                  file=sys.stderr)

        pre_stats = self.queue.stats("danistay")
        print(f"[DAN] kuyruk başlangıç durumu: {pre_stats}", file=sys.stderr)

        # Tek client — session, cookies tüm akış boyunca persist
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True,
                                      timeout=30.0) as client:
            await self._fetch_session(client)

            # 1) İndeksleme — max_items kadar
            indexed = 0
            async for item in self.discover(client, limit=max_items):
                self.queue.add(f"dan_{item['id']}", "danistay", item)
                indexed += 1
            print(f"[DAN] indeks bitti: {indexed} kayıt kuyruğa girdi",
                  file=sys.stderr)
            print(f"[DAN] kuyruk indeks sonrası: {self.queue.stats('danistay')}",
                  file=sys.stderr)

            # 2) Detay fetch — kuyruğu boşalt
            processed = 0
            full_text = 0       # char_count > 500
            partial = 0         # 0 < char_count <= 500 (muhtemel rate-limit veya boş karar)
            empty_text = 0      # char_count == 0
            while processed < max_items:
                batch = self.queue.claim_batch("danistay", n=5)
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
                            self.queue.mark_failed(job["id"], "short/rate-limit",
                                                    retry=True)
                        else:
                            full_text += 1
                            self.queue.mark_done(job["id"])
                        processed += 1
                    else:
                        self.queue.mark_failed(job["id"], "no detail")
                if processed % 10 == 0 and processed > 0:
                    print(f"[DAN] {processed}/{indexed} "
                          f"(tam: {full_text}, kısmi: {partial}, boş: {empty_text})",
                          file=sys.stderr)
            print(f"[DAN] tamamlandı: tam metin {full_text}, "
                  f"kısmi/rate-limit {partial}, boş {empty_text}",
                  file=sys.stderr)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--max", type=int, default=500)
    p.add_argument("--root", default="data")
    p.add_argument("--keyword", help="Sadece bu keyword için çalıştır "
                   "(birden çok: --keyword 'icra' --keyword 'haciz')",
                   action="append")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--clear", action="store_true")
    args = p.parse_args()

    s = DanistayScraper(root=args.root, keywords=args.keyword)
    asyncio.run(s.run(max_items=args.max, reset=args.reset, clear=args.clear))
