"""Danıştay karararama gerçek endpoint keşfi.

Birkaç tahmin denenecek; hangisi JSON döndürürse ona göre scraper kalibre edilir.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://karararama.danistay.gov.tr/",
    "Origin": "https://karararama.danistay.gov.tr",
}


async def probe():
    base = "https://karararama.danistay.gov.tr"
    candidates = [
        # path                          method  payload_kind
        ("/aramalist",                   "POST",  "wrapped"),
        ("/aramalist",                   "POST",  "flat"),
        ("/aramadetaylist",              "POST",  "wrapped"),
        ("/aramaListele",                "POST",  "wrapped"),
        ("/karar/karar-arama",           "POST",  "wrapped"),
        ("/api/karar/ara",               "POST",  "wrapped"),
        ("/Karar/KararSorgula",          "POST",  "flat"),
        ("/",                            "GET",   None),
    ]

    payloads = {
        "wrapped": {
            "data": {
                "arananKelime": "icra",
                "siralama": "1",
                "siralamaDirection": "desc",
            },
            "draw": 1, "start": 0, "length": 5,
        },
        "flat": {
            "arananKelime": "icra",
            "draw": 1, "start": 0, "length": 5,
        },
        None: None,
    }

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True,
                                  headers=HEADERS) as client:
        # Önce ana sayfayı çekip cookie al
        try:
            home = await client.get(base, timeout=15.0)
            print(f"[home] HTTP {home.status_code}  cookies={len(client.cookies)}")
            print(f"[home] body (ilk 300): {home.text[:300]}")
        except Exception as e:
            print(f"[home] HATA: {e}")
            return

        print(f"\n{'='*60}")
        for path, method, kind in candidates:
            url = base + path
            payload = payloads.get(kind)
            try:
                if method == "POST":
                    r = await client.post(url, json=payload, timeout=15.0)
                else:
                    r = await client.get(url, timeout=15.0)
            except Exception as e:
                print(f"[{method} {path}]  EXC: {e}")
                continue

            ct = r.headers.get("content-type", "")
            print(f"\n[{method} {path}]  HTTP {r.status_code}  {ct}")
            print(f"  Body uzunluğu: {len(r.text)}")
            if "json" in ct.lower():
                try:
                    j = r.json()
                    print(f"  JSON top-keys: {list(j.keys())[:10]}")
                    print(f"  Snippet: {json.dumps(j, ensure_ascii=False)[:400]}")
                except Exception as e:
                    print(f"  JSON parse hatası: {e}")
            else:
                snippet = r.text[:300].replace("\n", " ")
                print(f"  Body (ilk 300): {snippet}")


if __name__ == "__main__":
    asyncio.run(probe())
