"""iyzico subscription billing servisi.

Akış:
1. Tenant Pro'ya geçmek istiyor → /api/billing/checkout POST
2. iyzico checkoutForm initialize → token + paymentPageUrl
3. Frontend kullanıcıyı iyzico ödeme sayfasına yönlendirir
4. Ödeme sonrası callback_url'e dönüş → /api/billing/callback
5. iyzico webhook (paralel) → /api/billing/webhook
6. Subscription DB'de active olur, tenant plan güncellenir

iyzico sandbox/prod:
- Sandbox: https://sandbox-api.iyzipay.com (geliştirme)
- Prod:    https://api.iyzipay.com
"""
from __future__ import annotations
import os
import json
import hashlib
import hmac
import base64
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

log = logging.getLogger("services.billing")

IYZICO_API_KEY = os.environ.get("IYZICO_API_KEY", "").strip()
IYZICO_SECRET_KEY = os.environ.get("IYZICO_SECRET_KEY", "").strip()
IYZICO_BASE_URL = os.environ.get("IYZICO_BASE_URL", "https://sandbox-api.iyzipay.com").strip().rstrip("/")
SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukcuyapayzekasi.com")
# iyzico panelinde tanımlanan webhook imza anahtarı (HMAC-SHA256). Set edilirse
# webhook'lar imza doğrulamasından geçmek zorunda kalır.
IYZICO_WEBHOOK_SECRET = os.environ.get("IYZICO_WEBHOOK_SECRET", "")

# Plan tier → iyzico pricing plan referansı (admin tarafından iyzico panelinde set edilir)
PLAN_PRICING: dict[str, dict] = {
    "pro_solo": {
        "name": "Pro Solo",
        "amount": Decimal("499.00"),
        "currency": "TRY",
        "iyzico_pricing_plan_ref": os.environ.get("IYZICO_PLAN_PRO_SOLO", ""),
    },
    "pro_solo_uyap": {
        "name": "Pro + UYAP",
        "amount": Decimal("799.00"),
        "currency": "TRY",
        "iyzico_pricing_plan_ref": os.environ.get("IYZICO_PLAN_PRO_UYAP", ""),
    },
    "team": {
        "name": "Team",
        "amount": Decimal("1499.00"),
        "currency": "TRY",
        "iyzico_pricing_plan_ref": os.environ.get("IYZICO_PLAN_TEAM", ""),
    },
    "team_uyap": {
        "name": "Team + UYAP",
        "amount": Decimal("1999.00"),
        "currency": "TRY",
        "iyzico_pricing_plan_ref": os.environ.get("IYZICO_PLAN_TEAM_UYAP", ""),
    },
}


def is_configured() -> bool:
    return bool(IYZICO_API_KEY and IYZICO_SECRET_KEY)


def get_plan_info(plan_tier: str) -> Optional[dict]:
    return PLAN_PRICING.get(plan_tier)


