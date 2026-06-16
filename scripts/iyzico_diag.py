"""iyzico abonelik ucu teşhisi — HAM yanıtı (HTTP kodu + gövde) yazdırır.

Çalıştır (proje kökünde, host'ta):
  python scripts/iyzico_diag.py

Amaç: "Service Unavailable" / 503 gibi durumlarda iyzico'nun gerçekte ne
döndürdüğünü görmek. HTTP kodu sorunu ayırır:
  401/imza  → auth/anahtar sorunu
  404       → yanlış endpoint
  5xx/HTML  → sandbox kesintisi veya merchant abonelik provizyonu
  200 JSON  → checkout zaten çalışıyor (uygulama tarafına bak)
"""
from __future__ import annotations
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import httpx
from services.billing import (
    _make_iyzico_auth, IYZICO_BASE_URL, get_plan_info, is_configured,
)


async def deneme(uri: str, body: dict | None, method: str = "POST"):
    body_json = json.dumps(body, separators=(",", ":")) if body is not None else ""
    headers = _make_iyzico_auth(uri, body_json)
    print(f"\n→ {method} {IYZICO_BASE_URL}{uri}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            if method == "POST":
                r = await c.post(f"{IYZICO_BASE_URL}{uri}", headers=headers, content=body_json)
            else:
                r = await c.get(f"{IYZICO_BASE_URL}{uri}", headers=headers)
        print(f"  HTTP {r.status_code}  content-type={r.headers.get('content-type')}")
        txt = r.text
        # JSON ise düzgün bas, değilse ham (ilk 1200 karakter)
        try:
            print("  JSON:", json.dumps(r.json(), ensure_ascii=False)[:1200])
        except Exception:
            print("  GÖVDE:", repr(txt[:1200]))
    except Exception as e:
        print(f"  BAĞLANTI HATASI: {type(e).__name__}: {e}")


async def main():
    print("configured:", is_configured(), "| base:", IYZICO_BASE_URL)
    plan = get_plan_info("pro_solo")
    ref = (plan or {}).get("iyzico_pricing_plan_ref", "")
    print("pro_solo pricing_plan_ref:", ref or "(BOŞ)")

    # 1) Ürün/plan listesini çek (read) — auth + erişim doğru mu hızlı test
    await deneme("/v2/subscription/products?page=1&count=10", None, method="GET")

    # 2) Asıl başarısız olan: checkout form initialize
    body = {
        "locale": "tr",
        "conversationId": f"diag:{datetime.now(timezone.utc).timestamp():.0f}",
        "pricingPlanReferenceCode": ref,
        "subscriptionInitialStatus": "ACTIVE",
        "callbackUrl": "https://example.com/callback",
        "customer": {
            "name": "Test", "surname": "Kullanici",
            "email": "test@example.com",
            "gsmNumber": "+905350000000",
            "identityNumber": "11111111111",
            "billingAddress": {
                "contactName": "Test Kullanici", "city": "İstanbul",
                "country": "Türkiye", "address": "Test adres", "zipCode": "34000",
            },
            "shippingAddress": {
                "contactName": "Test Kullanici", "city": "İstanbul",
                "country": "Türkiye", "address": "Test adres", "zipCode": "34000",
            },
        },
    }
    await deneme("/v2/subscription/checkoutform/initialize", body, method="POST")


if __name__ == "__main__":
    asyncio.run(main())
