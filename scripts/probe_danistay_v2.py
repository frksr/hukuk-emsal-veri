"""Danıştay /aramalist payload schema keşfi — v2.

Endpoint doğru ('aramalist' JSON dönüyor), ama payload yanlış.
Adalet Bakanlığı API'lerinde yaygın field varyasyonlarını dene.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import httpx

URL = "https://karararama.danistay.gov.tr/aramalist"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Content-Type": "application/json;charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://karararama.danistay.gov.tr/",
    "Origin": "https://karararama.danistay.gov.tr",
}


# Sistematik payload varyantları
VARIANTS = [
    # 1. Adalet ortak pattern: tam tipik field set
    {
        "label": "Tam Adalet field set + wrapped + page",
        "payload": {
            "data": {
                "aranan": "icra",
                "arananKelime": "icra",
                "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
                "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
                "baslangicTarihi": "", "bitisTarihi": "",
                "siralama": "1", "siralamaDirection": "desc",
                "birimAdi": "",
            },
            "pageSize": 10, "pageNumber": 1,
        },
    },
    # 2. DataTables (DT) yapısı
    {
        "label": "DataTables - draw/start/length",
        "payload": {
            "data": {
                "aranan": "icra",
                "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
                "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
                "baslangicTarihi": "", "bitisTarihi": "",
                "birimAdi": "",
            },
            "draw": 1, "start": 0, "length": 10,
        },
    },
    # 3. Sadece arama metni
    {
        "label": "Minimum: sadece aranan",
        "payload": {"data": {"aranan": "icra"}, "pageSize": 10, "pageNumber": 1},
    },
    # 4. Flat ama tam alanlar
    {
        "label": "Flat full set",
        "payload": {
            "aranan": "icra", "arananKelime": "icra",
            "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
            "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
            "baslangicTarihi": "", "bitisTarihi": "",
            "siralama": "1", "siralamaDirection": "desc",
            "pageSize": 10, "pageNumber": 1, "birimAdi": "",
        },
    },
    # 5. UYAP tarzı
    {
        "label": "UYAP tarzı: tam field",
        "payload": {
            "data": {
                "aranan": "icra",
                "kararIcerigiAranan": "icra",
                "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
                "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
                "baslangicTarihi": "", "bitisTarihi": "",
                "birimYrgKurulId": "",
                "birimYrgHukukDaireKurulId": "",
                "birimYrgCezaDaireKurulId": "",
                "siralama": 1, "siralamaDirection": "desc",
            },
            "pageSize": 10, "pageNumber": 1,
        },
    },
    # 6. Boş data — schema öğrenmek için
    {
        "label": "Tamamen boş",
        "payload": {"data": {}},
    },
    # 7. Form-encoded format (JSON yerine)
    {
        "label": "Form-encoded (form-data)",
        "payload": None,  # özel handler
        "form": {"aranan": "icra", "pageSize": "10", "pageNumber": "1"},
    },
]


async def probe():
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True,
                                  headers=HEADERS) as client:
        # Önce homepage ile cookie/session al
        await client.get("https://karararama.danistay.gov.tr/", timeout=15.0)
        print(f"Cookie sayısı: {len(client.cookies)}\n")

        for v in VARIANTS:
            print(f"{'='*70}")
            print(f"VARIANT: {v['label']}")
            print('-'*70)
            try:
                if v.get("form"):
                    h = {**HEADERS, "Content-Type": "application/x-www-form-urlencoded"}
                    r = await client.post(URL, data=v["form"], headers=h, timeout=15.0)
                else:
                    r = await client.post(URL, json=v["payload"], timeout=15.0)
            except Exception as e:
                print(f"  EXC: {e}")
                continue

            print(f"  HTTP {r.status_code}  CT: {r.headers.get('content-type')}")
            try:
                j = r.json()
                # Sadece "data" non-null mı diye bak
                d = j.get("data")
                m = j.get("metadata", {})
                fmty = m.get("FMTY", "?")
                fmte = m.get("FMTE", "")
                print(f"  metadata.FMTY: {fmty}")
                if fmty != "ERROR":
                    print(f"  >>> BAŞARI! data preview:")
                    print(f"  {json.dumps(d, ensure_ascii=False)[:600]}")
                else:
                    print(f"  metadata.FMTE: {fmte[:150]}")
            except Exception as e:
                print(f"  JSON parse: {e}")
                print(f"  Body[:200]: {r.text[:200]}")
            await asyncio.sleep(1.5)


if __name__ == "__main__":
    asyncio.run(probe())
