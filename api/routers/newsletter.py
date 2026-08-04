"""Haftalık bülten — public abonelik/çıkış + admin yönetim.

Public:
  POST /api/newsletter/        → abone ol (KVKK onayı zorunlu)
  POST /api/newsletter/cikis   → tek-tık abonelikten çıkış (e-postadaki token ile)

Admin (role=admin):
  GET  /api/newsletter/admin                    → abone listesi (durum filtresi + arama)
  POST /api/newsletter/admin/{id}/unsubscribe   → admin bu kişiyi abonelikten çıkarır
  POST /api/newsletter/admin/{id}/block         → bu kişiye bülten gönderimini engelle
  POST /api/newsletter/admin/{id}/reactivate    → çıkış/engeli kaldır, tekrar aktif et

Tablo GLOBAL (RLS yok, bkz. infra/db/31_newsletter_subscribers.sql). Yazımlar
service_session ile yapılır (feedback.py/waitlist.py deseni); yeni yazı
yayınlandığında bildirim gönderimi services/newsletter.py üzerinden yapılır
(bkz. api/routers/icerik.py admin_yayinla).
"""
from __future__ import annotations

import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from api.audit import audit
from api.auth import CurrentUser, get_current_user
from api.db import service_session
from api.deps import rate_limit
from api.schemas import APIResponse

log = logging.getLogger("api.newsletter")
router = APIRouter()

GECERLI_DURUMLAR = ("active", "unsubscribed", "blocked")


def _uret_token() -> str:
    return secrets.token_urlsafe(24)


# ---------------------------------------------------------------------------
# Public endpoint'ler — auth gerektirmez
# ---------------------------------------------------------------------------

class AboneReq(BaseModel):
    email: EmailStr
    consent: bool = Field(..., description="KVKK/e-posta pazarlama onayı — zorunlu.")


@router.post("/", response_model=APIResponse, dependencies=[Depends(rate_limit)])
async def abone_ol(payload: AboneReq, request: Request):
    """Haftalık bültene abone ol. Onay verilmeden kayıt yapılmaz."""
    if not payload.consent:
        raise HTTPException(422, "Devam etmek için e-posta izni onayı gereklidir.")

    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)

    async with service_session() as conn:
        existing = await conn.fetchrow(
            "SELECT id, status FROM newsletter_subscribers WHERE email = $1",
            payload.email,
        )
        if existing:
            if existing["status"] == "blocked":
                # Admin tarafından engellenmiş — sessizce başarı dön (bilgi
                # sızdırma önlemi + admin kararını kullanıcı kendi isteğiyle
                # geçersiz kılamasın).
                return APIResponse(ok=True, message="Bültene abone oldunuz.")
            if existing["status"] == "unsubscribed":
                await conn.execute(
                    """UPDATE newsletter_subscribers
                       SET status = 'active', consent_at = NOW(),
                           unsubscribed_at = NULL
                       WHERE id = $1""",
                    existing["id"],
                )
            # zaten active ise değişiklik yok — tekrar kayıt oluşturma
            return APIResponse(ok=True, message="Bültene abone oldunuz.")

        await conn.execute(
            """INSERT INTO newsletter_subscribers (email, unsubscribe_token, ip)
               VALUES ($1, $2, $3)""",
            payload.email, _uret_token(), ip,
        )

    return APIResponse(ok=True, message="Bültene abone oldunuz.")


class CikisReq(BaseModel):
    token: str = Field(min_length=10)


@router.post("/cikis", response_model=APIResponse)
async def abonelikten_cik(payload: CikisReq):
    """E-postadaki tek-tık bağlantısıyla abonelikten çıkış."""
    async with service_session() as conn:
        rec = await conn.fetchrow(
            """UPDATE newsletter_subscribers
               SET status = 'unsubscribed', unsubscribed_at = NOW()
               WHERE unsubscribe_token = $1 AND status != 'blocked'
               RETURNING id""",
            payload.token,
        )
    if not rec:
        # Token geçersiz VEYA zaten blocked/unsubscribed — kullanıcıya göre
        # sonuç aynı (artık bülten almıyor), bu yüzden hata değil başarı dönülür.
        return APIResponse(ok=True, message="Abonelikten çıkış yapıldı.")
    return APIResponse(ok=True, message="Abonelikten çıkış yapıldı.")


# ---------------------------------------------------------------------------
# Admin endpoint'ler — sadece role='admin'
# ---------------------------------------------------------------------------

async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(403, "Sadece admin erişebilir.")
    return user


