"""Billing endpoints — iyzico subscription checkout + webhook."""
from __future__ import annotations
import json
import logging
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.audit import audit
from api.auth import CurrentUser, get_current_user
from api.db import db_session, service_session
from api.schemas import APIResponse
from services.billing import (
    create_subscription_checkout,
    retrieve_checkout_result,
    cancel_subscription,
    retrieve_subscription,
    create_addon_checkout,
    retrieve_addon_result,
    get_plan_info,
    PLAN_PRICING,
    verify_webhook_signature,
    webhook_verification_enabled,
    get_authoritative_subscription,
    is_configured as iyzico_is_configured,
)
from services import krediler

log = logging.getLogger("api.billing")
router = APIRouter()


async def _tenant_plani_uygula(conn, tenant_id, plan_tier: str) -> None:
    """Tenant'ın plan_tier'ını ve plana bağlı limit kolonlarını ayarlar.
    Callback/webhook/reconcile aynı mantığı kullansın diye merkezi."""
    await conn.execute(
        """UPDATE tenants SET
           plan_tier = $1::plan_tier,
           plan_started_at = COALESCE(plan_started_at, NOW()),
           max_uyap_documents = CASE
             WHEN $1 = 'pro_solo_uyap' THEN 50
             WHEN $1 = 'team_uyap' THEN 250
             WHEN $1 = 'enterprise' THEN 100000 ELSE 0 END,
           max_monthly_queries = CASE
             WHEN $1 = 'pro_solo_uyap' THEN 200
             WHEN $1 = 'team_uyap' THEN 1000
             WHEN $1 = 'enterprise' THEN 100000 ELSE 0 END,
           max_users = CASE
             WHEN $1::text LIKE 'team%' THEN 5
             WHEN $1 = 'enterprise' THEN 50 ELSE 1 END
           WHERE id = $2""",
        plan_tier, tenant_id,
    )


def _require_verified(user: CurrentUser) -> None:
    """Ödeme işlemleri için e-posta doğrulaması zorunlu (admin muaf)."""
    if getattr(user, "role", None) == "admin":
        return
    if not getattr(user, "email_verified", False):
        raise HTTPException(
            403,
            {
                "error": "email_dogrulanmadi",
                "message": (
                    "Ödeme yapabilmek için önce e-posta adresinizi doğrulayın."
                ),
                "verify_url": "/giris/dogrulama",
            },
        )


@router.get("/plans", response_model=APIResponse)
async def list_plans():
    """Mevcut planlar + fiyat bilgisi."""
    return APIResponse(ok=True, data={
        "plans": [
            {
                "key": k,
                "name": v["name"],
                "amount_try": float(v["amount"]),
                "currency": v["currency"],
            }
            for k, v in PLAN_PRICING.items()
        ],
    })


@router.get("/plan-limits", response_model=APIResponse)
async def public_plan_limits():
    """Public: her (tier, araç) için ŞU AN geçerli aylık limit. null = sınırsız.

    Admin'in 'Paketler & Limitler'den yaptığı değişiklikler buradan okunur →
    Fiyatlandırma sayfası bu uçtan beslenir (statik metin yerine dinamik).
    """
    from api.rate_limit import tool_daily_limit
    from services import app_config

    override = await app_config.get_plan_limits()
    tiers = ["free", "pro_solo", "pro_solo_uyap", "team", "team_uyap", "enterprise"]
    tools = ["arama", "dilekce", "ihtarname", "ozet", "denetim",
             "karsi_argument", "sozlesme", "kvkk"]
    limits = {
        t: {tool: tool_daily_limit(t, tool, override) for tool in tools}
        for t in tiers
    }
    return APIResponse(ok=True, data={"limits": limits})


class CheckoutReq(BaseModel):
    plan_tier: str
    # TR faturalama için ZORUNLU (iyzico gerçek kimlik/adres ister)
    identity_no: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None


