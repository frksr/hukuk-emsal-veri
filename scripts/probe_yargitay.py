"""Yargıtay endpoint'lerini doğrulamak için keşif scripti.

Kullanım:
  1. Tarayıcıda https://karararama.yargitay.gov.tr aç
  2. F12 -> Network sekmesi
  3. "icra" araması yap, daire seç
  4. /aramalist isteğinin Request Payload'ını kopyala
  5. Bu scripti çalıştır, payload'ı uyarla
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.http_client import RespectfulClient


async def probe():
    test_payload = {
        "data": {
            "arananKelime": "icra",
            "yargitayDaireleri": ["12. Hukuk Dairesi"],
            "esasYil": "", "esasIlkSiraNo": "", "esasSonSiraNo": "",
            "kararYil": "", "kararIlkSiraNo": "", "kararSonSiraNo": "",
            "baslangicTarihi": "", "bitisTarihi": "",
            "siralama": "1", "siralamaDirection": "desc",
        },
        "draw": 1, "start": 0, "length": 5,
    }

    async with RespectfulClient() as client:
        try:
            r = await client.post(
                "https://karararama.yargitay.gov.tr/aramalist",
                json=test_payload,
            )
            print("HTTP", r.status_code)
            print("Response:")
            print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:3000])
        except Exception as e:
            print(f"Hata: {e}")


if __name__ == "__main__":
    asyncio.run(probe())
