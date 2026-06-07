"""iyzico sandbox'ta 4 abonelik ürünü + pricing plan oluşturur.

Çalıştır:
  python scripts/setup_iyzico_plans.py

Çıktıdaki referans kodlarını .env dosyasına yapıştır.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from services.billing import _post


PRODUCTS = [
    {
        "key": "pro_solo",
        "name": "Pro Solo",
        "description": "Bireysel avukat — sınırsız genel araçlar",
        "productCode": "hukuk-pro-solo",
        "price": "499.00",
        "env_var": "IYZICO_PLAN_PRO_SOLO",
    },
    {
        "key": "pro_solo_uyap",
        "name": "Pro + UYAP",
        "description": "Bireysel avukat + UYAP entegrasyonu (50 dosya, 200 sorgu/ay)",
        "productCode": "hukuk-pro-uyap",
        "price": "799.00",
        "env_var": "IYZICO_PLAN_PRO_UYAP",
    },
    {
        "key": "team",
        "name": "Team",
        "description": "Hukuk bürosu — 5 kullanıcı",
        "productCode": "hukuk-team",
        "price": "1499.00",
        "env_var": "IYZICO_PLAN_TEAM",
    },
    {
        "key": "team_uyap",
        "name": "Team + UYAP",
        "description": "Hukuk bürosu + UYAP (250 dosya, 1000 sorgu/ay)",
        "productCode": "hukuk-team-uyap",
        "price": "1999.00",
        "env_var": "IYZICO_PLAN_TEAM_UYAP",
    },
]


async def list_existing_products() -> dict[str, str]:
    """Mevcut ürünleri çek — duplicate önlemek için."""
    try:
        result = await _post("/v2/subscription/products", {
            "locale": "tr",
            "page": 1, "count": 100,
        })
        items = result.get("data", {}).get("items", []) if isinstance(result.get("data"), dict) else []
        return {it.get("productCode", ""): it.get("referenceCode", "") for it in items if it.get("productCode")}
    except Exception as e:
        print(f"⚠ Mevcut ürün listesi alınamadı: {e}")
        return {}


async def create_product(name: str, description: str, product_code: str) -> str | None:
    """Tek ürün oluştur, referenceCode döndür."""
    body = {
        "locale": "tr",
        "name": name,
        "description": description,
        "productCode": product_code,
    }
    result = await _post("/v2/subscription/products", body)
    if result.get("status") != "success":
        print(f"  ✗ '{name}' oluşturma hatası: {result.get('errorMessage')}")
        return None
    return result.get("data", {}).get("referenceCode")


async def create_pricing_plan(
    product_ref: str, plan_name: str, price: str,
) -> str | None:
    """Ürüne aylık pricing plan ekle."""
    body = {
        "locale": "tr",
        "productReferenceCode": product_ref,
        "name": plan_name,
        "price": price,
        "currencyCode": "TRY",
        "paymentInterval": "MONTHLY",
        "paymentIntervalCount": 1,
        "planPaymentType": "RECURRING",
        "trialPeriodDays": 0,
    }
    result = await _post("/v2/subscription/pricing-plans", body)
    if result.get("status") != "success":
        print(f"  ✗ Pricing plan hatası: {result.get('errorMessage')}")
        return None
    return result.get("data", {}).get("referenceCode")


async def main():
    if not os.environ.get("IYZICO_API_KEY"):
        print("✗ IYZICO_API_KEY env eksik. .env dosyasını kontrol et.")
        sys.exit(1)

    print("=" * 60)
    print("  iyzico Subscription Setup")
    print("=" * 60)
    print(f"  Base URL: {os.environ.get('IYZICO_BASE_URL')}")
    print()

    # Mevcut ürünleri kontrol et
    print("→ Mevcut ürünler kontrol ediliyor...")
    existing = await list_existing_products()
    if existing:
        print(f"  {len(existing)} mevcut ürün bulundu.")

    results = {}

    for prod in PRODUCTS:
        print(f"\n→ '{prod['name']}' (₺{prod['price']}/ay)")

        # Ürün zaten varsa atla
        if prod["productCode"] in existing:
            product_ref = existing[prod["productCode"]]
            print(f"  ⊙ Ürün zaten var: {product_ref}")
        else:
            product_ref = await create_product(
                prod["name"], prod["description"], prod["productCode"],
            )
            if not product_ref:
                continue
            print(f"  ✓ Ürün oluşturuldu: {product_ref}")

        # Pricing plan oluştur (her seferinde yeni — duplicate engelleme için kontrolü
        # iyzico panelinden manuel yapmak gerekebilir)
        plan_ref = await create_pricing_plan(
            product_ref, f"{prod['name']} - Aylık", prod["price"],
        )
        if plan_ref:
            print(f"  ✓ Pricing plan: {plan_ref}")
            results[prod["env_var"]] = plan_ref

        await asyncio.sleep(0.5)  # rate limit

    # .env güncellemek için çıktı
    print("\n" + "=" * 60)
    print("  .env DOSYASINA EKLENECEK:")
    print("=" * 60)
    for env_var, ref in results.items():
        print(f"{env_var}={ref}")
    print()

    # JSON dump
    output_path = Path(__file__).parent.parent / "iyzico_plans.json"
    output_path.write_text(json.dumps(results, indent=2))
    print(f"✓ Pricing plan referansları kaydedildi: {output_path}")
    print()
    print("Sonraki adım: Yukarıdaki satırları .env dosyasındaki ilgili yerlere yapıştır.")


if __name__ == "__main__":
    asyncio.run(main())
