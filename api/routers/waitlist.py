"""Bekleme listesi — public kayıt + admin listeleme."""
from __future__ import annotations
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from api.auth import CurrentUser, get_current_user
from api.db import service_session
from api.schemas import APIResponse

log = logging.getLogger("api.waitlist")
router = APIRouter()

PLAN_ETIKET = {
    "pro_solo": "Pro Solo",
    "pro_solo_uyap": "Pro + UYAP",
    "team": "Team",
}


# ---------------------------------------------------------------------------
# Public endpoint — auth gerektirmez
# ---------------------------------------------------------------------------

class WaitlistReq(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    plan: str | None = Field(default=None, max_length=50)


@router.post("/", response_model=APIResponse)
async def join_waitlist(payload: WaitlistReq, request: Request):
    """Bekleme listesine kayıt. Duplicate e-posta sessizce kabul edilir."""
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)

    async with service_session() as conn:
        # Upsert: aynı e-posta tekrar gelirse güncelleme yapma, sadece geç
        existing = await conn.fetchval(
            "SELECT id FROM waitlist WHERE email = $1", payload.email
        )
        if existing:
            # Zaten kayıtlı — hata vermeden başarılı döndür (bilgi sızdırma önlemi)
            return APIResponse(ok=True, message="Bekleme listesine alındınız.")

        await conn.execute(
            """INSERT INTO waitlist (name, email, plan, ip)
               VALUES ($1, $2, $3, $4)""",
            payload.name, payload.email,
            payload.plan if payload.plan in PLAN_ETIKET else None,
            ip,
        )

    # Admin e-posta bildirimi
    try:
        from services.email import send_email, _wrap
        admin_to = (
            os.environ.get("ADMIN_EMAIL")
            or os.environ.get("FEEDBACK_ADMIN_EMAIL")
            or "admin@hukukcuyapayzekasi.com"
        )
        site = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukcuyapayzekasi.com")
        plan_label = PLAN_ETIKET.get(payload.plan or "", "")

        body = (
            "<p>Yeni bir kullanıcı bekleme listesine katıldı.</p>"
            f"<p><strong>Ad:</strong> {payload.name}<br>"
            f"<strong>E-posta:</strong> {payload.email}<br>"
            f"<strong>İlgilendiği plan:</strong> {plan_label or '(belirtilmedi)'}</p>"
            f"<p><a href='{site}/app/admin/bekleme-listesi'>Admin panelinde görüntüle →</a></p>"
        )
        await send_email(
            to=admin_to,
            subject=f"🎯 Bekleme listesi — {payload.name} ({payload.email})",
            html=_wrap("Yeni Bekleme Listesi Kaydı", body),
        )
    except Exception:
        log.exception("Bekleme listesi e-posta bildirimi gönderilemedi.")

    return APIResponse(ok=True, message="Bekleme listesine alındınız.")


# ---------------------------------------------------------------------------
# Admin endpoint — sadece role='admin'
# ---------------------------------------------------------------------------

async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(403, "Sadece admin erişebilir.")
    return user


@router.get("/admin", response_model=APIResponse)
async def list_waitlist(
    limit: int = 100,
    offset: int = 0,
    admin: CurrentUser = Depends(require_admin),
):
    """Bekleme listesi kayıtlarını listele."""
    async with service_session() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM waitlist")
        rows = await conn.fetch(
            """SELECT id, name, email, plan, created_at
               FROM waitlist
               ORDER BY created_at DESC
               LIMIT $1 OFFSET $2""",
            limit, offset,
        )

    entries = [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "email": r["email"],
            "plan": r["plan"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]

    return APIResponse(ok=True, data={"total": total, "entries": entries})
