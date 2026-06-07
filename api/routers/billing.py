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
    get_plan_info,
    PLAN_PRICING,
    verify_webhook_signature,
    webhook_verification_enabled,
    get_authoritative_subscription,
    is_configured as iyzico_is_configured,
)

log = logging.getLogger("api.billing")
router = APIRouter()


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
    if not user.tenant_id:
        raise HTTPException(400, "Aktif tenant gerekli.")

    plan = get_plan_info(payload.plan_tier)
    if not plan:
        raise HTTPException(400, "Geçersiz plan.")

    # TR faturalama: gerçek kimlik/telefon/adres ZORUNLU (iyzico canlı modda).
    # (Eskiden sahte 11111111111 / +905000000000 gönderiliyordu — fatura geçersiz
    # olur ve KVKK/VUK açısından hatalı kayıt oluşurdu.)
    # Dev/mock modda (iyzico yapılandırılmamış) doğrulama esnetilir.
    phone = _normalize_phone(payload.phone)
    if iyzico_is_configured():
        if not _valid_tckn(payload.identity_no):
            raise HTTPException(400, "Geçerli bir TC Kimlik No (11 hane) gerekli.")
        if not phone:
            raise HTTPException(400, "Geçerli bir cep telefonu (5XXXXXXXXX) gerekli.")
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
                "phone": phone or "+905000000000",  # dev/mock fallback
                "identity_no": payload.identity_no or "11111111111",
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

    status = result.get("status")
    iyzico_sub_ref = result.get("subscriptionReferenceCode")
    iyzico_cust_ref = result.get("customerReferenceCode")

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        sub = await conn.fetchrow(
            """SELECT id, plan_tier, tenant_id FROM subscriptions
               WHERE metadata->>'checkout_token' = $1 LIMIT 1""",
            payload.token,
        )
        if not sub:
            raise HTTPException(404, "Subscription bulunamadı.")
        if sub["tenant_id"] != user.tenant_id and not result.get("dev_mode"):
            raise HTTPException(403, "Bu subscription size ait değil.")

        if status == "success":
            async with conn.transaction():
                await conn.execute(
                    """UPDATE subscriptions SET
                       status = 'active',
                       iyzico_subscription_ref = $1,
                       iyzico_customer_ref = $2,
                       started_at = NOW(),
                       updated_at = NOW()
                       WHERE id = $3""",
                    iyzico_sub_ref, iyzico_cust_ref, sub["id"],
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
                         WHEN $1 LIKE 'team%' THEN 5
                         WHEN $1 = 'enterprise' THEN 50
                         ELSE 1
                       END
                       WHERE id = $4""",
                    sub["plan_tier"], iyzico_cust_ref, iyzico_sub_ref, sub["tenant_id"],
                )
        else:
            await conn.execute(
                "UPDATE subscriptions SET status = 'failed', updated_at = NOW() WHERE id = $1",
                sub["id"],
            )

    await audit(
        action=f"billing.subscription_{'activated' if status == 'success' else 'failed'}",
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        request=request,
        success=(status == "success"),
        metadata={"iyzico_sub_ref": iyzico_sub_ref},
    )

    return APIResponse(
        ok=(status == "success"),
        data={"status": status, "subscription_id": str(sub["id"])},
        message="Aboneliğiniz aktif!" if status == "success" else "Ödeme başarısız oldu.",
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
    """Tenant'ın mevcut subscription bilgisi."""
    if not user.tenant_id:
        return APIResponse(ok=True, data=None)
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        sub = await conn.fetchrow(
            """SELECT id, plan_tier, status, started_at, current_period_end,
                      cancel_at_period_end, amount_try, currency
               FROM subscriptions
               WHERE tenant_id = $1
               ORDER BY created_at DESC LIMIT 1""",
            user.tenant_id,
        )
    if not sub:
        return APIResponse(ok=True, data=None)
    return APIResponse(ok=True, data={
        "id": str(sub["id"]),
        "plan": sub["plan_tier"],
        "status": sub["status"],
        "started_at": sub["started_at"].isoformat() if sub["started_at"] else None,
        "period_end": sub["current_period_end"].isoformat() if sub["current_period_end"] else None,
        "cancel_at_period_end": sub["cancel_at_period_end"],
        "amount_try": float(sub["amount_try"]) if sub["amount_try"] else None,
        "currency": sub["currency"],
    })


@router.get("/invoices", response_model=APIResponse)
async def list_invoices(user: CurrentUser = Depends(get_current_user)):
    """Tenant'ın geçmiş ödemeleri."""
    if not user.tenant_id:
        return APIResponse(ok=True, data={"payments": []})
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
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
                await conn.execute(
                    """UPDATE subscriptions SET status = 'failed', updated_at = NOW()
                       WHERE iyzico_subscription_ref = $1""",
                    sub_ref,
                )

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