def _make_iyzico_auth(uri: str, body: str | None) -> dict[str, str]:
    """iyzico v2 HMAC-SHA256 imzalama."""
    # randomKey özel karakter (+ / =) İÇERMEMELİ — iyzico header'dan yeniden
    # okuyup imzayı doğruluyor; base64 özel karakterleri bozulup imza tutmuyordu.
    # Resmi SDK gibi salt alfanümerik (hex) bir değer kullan.
    rand_str = os.urandom(16).hex()
    payload = rand_str + uri + (body or "")
    signature = hmac.new(
        IYZICO_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    auth_str = (
        f"apiKey:{IYZICO_API_KEY}&randomKey:{rand_str}"
        f"&signature:{signature}"
    )
    return {
        "Authorization": f"IYZWSv2 {base64.b64encode(auth_str.encode()).decode()}",
        "x-iyzi-rnd": rand_str,
        "Content-Type": "application/json",
    }


async def _post(uri: str, body: dict) -> dict:
    """iyzico API'sine async POST.

    Aralıklı DNS/bağlantı hatalarına (örn. flaky router DNS → getaddrinfo failed)
    karşı dayanıklı: ConnectError/timeout durumunda artan beklemeyle yeniden dener.
    """
    import asyncio
    import httpx
    body_json = json.dumps(body, separators=(",", ":"))
    headers = _make_iyzico_auth(uri, body_json)
    max_attempts = 5
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{IYZICO_BASE_URL}{uri}", headers=headers, content=body_json,
                )
            # JSON ise normal sonuç. iyzico bazen 5xx'te HTML "Service Unavailable"
            # sayfası döner → ham HTML'i kullanıcıya yansıtma; geçiciyse yeniden dene.
            try:
                return r.json()
            except Exception:
                if r.status_code >= 500 and attempt < max_attempts:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                print(f"[IYZICO] JSON olmayan yanıt ({r.status_code}) {uri}: {r.text[:300]!r}")
                return {
                    "status": "failure",
                    "errorMessage": "Ödeme servisine şu an ulaşılamıyor. Lütfen birazdan tekrar deneyin.",
                }
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            last_exc = e
            if attempt < max_attempts:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))  # 0.5,1,2,4 sn
                continue
    return {"status": "failure", "errorMessage": f"Ödeme servisine bağlanılamadı. Lütfen birazdan tekrar deneyin. ({last_exc})"}


async def _get(uri: str) -> dict:
    """iyzico API'sine async GET (imza boş body ile hesaplanır)."""
    import asyncio
    import httpx
    headers = _make_iyzico_auth(uri, "")
    max_attempts = 5
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(f"{IYZICO_BASE_URL}{uri}", headers=headers)
            try:
                return r.json()
            except Exception:
                return {"status": "failure", "errorMessage": r.text[:500]}
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            last_exc = e
            if attempt < max_attempts:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                continue
    return {"status": "failure", "errorMessage": f"Bağlantı hatası ({max_attempts} deneme): {last_exc}"}


async def create_subscription_checkout(
    tenant_id: str,
    user: dict,            # {name, surname, email, phone, identity_no, address}
    plan_tier: str,
    callback_url: str | None = None,
) -> dict:
    """Subscription checkout form başlat. Kullanıcı yönlendirilecek URL döner.

    Returns: {token, checkoutFormContent, paymentPageUrl, conversationId}
    """
    if not is_configured():
        # Dev fallback — mock URL
        return {
            "status": "success",
            "token": f"mock-{tenant_id}-{plan_tier}",
            "paymentPageUrl": f"{SITE_URL}/app/ayarlar/abonelik?mock=1&plan={plan_tier}",
            "checkoutFormContent": "",
            "dev_mode": True,
        }

    plan = get_plan_info(plan_tier)
    if not plan:
        raise ValueError(f"Bilinmeyen plan: {plan_tier}")
    if not plan["iyzico_pricing_plan_ref"]:
        raise RuntimeError(f"IYZICO_PLAN_{plan_tier.upper()} env eksik")

    # iyzico ödeme sonunda buraya POST yapar → route handler token'ı alıp
    # abonelik sayfasına 303 GET yönlendirir (sayfa ham POST'u işleyemez).
    cb_url = callback_url or f"{SITE_URL}/api/billing/subscription-callback"
    body = {
        "locale": "tr",
        "conversationId": f"{tenant_id}:{plan_tier}:{datetime.now(timezone.utc).timestamp():.0f}",
        "pricingPlanReferenceCode": plan["iyzico_pricing_plan_ref"],
        "subscriptionInitialStatus": "ACTIVE",
        "callbackUrl": cb_url,
        "customer": {
            "name": user.get("name", "")[:50] or "Avukat",
            "surname": user.get("surname", "")[:50] or "Hesap",
            "email": user["email"],
            "gsmNumber": user.get("phone", "+905000000000"),
            "identityNumber": user.get("identity_no", "11111111111"),
            "billingAddress": {
                "contactName": f"{user.get('name','')} {user.get('surname','')}".strip(),
                "city": user.get("city", "İstanbul"),
                "country": "Türkiye",
                "address": user.get("address", "—"),
                "zipCode": user.get("zip", "34000"),
            },
            "shippingAddress": {
                "contactName": f"{user.get('name','')} {user.get('surname','')}".strip(),
                "city": user.get("city", "İstanbul"),
                "country": "Türkiye",
                "address": user.get("address", "—"),
                "zipCode": user.get("zip", "34000"),
            },
        },
    }
    return await _post("/v2/subscription/checkoutform/initialize", body)


