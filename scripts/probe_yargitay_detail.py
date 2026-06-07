"""Yargıtay detay endpoint'inin ham yanıtını incele.

1. Session init
2. Arama yap, bir geçerli id al
3. /getDokuman?id=... GET et
4. Ham yanıtı yazdır (ilk 2000 karakter) ve disk'e kaydet
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import httpx

BASE = "https://karararama.yargitay.gov.tr"
HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Content-Type": "application/json; charset=UTF-8",
    "Origin": BASE,
    "Referer": f"{BASE}/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0",
    "X-Requested-With": "XMLHttpRequest",
}


async def main():
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True,
                                  timeout=30.0) as client:
        # 1) Session
        r = await client.get(f"{BASE}/", timeout=20.0)
        print(f"[home] HTTP {r.status_code}, cookies={len(client.cookies)}")

        # 2) Arama
        await asyncio.sleep(2)
        search_payload = {
            "data": {
                "arananKelime": "icra",
                "hukuk": "12. Hukuk Dairesi",
                "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
                "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
                "baslangicTarihi": "", "bitisTarihi": "",
                "siralama": "1", "siralamaDirection": "desc",
                "birimYrgKurulDaire": "",
                "birimYrgHukukDaire": "12. Hukuk Dairesi",
                "birimYrgCezaDaire": "",
                "pageSize": 5, "pageNumber": 1,
            }
        }
        r = await client.post(f"{BASE}/aramadetaylist", json=search_payload)
        sj = r.json()
        print(f"[search] FMTY: {(sj.get('metadata') or {}).get('FMTY')}")
        data = sj.get("data") or {}
        rows = (data.get("data") or data.get("emsalKararList") or
                data.get("kararList") or [])
        print(f"[search] data keys: {list(data.keys())}")
        if not rows:
            print("[search] rows boş, ham response:")
            print(json.dumps(sj, ensure_ascii=False, indent=2)[:2000])
            return

        print(f"[search] {len(rows)} kayıt geldi")
        first = rows[0]
        print(f"[search] ilk row keys: {list(first.keys())}")
        print(f"[search] ilk row preview: "
              f"{json.dumps(first, ensure_ascii=False)[:500]}")

        item_id = (first.get("id") or first.get("kararId") or
                   first.get("dokumanId"))
        print(f"[search] kullanılacak id: {item_id}")

        # 3) Detay
        await asyncio.sleep(3)
        detail_url = f"{BASE}/getDokuman"
        r = await client.get(detail_url, params={"id": item_id})
        print(f"\n[detail] HTTP {r.status_code}")
        print(f"[detail] Content-Type: {r.headers.get('content-type')}")
        print(f"[detail] body uzunluğu: {len(r.text)}")

        # Kaydet
        out = Path(__file__).resolve().parent.parent / "data" / "raw" / "yargitay" / f"probe_{item_id}.raw"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(r.text, encoding="utf-8")
        print(f"[detail] kaydedildi: {out}")

        # Ham yanıt — ilk 2000 karakter
        print(f"\n[detail] body (ilk 2000):")
        print("-" * 60)
        print(r.text[:2000])
        print("-" * 60)

        # JSON mu?
        if r.text.lstrip().startswith("{"):
            try:
                j = r.json()
                print(f"\n[detail] JSON top-keys: {list(j.keys())}")
                d = j.get("data")
                if isinstance(d, dict):
                    print(f"[detail] data sub-keys: {list(d.keys())}")
                    for k, v in d.items():
                        if isinstance(v, str):
                            print(f"  {k}: {v[:200]!r}")
                        else:
                            print(f"  {k}: {type(v).__name__} = {v}")
            except Exception as e:
                print(f"[detail] JSON parse hatası: {e}")


if __name__ == "__main__":
    asyncio.run(main())
