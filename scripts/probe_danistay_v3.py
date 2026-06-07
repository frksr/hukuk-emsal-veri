"""Danıştay payload schema cerrahi probe — `arananKelime` kritik field tespit edildi.

V1 validation geçti ama downstream patladı, demek field var ama ek bir şey eksik.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import httpx

URL = "https://karararama.danistay.gov.tr/aramalist"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Content-Type": "application/json;charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://karararama.danistay.gov.tr/",
    "Origin": "https://karararama.danistay.gov.tr",
}


VARIANTS = [
    # V1: arananKelime tek başına
    {
        "label": "arananKelime tek + wrapped + page",
        "payload": {"data": {"arananKelime": "icra"}, "pageSize": 10, "pageNumber": 1},
    },
    # V2: arananKelime + boş diğerleri
    {
        "label": "arananKelime + tüm boş alanlar",
        "payload": {
            "data": {
                "arananKelime": "icra",
                "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
                "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
                "baslangicTarihi": "", "bitisTarihi": "",
            },
            "pageSize": 10, "pageNumber": 1,
        },
    },
    # V3: V1 başarılı bulunan formattaki gibi BİREBİR — pageNumber yerine sayfa
    {
        "label": "sayfa/sayfaBoyu (TR)",
        "payload": {
            "data": {"arananKelime": "icra"},
            "sayfa": 1, "sayfaBoyu": 10,
        },
    },
    # V4: hem en/tr field
    {
        "label": "draw/start/length wrapped",
        "payload": {
            "data": {"arananKelime": "icra",
                     "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
                     "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
                     "baslangicTarihi": "", "bitisTarihi": ""},
            "draw": 1, "start": 0, "length": 10,
        },
    },
    # V5: belki "data" sarmalı yok
    {
        "label": "Flat - just arananKelime + pagination",
        "payload": {
            "arananKelime": "icra",
            "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
            "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
            "baslangicTarihi": "", "bitisTarihi": "",
            "pageSize": 10, "pageNumber": 1,
        },
    },
    # V6: pageSize sayı değil string
    {
        "label": "pageSize/pageNumber STRING",
        "payload": {
            "data": {"arananKelime": "icra",
                     "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
                     "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
                     "baslangicTarihi": "", "bitisTarihi": ""},
            "pageSize": "10", "pageNumber": "1",
        },
    },
    # V7: birim/daire field eksikliği olabilir
    {
        "label": "arananKelime + birim alanları",
        "payload": {
            "data": {"arananKelime": "icra",
                     "birimAdi": "",
                     "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
                     "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
                     "baslangicTarihi": "", "bitisTarihi": ""},
            "pageSize": 10, "pageNumber": 1,
        },
    },
    # V8: 0-based start
    {
        "label": "pageNumber=0 (0-indexed)",
        "payload": {
            "data": {"arananKelime": "icra",
                     "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
                     "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
                     "baslangicTarihi": "", "bitisTarihi": ""},
            "pageSize": 10, "pageNumber": 0,
        },
    },
]


async def probe():
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True,
                                  headers=HEADERS) as client:
        await client.get("https://karararama.danistay.gov.tr/", timeout=15.0)
        print(f"Cookie sayısı: {len(client.cookies)}\n")

        for v in VARIANTS:
            print(f"{'='*70}")
            print(f"VARIANT: {v['label']}")
            print(f"Payload: {json.dumps(v['payload'], ensure_ascii=False)[:200]}")
            print('-'*70)
            try:
                r = await client.post(URL, json=v["payload"], timeout=15.0)
            except Exception as e:
                print(f"  EXC: {e}")
                continue

            print(f"  HTTP {r.status_code}")
            try:
                j = r.json()
                d = j.get("data")
                m = j.get("metadata", {})
                fmty = m.get("FMTY", "?")
                fmte = m.get("FMTE", "")
                print(f"  FMTY: {fmty}")
                print(f"  FMTE: {fmte[:200]}")
                if fmty != "ERROR" or d:
                    print(f"  >>> data preview:")
                    print(f"  {json.dumps(d, ensure_ascii=False)[:800]}")
                    print(f"\n  *** BU VARYANT BAŞARILI GİBİ! ***")
            except Exception as e:
                print(f"  JSON parse: {e}")
                print(f"  Body: {r.text[:300]}")
            await asyncio.sleep(1.5)


if __name__ == "__main__":
    asyncio.run(probe())