async def retrieve_checkout_result(token: str) -> dict:
    """Callback sonrası abonelik checkout sonucunu sorgula.

    Doğru uç: GET /v2/subscription/checkoutform/{token}  (POST .../auth/ecom/detail
    abonelikte 'Sistem hatası 100001' döndürüyordu — o tek-seferlik ödeme içindir).
    """
    if not is_configured():
        return {"status": "success", "dev_mode": True, "subscriptionReferenceCode": f"mock-{token}"}
    return await _get(f"/v2/subscription/checkoutform/{token}")


async def cancel_subscription(iyzico_subscription_ref: str) -> dict:
    """Subscription'ı iptal et (period sonunda biter)."""
    if not is_configured():
        return {"status": "success", "dev_mode": True}
    body = {
        "locale": "tr",
        "subscriptionReferenceCode": iyzico_subscription_ref,
    }
    return await _post("/v2/subscription/subscriptions/cancel", body)


async def retrieve_subscription(iyzico_subscription_ref: str) -> dict:
    """Subscription detayını çek."""
    if not is_configured():
        return {"status": "success", "dev_mode": True}
    body = {
        "locale": "tr",
        "subscriptionReferenceCode": iyzico_subscription_ref,
    }
    return await _post("/v2/subscription/subscriptions/detail", body)


# ===========================================================================
# Tek seferlik ödeme (ek/kredi paketleri) — iyzico CheckoutForm (non-recurring)
# ===========================================================================

async def create_addon_checkout(
    order_id: str,
    user: dict,            # {name, surname, email, phone, identity_no, address, city, zip}
    pack: dict,            # {ad, amount, ...}
    callback_url: str | None = None,
) -> dict:
    """Ek paket için tek seferlik CheckoutForm başlat.

    Returns: {status, token, paymentPageUrl, checkoutFormContent, dev_mode?}
    """
    if not is_configured():
        # Dev fallback — gerçek ödeme yok; çağıran taraf krediyi hemen yükler.
        return {
            "status": "success",
            "token": f"mock-addon-{order_id}",
            "paymentPageUrl": f"{SITE_URL}/app/ayarlar/ek-paketler?mock=1&order={order_id}",
            "checkoutFormContent": "",
            "dev_mode": True,
        }

    fiyat = f"{Decimal(str(pack['amount'])):.2f}"
    # Callback bir route handler'a gider (POST'u karşılayıp sayfaya 303 yönlendirir);
    # doğrudan sayfaya POST → Next.js "Invalid URL" hatası verir.
    cb_url = callback_url or f"{SITE_URL}/api/billing/addon-callback"
    body = {
        "locale": "tr",
        "conversationId": order_id,
        "price": fiyat,
        "paidPrice": fiyat,
        "currency": "TRY",
        "basketId": order_id,
        "paymentGroup": "PRODUCT",
        "callbackUrl": cb_url,
        "enabledInstallments": [1],
        "buyer": {
            "id": user.get("buyer_id", order_id),
            "name": user.get("name", "")[:50] or "Avukat",
            "surname": user.get("surname", "")[:50] or "Hesap",
            "email": user["email"],
            "gsmNumber": user.get("phone", "+905000000000"),
            "identityNumber": user.get("identity_no", "11111111111"),
            "registrationAddress": user.get("address", "—"),
            "city": user.get("city", "İstanbul"),
            "country": "Türkiye",
            "zipCode": user.get("zip", "34000"),
            "ip": user.get("ip", "85.34.78.112"),
        },
        "billingAddress": {
            "contactName": f"{user.get('name','')} {user.get('surname','')}".strip() or "Hesap",
            "city": user.get("city", "İstanbul"),
            "country": "Türkiye",
            "address": user.get("address", "—"),
            "zipCode": user.get("zip", "34000"),
        },
        "basketItems": [
            {
                "id": pack.get("key", "addon"),
                "name": pack.get("ad", "Ek Paket")[:120],
                "category1": "Ek Paket",
                "itemType": "VIRTUAL",
                "price": fiyat,
            }
        ],
    }
    return await _post("/payment/iyzipos/checkoutform/initialize/auth/ecom", body)