@router.get("/admin", response_model=APIResponse)
async def admin_liste(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    arama: str | None = None,
    admin: CurrentUser = Depends(require_admin),
):
    where_parts = []
    args: list = []
    if status:
        if status not in GECERLI_DURUMLAR:
            raise HTTPException(400, "Geçersiz durum filtresi.")
        args.append(status)
        where_parts.append(f"status = ${len(args)}")
    if arama:
        args.append(f"%{arama.strip()}%")
        where_parts.append(f"email ILIKE ${len(args)}")
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    async with service_session() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM newsletter_subscribers {where}", *args
        )
        durum_rows = await conn.fetch(
            "SELECT status, COUNT(*) c FROM newsletter_subscribers GROUP BY status"
        )
        args.extend([limit, offset])
        rows = await conn.fetch(
            f"""SELECT id, email, status, user_id, consent_at, unsubscribed_at,
                       blocked_at, blocked_reason, last_sent_at, created_at
                FROM newsletter_subscribers
                {where}
                ORDER BY created_at DESC
                LIMIT ${len(args) - 1} OFFSET ${len(args)}""",
            *args,
        )

    entries = [
        {
            "id": str(r["id"]),
            "email": r["email"],
            "status": r["status"],
            "has_account": r["user_id"] is not None,
            "consent_at": r["consent_at"].isoformat() if r["consent_at"] else None,
            "unsubscribed_at": r["unsubscribed_at"].isoformat() if r["unsubscribed_at"] else None,
            "blocked_at": r["blocked_at"].isoformat() if r["blocked_at"] else None,
            "blocked_reason": r["blocked_reason"],
            "last_sent_at": r["last_sent_at"].isoformat() if r["last_sent_at"] else None,
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]
    durumlar = {d: 0 for d in GECERLI_DURUMLAR}
    for r in durum_rows:
        durumlar[r["status"]] = r["c"]

    return APIResponse(ok=True, data={"total": total, "durumlar": durumlar, "entries": entries})


@router.post("/admin/{sub_id}/unsubscribe", response_model=APIResponse)
async def admin_unsubscribe(sub_id: str, admin: CurrentUser = Depends(require_admin)):
    async with service_session() as conn:
        rec = await conn.fetchrow(
            """UPDATE newsletter_subscribers
               SET status = 'unsubscribed', unsubscribed_at = NOW()
               WHERE id = $1::uuid
               RETURNING email""",
            sub_id,
        )
    if not rec:
        raise HTTPException(404, "Abone bulunamadı.")
    await audit(action="admin.newsletter_unsubscribe", user_id=admin.user_id,
                resource=f"newsletter_subscriber:{sub_id}")
    return APIResponse(ok=True, message=f"{rec['email']} abonelikten çıkarıldı.")


class BlokReq(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.post("/admin/{sub_id}/block", response_model=APIResponse)
async def admin_block(
    sub_id: str,
    payload: BlokReq,
    admin: CurrentUser = Depends(require_admin),
):
    """Bu adrese bülten gönderimini kalıcı olarak engelle (kullanıcı kendi
    isteğiyle geri açamaz — yalnızca admin `reactivate` ile kaldırabilir)."""
    async with service_session() as conn:
        rec = await conn.fetchrow(
            """UPDATE newsletter_subscribers
               SET status = 'blocked', blocked_at = NOW(),
                   blocked_by = $1::uuid, blocked_reason = $2
               WHERE id = $3::uuid
               RETURNING email""",
            admin.user_id, payload.reason, sub_id,
        )
    if not rec:
        raise HTTPException(404, "Abone bulunamadı.")
    await audit(action="admin.newsletter_block", user_id=admin.user_id,
                resource=f"newsletter_subscriber:{sub_id}",
                metadata={"reason": payload.reason})
    return APIResponse(ok=True, message=f"{rec['email']} için bülten gönderimi engellendi.")


@router.post("/admin/{sub_id}/reactivate", response_model=APIResponse)
async def admin_reactivate(sub_id: str, admin: CurrentUser = Depends(require_admin)):
    """Unsubscribe/blocked durumundan çıkarıp tekrar aktif eder."""
    async with service_session() as conn:
        rec = await conn.fetchrow(
            """UPDATE newsletter_subscribers
               SET status = 'active', unsubscribed_at = NULL,
                   blocked_at = NULL, blocked_by = NULL, blocked_reason = NULL
               WHERE id = $1::uuid
               RETURNING email""",
            sub_id,
        )
    if not rec:
        raise HTTPException(404, "Abone bulunamadı.")
    await audit(action="admin.newsletter_reactivate", user_id=admin.user_id,
                resource=f"newsletter_subscriber:{sub_id}")
    return APIResponse(ok=True, message=f"{rec['email']} tekrar aktif edildi.")