def _valid_tckn(value: str | None) -> bool:
    """TC Kimlik No doğrulama (11 hane + algoritma).

    Kurallar: 11 hane, ilk hane 0 olamaz, 10. ve 11. hane checksum'ları tutmalı.
    """
    if not value or not value.isdigit() or len(value) != 11:
        return False
    d = [int(c) for c in value]
    if d[0] == 0:
        return False
    if (sum(d[0:10]) % 10) != d[10]:
        return False
    if (((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10) != d[9]:
        return False
    return True


def _normalize_phone(value: str | None) -> str | None:
    """TR cep telefonunu +90XXXXXXXXXX formatına getir; geçersizse None."""
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if digits.startswith("90") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10 and digits.startswith("5"):
        return "+90" + digits
    return None


@router.post("/checkout", response_model=APIResponse)
async def checkout(
    payload: CheckoutReq,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Subscription checkout başlat. Kullanıcı iyzico ödeme sayfasına yönlendirilir."""
    _require_verified(user)
    if not user.tenant_id:
        raise HTTPException(400, "Aktif tenant gerekli.")

    plan = get_plan_info(payload.plan_tier)
    if not plan:
        raise HTTPException(400, "Geçersiz plan.")

    # TR faturalama: iyzico TC/telefon/adres/şehir ZORUNLU.
    # Dev/mock modda (iyzico yapılandırılmamış) doğrulama esnetilir.
    phone = _normalize_phone(payload.phone)
    if iyzico_is_configured():
        if not _valid_tckn(payload.identity_no):
            raise HTTPException(400, "Geçerli bir TC Kimlik No (11 hane) gerekli.")
        if not phone:
            raise HTTPException(400, "Geçerli bir cep telefonu numarası gerekli (05XXXXXXXXX).")
        if not (payload.address and payload.address.strip()):
            raise HTTPException(400, "Fatura adresi gerekli.")
        if not (payload.city and payload.city.strip()):
            raise HTTPException(400, "Şehir gerekli.")

    # Kullanıcı ad-soyad ayırma
    full_name = (user.name or user.email.split("@")[0]).strip()
    parts = full_name.split(" ", 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else "—"

    try:
        result = await create_subscription_checkout(
            tenant_id=user.tenant_id,
            user={
                "name": first,
                "surname": last,
                "email": user.email,
                "phone": phone or "+905000000000",  # dev/mock modu (iyzico kapalı) için
                "identity_no": payload.identity_no or "11111111111",  # dev/mock modu için
                "city": (payload.city or "İstanbul").strip(),
                "address": (payload.address or "—").strip(),
                "zip": payload.zip_code or "34000",
            },
            plan_tier=payload.plan_tier,
        )
    except Exception as e:
        log.exception("iyzico checkout başarısız")
        raise HTTPException(503, f"Ödeme servisi şu an erişilemez: {e}")

    if result.get("status") != "success":
        raise HTTPException(400, result.get("errorMessage", "Checkout başarısız"))

    # Pending subscription oluştur
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        sub_id = await conn.fetchval(
            """INSERT INTO subscriptions
               (tenant_id, plan_tier, status, amount_try, currency, metadata)
               VALUES ($1, $2, 'pending', $3, 'TRY', $4::jsonb)
               RETURNING id""",
            user.tenant_id,
            payload.plan_tier,
            float(plan["amount"]),
            json.dumps({"checkout_token": result.get("token"), "conversation_id": result.get("conversationId")}),
        )

    await audit(
        action="billing.checkout_initiated",
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        request=request,
        metadata={"plan": payload.plan_tier, "subscription_id": str(sub_id)},
    )

    return APIResponse(ok=True, data={
        "subscription_id": str(sub_id),
        "payment_page_url": result.get("paymentPageUrl"),
        "checkout_form_content": result.get("checkoutFormContent"),
        "token": result.get("token"),
        "dev_mode": result.get("dev_mode", False),
    })


class CallbackReq(BaseModel):
    token: str


@router.post("/callback", response_model=APIResponse)
async def callback(
    payload: CallbackReq,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """iyzico'dan dönüş — çekout sonucunu sorgula, subscription'ı aktive et."""
    try:
        result = await retrieve_checkout_result(payload.token)
    except Exception as e:
        raise HTTPException(503, f"İyzico sorgu hatası: {e}")

    status = result.get("status")  # SADECE API sorgu durumu — ödeme durumu DEĞİL
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    iyzico_sub_ref = (
        result.get("subscriptionReferenceCode") or result.get("referenceCode")
        or data.get("subscriptionReferenceCode") or data.get("referenceCode")
    )
    iyzico_cust_ref = result.get("customerReferenceCode") or data.get("customerReferenceCode")
    sub_status = (result.get("subscriptionStatus") or data.get("subscriptionStatus") or "").upper()
    log.info(
        "iyzico callback: status=%s sub_status=%s ref=%s raw=%s",
        status, sub_status, iyzico_sub_ref, result,
    )

    # Başarı belirleme (iyzico alan adları sürüme göre değişebildiği için sağlam):
    #  - dev_mode → başarılı (mock).
    #  - subscriptionStatus geldiyse: ACTIVE/ACTIVATED → başarılı.
    #  - gelmediyse: sorgu başarılı + abonelik referansı oluşmuşsa başarılı
    #    (başarısız ödemede iyzico abonelik referansı üretmez → plan aktifleşmez).
    if result.get("dev_mode"):
        basarili = True
    elif sub_status:
        basarili = sub_status in ("ACTIVE", "ACTIVATED")
    else:
        basarili = (status == "success") and bool(iyzico_sub_ref)

    # Ayrıcalıklı işlemler (tenant plan yükseltme, ödeme kaydı) → service_session
    # (BYPASSRLS), webhook ile aynı. Sahiplik aşağıda açıkça doğrulanır.
    async with service_session() as conn:
        sub = await conn.fetchrow(
            """SELECT id, plan_tier, tenant_id, amount_try FROM subscriptions
               WHERE metadata->>'checkout_token' = $1 LIMIT 1""",
            payload.token,
        )
        if not sub:
            raise HTTPException(404, "Subscription bulunamadı.")
        # tenant_id asyncpg'den UUID nesnesi, user.tenant_id string → stringe çevirip
        # karşılaştır (aksi halde UUID != str hep True olur ve yanlış 403 verir).
        if str(sub["tenant_id"]) != str(user.tenant_id) and not result.get("dev_mode"):
            raise HTTPException(403, "Bu subscription size ait değil.")

        if basarili:
            async with conn.transaction():
                await conn.execute(
                    """UPDATE subscriptions SET
                       status = 'active',
                       iyzico_subscription_ref = $1,
                       iyzico_customer_ref = $2,
                       started_at = COALESCE(started_at, NOW()),
                       current_period_start = NOW(),
                       current_period_end = NOW() + INTERVAL '1 month',
                       updated_at = NOW()
                       WHERE id = $3""",
                    iyzico_sub_ref, iyzico_cust_ref, sub["id"],
                )
                # Ödeme kaydı — webhook gelmese de (lokal/sandbox) raporlarda görünsün.
                # Idempotent: aynı checkout token için tek satır (ON CONFLICT).
                await conn.execute(
                    """INSERT INTO payments
                       (subscription_id, tenant_id, iyzico_payment_id,
                        amount_try, currency, status, paid_at)
                       VALUES ($1, $2, $3, $4, 'TRY', 'success', NOW())
                       ON CONFLICT (iyzico_payment_id) DO NOTHING""",
                    sub["id"], sub["tenant_id"],
                    f"sub-{payload.token}",
                    float(sub["amount_try"] or 0),
                )
                await conn.execute(
                    """UPDATE tenants SET
                       plan_tier = $1::plan_tier,
                       plan_started_at = NOW(),
                       iyzico_customer_id = $2,
                       iyzico_subscription_id = $3,
                       max_uyap_documents = CASE
                         WHEN $1 = 'pro_solo_uyap' THEN 50
                         WHEN $1 = 'team_uyap' THEN 250
                         WHEN $1 = 'enterprise' THEN 100000
                         ELSE 0
                       END,
                       max_monthly_queries = CASE
                         WHEN $1 = 'pro_solo_uyap' THEN 200
                         WHEN $1 = 'team_uyap' THEN 1000
                         WHEN $1 = 'enterprise' THEN 100000
                         ELSE 0
                       END,
                       max_users = CASE
                         WHEN $1::text LIKE 'team%' THEN 5
                         WHEN $1 = 'enterprise' THEN 50
                         ELSE 1
                       END
                       WHERE id = $4""",
                    sub["plan_tier"], iyzico_cust_ref, iyzico_sub_ref, sub["tenant_id"],
                )
        else:
            # Zaten aktifleşmiş bir aboneliği, tüketilmiş token'la gelen ikinci
            # (bayat) sorgu 'failed'e ÇEVİRMESİN — yalnızca aktif değilse işaretle.
            await conn.execute(
                "UPDATE subscriptions SET status = 'failed', updated_at = NOW() "
                "WHERE id = $1 AND status <> 'active'",
                sub["id"],
            )
            # Başarısız ödeme kaydı (admin → Sistem → "başarısız ödemeler"de görünsün).
            # Idempotent: aynı checkout token için tek 'failure' satırı.
            await conn.execute(
                """INSERT INTO payments
                   (subscription_id, tenant_id, iyzico_payment_id,
                    amount_try, currency, status, failure_reason)
                   VALUES ($1, $2, $3, $4, 'TRY', 'failure', $5)
                   ON CONFLICT (iyzico_payment_id) DO NOTHING""",
                sub["id"], sub["tenant_id"], f"sub-fail-{payload.token}",
                float(sub["amount_try"] or 0),
                (result.get("errorMessage") or sub_status or "Ödeme alınamadı")[:300],
            )

    await audit(
        action=f"billing.subscription_{'activated' if basarili else 'failed'}",
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        request=request,
        success=basarili,
        metadata={"iyzico_sub_ref": iyzico_sub_ref},
    )

    return APIResponse(
        ok=basarili,
        data={"status": "active" if basarili else "failed", "subscription_id": str(sub["id"])},
        message="Aboneliğiniz aktif!" if basarili else "Ödeme onaylanamadı.",
    )


@router.post("/cancel", response_model=APIResponse)
async def cancel(request: Request, user: CurrentUser = Depends(get_current_user)):
    """Mevcut subscription'ı period sonunda iptal et."""
    if not user.tenant_id:
        raise HTTPException(400, "Aktif tenant gerekli.")

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        sub = await conn.fetchrow(
            """SELECT id, iyzico_subscription_ref FROM subscriptions
               WHERE tenant_id = $1 AND status = 'active'
               ORDER BY created_at DESC LIMIT 1""",
            user.tenant_id,
        )
        if not sub:
            raise HTTPException(404, "Aktif abonelik yok.")

        if sub["iyzico_subscription_ref"]:
            try:
                await cancel_subscription(sub["iyzico_subscription_ref"])
            except Exception as e:
                log.warning(f"iyzico cancel hatası: {e}")

        await conn.execute(
            """UPDATE subscriptions SET
               cancel_at_period_end = TRUE,
               canceled_at = NOW(),
               updated_at = NOW()
               WHERE id = $1""",
            sub["id"],
        )

    await audit(
        action="billing.subscription_canceled",
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        request=request,
    )
    return APIResponse(ok=True, message="Abonelik dönem sonunda iptal edilecek.")


@router.get("/current", response_model=APIResponse)
async def current_subscription(user: CurrentUser = Depends(get_current_user)):
    """Tenant'ın mevcut subscription bilgisi (+ kendi kendine onarım).

    Aktif abonelik varsa tenant.plan_tier ve ödeme kaydı onunla SENKRONLANIR —
    eski/eksik aktivasyonlardan kalan 'abonelik aktif ama tenant free / ödeme yok'
    tutarsızlığını giderir. Ayrıcalıklı işlem → service_session.
    """
    if not user.tenant_id:
        return APIResponse(ok=True, data=None)
    async with service_session() as conn:
        sub = await conn.fetchrow(
            """SELECT id, plan_tier, status, started_at, current_period_end,
                      cancel_at_period_end, amount_try, currency, tenant_id
               FROM subscriptions
               WHERE tenant_id = $1
               ORDER BY created_at DESC LIMIT 1""",
            user.tenant_id,
        )
        if sub and sub["status"] == "active":
            # 1) Tenant planı abonelikten farklıysa senkronla.
            tenant_plan = await conn.fetchval(
                "SELECT plan_tier FROM tenants WHERE id = $1", user.tenant_id,
            )
            if str(tenant_plan) != str(sub["plan_tier"]):
                await _tenant_plani_uygula(conn, user.tenant_id, sub["plan_tier"])
            # 2) Bu abonelik için ödeme kaydı yoksa geri-doldur (raporlarda görünsün).
            pay_var = await conn.fetchval(
                "SELECT 1 FROM payments WHERE subscription_id = $1 LIMIT 1", sub["id"],
            )
            if not pay_var and sub["amount_try"]:
                await conn.execute(
                    """INSERT INTO payments
                       (subscription_id, tenant_id, iyzico_payment_id,
                        amount_try, currency, status, paid_at)
                       VALUES ($1, $2, $3, $4, 'TRY', 'success', COALESCE($5, NOW()))
                       ON CONFLICT (iyzico_payment_id) DO NOTHING""",
                    sub["id"], sub["tenant_id"], f"sub-backfill-{sub['id']}",
                    float(sub["amount_try"] or 0), sub["started_at"],
                )
        # "Mevcut Plan" = tenant'ın GERÇEK hakkı (ödeme alınmadıysa free). Abonelik
        # kaydının plan_tier'ı (pending/failed olabilir) bunu belirlemez.
        tenant_plani = await conn.fetchval(
            "SELECT plan_tier FROM tenants WHERE id = $1", user.tenant_id,
        )
    if not sub:
        return APIResponse(ok=True, data=None)
    return APIResponse(ok=True, data={
        "id": str(sub["id"]),
        "plan": str(tenant_plani or "free"),
        "subscription_plan": sub["plan_tier"],
        "status": sub["status"],
        "started_at": sub["started_at"].isoformat() if sub["started_at"] else None,
        "period_end": sub["current_period_end"].isoformat() if sub["current_period_end"] else None,
        "cancel_at_period_end": sub["cancel_at_period_end"],
        "amount_try": float(sub["amount_try"]) if sub["amount_try"] else None,
        "currency": sub["currency"],
    })


@router.get("/invoices", response_model=APIResponse)
async def list_invoices(user: CurrentUser = Depends(get_current_user)):
    """Tenant'ın geçmiş ödemeleri. Açık tenant filtresiyle service_session
    (ödeme kayıtları RLS'e takılmadan güvenle listelenir)."""
    if not user.tenant_id:
        return APIResponse(ok=True, data={"payments": []})
    async with service_session() as conn:
        rows = await conn.fetch(
            """SELECT id, amount_try, currency, status, paid_at,
                      invoice_number, invoice_pdf_url
               FROM payments
               WHERE tenant_id = $1
               ORDER BY created_at DESC LIMIT 100""",
            user.tenant_id,
        )
    return APIResponse(ok=True, data={
        "payments": [
            {
                "id": str(r["id"]),
                "amount_try": float(r["amount_try"]),
                "currency": r["currency"],
                "status": r["status"],
                "paid_at": r["paid_at"].isoformat() if r["paid_at"] else None,
                "invoice_number": r["invoice_number"],
                "invoice_pdf_url": r["invoice_pdf_url"],
            }
            for r in rows
        ],
    })


# ===========================================================================
# Ek/kredi paketleri — tek seferlik satın alma, krediler hesaba yüklenir.
# ===========================================================================

@router.get("/addons", response_model=APIResponse)
async def list_addons():
    """Satın alınabilir ek paket kataloğu (dinamik — admin panelden düzenlenebilir)."""
    paketler = await krediler.aktif_paketler()
    return APIResponse(ok=True, data={
        "packs": [
            {
                "key": k,
                "ad": p["ad"],
                "aciklama": p["aciklama"],
                "modul": p["modul"],
                "krediler": p["krediler"],
                "amount_try": float(p["amount"]),
                "currency": "TRY",
                "bundle": p["modul"] is None,
            }
            for k, p in paketler.items()
        ],
    })


class AddonCheckoutReq(BaseModel):
    pack_key: str
    identity_no: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None


async def _kredi_yukle(conn, order_row) -> None:
    """Siparişin kredilerini hesaba yükle — eşzamanlı çağrılara karşı idempotent.

    'granted' bayrağını FALSE→TRUE'ya ATOMİK olarak çevirebilen ilk çağrı kredileri
    yükler; aynı anda gelen ikinci çağrı (çift callback / StrictMode / reconcile
    yarışı) hiçbir satır güncelleyemez ve hiçbir şey yüklemez. Böylece çift yükleme
    (ör. 100 yerine 200) önlenir."""
    claimed = await conn.fetchval(
        """UPDATE credit_orders SET status='paid', granted=TRUE, updated_at=NOW()
           WHERE id = $1 AND granted = FALSE
           RETURNING id""",
        order_row["id"],
    )
    if not claimed:
        return  # başka bir çağrı zaten yükledi → tekrar yükleme

    krediler_map = order_row["credits"]
    if isinstance(krediler_map, str):
        krediler_map = json.loads(krediler_map)
    try:
        await krediler.ekle(
            user_id=str(order_row["user_id"]),
            tenant_id=str(order_row["tenant_id"]) if order_row["tenant_id"] else None,
            krediler=krediler_map,
            reason="purchase",
            ref=str(order_row["id"]),
        )
    except Exception:
        # Yükleme başarısızsa claim'i geri al ki reconcile sonradan tekrar deneyebilsin.
        await conn.execute(
            "UPDATE credit_orders SET granted = FALSE WHERE id = $1", order_row["id"],
        )
        raise


@router.post("/addons/checkout", response_model=APIResponse)
async def addon_checkout(
    payload: AddonCheckoutReq,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Ek paket satın alma başlat. Dev modda (iyzico yok) krediler hemen yüklenir."""
    _require_verified(user)
    pack = await krediler.paket_bilgi_async(payload.pack_key)
    if not pack:
        raise HTTPException(400, "Geçersiz paket.")

    phone = _normalize_phone(payload.phone)
    if iyzico_is_configured():
        if not _valid_tckn(payload.identity_no):
            raise HTTPException(400, "Geçerli bir TC Kimlik No (11 hane) gerekli.")
        if not phone:
            raise HTTPException(400, "Geçerli bir cep telefonu numarası gerekli (05XXXXXXXXX).")
        if not (payload.address and payload.address.strip()):
            raise HTTPException(400, "Fatura adresi gerekli.")

    full_name = (user.name or user.email.split("@")[0]).strip()
    parts = full_name.split(" ", 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else "—"

    # Sipariş kaydı (pending)
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        order = await conn.fetchrow(
            """INSERT INTO credit_orders
                   (user_id, tenant_id, pack_key, amount_try, credits, status)
               VALUES ($1, $2, $3, $4, $5::jsonb, 'pending')
               RETURNING id, user_id, tenant_id, credits, granted""",
            user.user_id, user.tenant_id, payload.pack_key,
            float(pack["amount"]), json.dumps(pack["krediler"]),
        )
        order_id = str(order["id"])

    try:
        result = await create_addon_checkout(
            order_id=order_id,
            user={
                "name": first, "surname": last, "email": user.email,
                "phone": phone or "+905000000000",  # dev/mock modu için
                "identity_no": payload.identity_no or "11111111111",  # dev/mock modu için
                "city": (payload.city or "İstanbul").strip(),
                "address": (payload.address or "—").strip(),
                "zip": payload.zip_code or "34000",
                "buyer_id": str(user.user_id),
            },
            pack={**pack, "key": payload.pack_key},
        )
    except Exception as e:
        log.exception("ek paket checkout başarısız")
        raise HTTPException(503, f"Ödeme servisi şu an erişilemez: {e}")

    token = result.get("token")
    # Token'ı siparişe işle
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        await conn.execute(
            "UPDATE credit_orders SET iyzico_token=$1, updated_at=NOW() WHERE id=$2",
            token, order["id"],
        )

    # Dev/mock mod: gerçek ödeme yok → krediyi hemen yükle.
    if result.get("dev_mode"):
        async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
            fresh = await conn.fetchrow(
                "SELECT id, user_id, tenant_id, credits, granted FROM credit_orders WHERE id=$1",
                order["id"],
            )
            await _kredi_yukle(conn, fresh)
        await audit(action="billing.addon_granted_dev", user_id=user.user_id,
                    tenant_id=user.tenant_id, request=request,
                    metadata={"pack": payload.pack_key, "order": order_id})
        return APIResponse(ok=True, data={
            "order_id": order_id, "dev_mode": True, "granted": True,
        }, message="Ek paket hesabınıza tanımlandı.")

    if result.get("status") not in ("success", None):
        raise HTTPException(400, result.get("errorMessage", "Ödeme başlatılamadı."))

    await audit(action="billing.addon_checkout_initiated", user_id=user.user_id,
                tenant_id=user.tenant_id, request=request,
                metadata={"pack": payload.pack_key, "order": order_id})
    return APIResponse(ok=True, data={
        "order_id": order_id,
        "payment_page_url": result.get("paymentPageUrl"),
        "checkout_form_content": result.get("checkoutFormContent"),
        "token": token,
        "dev_mode": False,
    })


class AddonCallbackReq(BaseModel):
    token: str


@router.post("/addons/callback", response_model=APIResponse)
async def addon_callback(
    payload: AddonCallbackReq,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """iyzico dönüşü — ödeme başarılıysa kredileri yükle (idempotent)."""
    try:
        result = await retrieve_addon_result(payload.token)
    except Exception as e:
        raise HTTPException(503, f"İyzico sorgu hatası: {e}")

    basarili = (
        result.get("paymentStatus") == "SUCCESS"
        or result.get("status") == "success"
    )
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        order = await conn.fetchrow(
            """SELECT id, user_id, tenant_id, credits, granted, status
               FROM credit_orders WHERE iyzico_token=$1 LIMIT 1""",
            payload.token,
        )
        if not order:
            raise HTTPException(404, "Sipariş bulunamadı.")
        if str(order["user_id"]) != str(user.user_id):
            raise HTTPException(403, "Bu sipariş size ait değil.")

        if basarili:
            await _kredi_yukle(conn, order)
        elif order["status"] == "pending":
            await conn.execute(
                "UPDATE credit_orders SET status='failed', updated_at=NOW() WHERE id=$1",
                order["id"],
            )

    await audit(
        action=f"billing.addon_{'granted' if basarili else 'failed'}",
        user_id=user.user_id, tenant_id=user.tenant_id, request=request,
        success=basarili, metadata={"order": str(order["id"])},
    )
    return APIResponse(
        ok=basarili,
        data={"order_id": str(order["id"]), "granted": basarili},
        message="Ek paket hesabınıza tanımlandı." if basarili else "Ödeme başarısız oldu.",
    )


@router.get("/addons/orders", response_model=APIResponse)
async def addon_orders(user: CurrentUser = Depends(get_current_user)):
    """Kullanıcının ek paket satın alma kayıtları (ödeme geçmişinde göstermek için)."""
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT id, pack_key, amount_try, currency, status, created_at
               FROM credit_orders WHERE user_id = $1
               ORDER BY created_at DESC LIMIT 100""",
            user.user_id,
        )
    orders = []
    paketler = await krediler.aktif_paketler()
    for r in rows:
        pack = paketler.get(r["pack_key"])
        orders.append({
            "id": str(r["id"]),
            "pack_key": r["pack_key"],
            "ad": pack["ad"] if pack else r["pack_key"],
            "amount_try": float(r["amount_try"]),
            "currency": r["currency"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat(),
        })
    return APIResponse(ok=True, data={"orders": orders})


@router.post("/addons/reconcile", response_model=APIResponse)
async def addon_reconcile(user: CurrentUser = Depends(get_current_user)):
    """Ödenmiş ama kredisi yüklenmemiş (callback ulaşmamış) siparişleri iyzico'dan
    doğrulayıp kredileri yükler. Ek paketler sayfası açıldığında çağrılır → kaçan
    ödemeler kendiliğinden telafi edilir. Idempotent (granted flag)."""
    yuklenen = 0
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        orders = await conn.fetch(
            """SELECT id, user_id, tenant_id, credits, granted, status, iyzico_token
               FROM credit_orders
               WHERE user_id=$1 AND granted=FALSE AND iyzico_token IS NOT NULL
                 AND created_at > NOW() - INTERVAL '7 days'
               ORDER BY created_at DESC LIMIT 10""",
            user.user_id,
        )
        for o in orders:
            try:
                res = await retrieve_addon_result(o["iyzico_token"])
            except Exception:
                continue
            if res.get("paymentStatus") == "SUCCESS" or res.get("status") == "success":
                await _kredi_yukle(conn, o)
                yuklenen += 1
    return APIResponse(ok=True, data={"yuklenen": yuklenen})


# Webhook — GÜVENLİK:
#   Webhook URL'i halka açıktır; gelen payload'a ASLA körü körüne güvenilmez.
#   İki katmanlı savunma uygulanır:
#     1) İmza doğrulama: IYZICO_WEBHOOK_SECRET set ise HMAC-SHA256 imzası
#        doğrulanır; geçersizse 401 ile reddedilir.
#     2) Otorite re-query: Plan/abonelik durumunu DEĞİŞTİREN her olayda durum
#        doğrudan iyzico API'sinden (kendi API key/secret'ımızla imzalı çağrı)
#        yeniden sorgulanır. Karar payload'a değil, iyzico'nun döndürdüğü gerçek
#        duruma göre verilir. Böylece sahte SUBSCRIPTION_PAYMENT_SUCCESS /
#        SUBSCRIPTION_CANCELLED ile bedava Pro açma veya başka tenant'ı düşürme
#        engellenir. Ödeme tutarı da payload'tan DEĞİL, kendi kayıtlı
#        amount_try'dan alınır.
#   Cross-tenant güncelleme yaptığı için service_session (RLS bypass) kullanılır.
@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request):
    """iyzico webhook handler."""
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body or b"{}")
    except Exception:
        raise HTTPException(400, "JSON parse edilemedi")

    # 1) İmza doğrulama
    sig_ok = verify_webhook_signature(raw_body, request.headers)
    if sig_ok is False:
        log.warning("iyzico webhook: geçersiz imza, reddedildi.")
        raise HTTPException(401, "Geçersiz webhook imzası.")
    # sig_ok is None → imza anahtarı yapılandırılmamış; (2) re-query'ye güveniriz.

    iyzico_token = payload.get("iyziEventToken") or payload.get("token")
    event_type = payload.get("iyziEventType") or payload.get("eventType") or "unknown"
    sub_ref = payload.get("subscriptionReferenceCode")
    source_ip = request.client.host if request.client else None

    async with service_session() as conn:
        # Idempotency + olay kaydı
        exists = await conn.fetchval(
            "SELECT 1 FROM webhook_events WHERE iyzico_token = $1",
            iyzico_token,
        )
        if exists:
            return {"ok": True, "duplicate": True}

        await conn.execute(
            """INSERT INTO webhook_events
               (provider, event_type, iyzico_token, payload, signature_valid, source_ip)
               VALUES ('iyzico', $1, $2, $3::jsonb, $4, $5)""",
            event_type, iyzico_token, json.dumps(payload), sig_ok, source_ip,
        )

        state_changing = event_type in (
            "SUBSCRIPTION_PAYMENT_SUCCESS", "SUBSCRIPTION_RENEWAL",
            "SUBSCRIPTION_PAYMENT_FAILED", "SUBSCRIPTION_CANCELLED",
        )

        # 2) Otorite re-query — durum değiştiren olaylarda iyzico'ya sor.
        reconciled = False
        if sub_ref and state_changing:
            # İmza yoksa VE iyzico API'si yapılandırılmamışsa (gerçek sorgu
            # yapamıyorsak) durumu DEĞİŞTİRMEYİZ — sadece kaydederiz.
            if sig_ok is None and not iyzico_is_configured():
                await conn.execute(
                    """UPDATE webhook_events
                       SET process_error = 'unverified: no signature key & iyzico not configured'
                       WHERE iyzico_token = $1""",
                    iyzico_token,
                )
                # 200 dönülür ki iyzico tekrar denemesin; ama state değişmez.
                return {"ok": True, "applied": False, "reason": "unverified"}

            auth_state = await get_authoritative_subscription(sub_ref)
            reconciled = True

            if not auth_state.get("found"):
                await conn.execute(
                    "UPDATE webhook_events SET process_error = 'iyzico lookup failed' WHERE iyzico_token = $1",
                    iyzico_token,
                )
                return {"ok": True, "applied": False, "reason": "not_found"}

            real_status = auth_state["status"]  # iyzico'nun GERÇEK durumu

            if real_status == "active":
                await conn.execute(
                    """UPDATE subscriptions SET
                       status = 'active',
                       current_period_start = COALESCE($1::timestamptz, current_period_start),
                       current_period_end = COALESCE($2::timestamptz, current_period_end),
                       updated_at = NOW()
                       WHERE iyzico_subscription_ref = $3""",
                    auth_state.get("current_period_start"),
                    auth_state.get("current_period_end"),
                    sub_ref,
                )
                # Ödeme yeniden alındı → tenant planını abonelikteki tier'a GERİ YÜKLE.
                # (Önceki bir başarısız ödeme tenant'ı 'free'e düşürmüş olabilir;
                # yenileme başarılı olunca paket hakları geri açılır.)
                await conn.execute(
                    """UPDATE tenants t SET
                       plan_tier = s.plan_tier,
                       max_uyap_documents = CASE
                         WHEN s.plan_tier = 'pro_solo_uyap' THEN 50
                         WHEN s.plan_tier = 'team_uyap' THEN 250
                         WHEN s.plan_tier = 'enterprise' THEN 100000
                         ELSE 0 END,
                       max_monthly_queries = CASE
                         WHEN s.plan_tier = 'pro_solo_uyap' THEN 200
                         WHEN s.plan_tier = 'team_uyap' THEN 1000
                         WHEN s.plan_tier = 'enterprise' THEN 100000
                         ELSE 0 END,
                       max_users = CASE
                         WHEN s.plan_tier::text LIKE 'team%' THEN 5
                         WHEN s.plan_tier = 'enterprise' THEN 50
                         ELSE 1 END
                       FROM subscriptions s
                       WHERE s.iyzico_subscription_ref = $1 AND t.id = s.tenant_id""",
                    sub_ref,
                )
                # Payment kaydı — tutar payload'tan DEĞİL, kayıtlı amount_try'dan.
                sub_row = await conn.fetchrow(
                    "SELECT id, tenant_id, amount_try FROM subscriptions WHERE iyzico_subscription_ref = $1",
                    sub_ref,
                )
                if sub_row and event_type in ("SUBSCRIPTION_PAYMENT_SUCCESS", "SUBSCRIPTION_RENEWAL"):
                    await conn.execute(
                        """INSERT INTO payments
                           (subscription_id, tenant_id, iyzico_payment_id,
                            amount_try, currency, status, paid_at)
                           VALUES ($1, $2, $3, $4, 'TRY', 'success', NOW())
                           ON CONFLICT (iyzico_payment_id) DO NOTHING""",
                        sub_row["id"], sub_row["tenant_id"],
                        payload.get("paymentId") or iyzico_token,
                        float(sub_row["amount_try"] or 0),
                    )

            elif real_status == "failed":
                # Ödeme alınamadı → aboneliği işaretle VE tenant'ı 'free'e düşür.
                # Böylece ücretli özellikler ödeme alınana kadar kullanılamaz
                # (kota sistemi tenant.plan_tier'a göre çalışır).
                await conn.execute(
                    """UPDATE subscriptions SET status = 'failed', updated_at = NOW()
                       WHERE iyzico_subscription_ref = $1""",
                    sub_ref,
                )
                fail_row = await conn.fetchrow(
                    """SELECT tenant_id, plan_tier, amount_try
                       FROM subscriptions WHERE iyzico_subscription_ref = $1""",
                    sub_ref,
                )
                if fail_row:
                    await conn.execute(
                        """UPDATE tenants SET plan_tier = 'free',
                           max_uyap_documents = 0, max_monthly_queries = 0, max_users = 1
                           WHERE id = $1""",
                        fail_row["tenant_id"],
                    )
                    # Tenant sahibine "ödeme alınamadı" e-postası gönder.
                    owner = await conn.fetchrow(
                        """SELECT u.email, u.name
                           FROM tenant_members tm JOIN users u ON u.id = tm.user_id
                           WHERE tm.tenant_id = $1 AND tm.role = 'owner'
                           ORDER BY tm.created_at LIMIT 1""",
                        fail_row["tenant_id"],
                    )
                    if owner and owner["email"]:
                        try:
                            from services.email import send_payment_failed_email
                            await send_payment_failed_email(
                                to=owner["email"],
                                name=owner["name"],
                                plan_tier=str(fail_row["plan_tier"]),
                                amount_try=float(fail_row["amount_try"] or 0),
                            )
                        except Exception as e:
                            log.warning("payment-failed email gönderilemedi: %s", e)

            elif real_status in ("canceled", "expired"):
                await conn.execute(
                    """UPDATE subscriptions SET status = $2,
                       canceled_at = NOW(), updated_at = NOW()
                       WHERE iyzico_subscription_ref = $1""",
                    sub_ref, real_status,
                )
                sub_row = await conn.fetchrow(
                    "SELECT tenant_id FROM subscriptions WHERE iyzico_subscription_ref = $1",
                    sub_ref,
                )
                if sub_row:
                    await conn.execute(
                        "UPDATE tenants SET plan_tier = 'free' WHERE id = $1",
                        sub_row["tenant_id"],
                    )
            # real_status 'pending'/'unknown' → state değiştirmeyiz.

        await conn.execute(
            """UPDATE webhook_events
               SET processed = TRUE, processed_at = NOW(), reconciled = $2
               WHERE iyzico_token = $1""",
            iyzico_token, reconciled,
        )

    return {"ok": True}