async def retrieve_addon_result(token: str) -> dict:
    """Tek seferlik ödeme sonucunu sorgula (callback sonrası)."""
    if not is_configured():
        return {"status": "success", "paymentStatus": "SUCCESS", "dev_mode": True}
    body = {"locale": "tr", "token": token}
    return await _post("/payment/iyzipos/checkoutform/auth/ecom/detail", body)


# ---------------------------------------------------------------------------
# Webhook güvenliği
# ---------------------------------------------------------------------------
def webhook_verification_enabled() -> bool:
    """İmza doğrulaması için anahtar yapılandırılmış mı?"""
    return bool(IYZICO_WEBHOOK_SECRET)


def verify_webhook_signature(raw_body: bytes, headers) -> Optional[bool]:
    """iyzico webhook imzasını HMAC-SHA256 ile doğrula.

    Dönüş:
        True  → imza geçerli
        False → imza var ama geçersiz (REDDET)
        None  → doğrulama yapılandırılmamış (IYZICO_WEBHOOK_SECRET yok) — çağıran
                tarafın re-query gibi başka bir savunmaya düşmesi gerekir.

    iyzico imza başlığını farklı sürümlerde farklı isimlerle gönderebilir; bilinen
    adayların tümü kontrol edilir. İmza, ham gövdenin HMAC-SHA256'sıdır (hex).
    """
    if not IYZICO_WEBHOOK_SECRET:
        return None

    def _h(name: str) -> str:
        try:
            return headers.get(name) or ""
        except Exception:
            return ""

    provided = (
        _h("X-IYZ-SIGNATURE-V3")
        or _h("x-iyz-signature-v3")
        or _h("X-IYZ-SIGNATURE")
        or _h("x-iyz-signature")
    ).strip().lower()
    if not provided:
        return False

    expected = hmac.new(
        IYZICO_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest().lower()
    return hmac.compare_digest(provided, expected)


# iyzico subscriptionStatus → iç durum eşlemesi
_IYZICO_STATUS_MAP = {
    "ACTIVE": "active",
    "UPGRADED": "active",
    "PENDING": "pending",
    "UNPAID": "failed",
    "CANCELED": "canceled",
    "CANCELLED": "canceled",
    "EXPIRED": "expired",
}


async def get_authoritative_subscription(iyzico_subscription_ref: str) -> dict:
    """iyzico'dan abonelik durumunu OTORİTE kaynaktan sorgula ve normalize et.

    Webhook payload'ına GÜVENMEK YERİNE bu kullanılır: webhook'u tetikleyen
    her kim olursa olsun, gerçek durum doğrudan iyzico'dan (API key/secret ile
    imzalı çağrı) okunur.

    Dönüş: {found, status, current_period_start, current_period_end, raw}
        status ∈ active|pending|failed|canceled|expired|unknown
    """
    detail = await retrieve_subscription(iyzico_subscription_ref)

    # Dev (yapılandırılmamış) — sandbox/test akışı
    if detail.get("dev_mode"):
        return {
            "found": True,
            "status": "active",
            "current_period_start": None,
            "current_period_end": None,
            "dev_mode": True,
            "raw": detail,
        }

    if detail.get("status") != "success":
        return {"found": False, "status": "unknown", "raw": detail}

    data = detail.get("data") or detail
    raw_status = str(data.get("subscriptionStatus") or "").upper()
    return {
        "found": True,
        "status": _IYZICO_STATUS_MAP.get(raw_status, "unknown"),
        "current_period_start": data.get("startDate") or data.get("currentPeriodStart"),
        "current_period_end": data.get("endDate") or data.get("currentPeriodEnd"),
        "raw": detail,
    }
