"""Bekleme listesi — public kayıt + admin CRM (listeleme, davet gönderimi)."""
from __future__ import annotations
import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from api.audit import audit
from api.auth import CurrentUser, get_current_user
from api.db import service_session
from api.schemas import APIResponse

log = logging.getLogger("api.waitlist")
router = APIRouter()

PLAN_ETIKET = {
    "pro_solo": "Pro Solo",
    "pro_solo_uyap": "Pro + UYAP",
    "team": "Team",
    "team_uyap": "Team + UYAP",
}

# Bekleme listesi CRM durumları (infra/db/24_waitlist_crm.sql)
GECERLI_DURUMLAR = ("bekliyor", "davet_edildi", "kayit_oldu")


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
    plan: str | None = None,
    status: str | None = None,
    arama: str | None = None,
    admin: CurrentUser = Depends(require_admin),
):
    """Bekleme listesi kayıtlarını listele — plan/durum filtresi + e-posta araması."""
    where_parts = []
    args: list = []
    if plan:
        args.append(plan)
        where_parts.append(f"plan = ${len(args)}")
    if status:
        if status not in GECERLI_DURUMLAR:
            raise HTTPException(400, "Geçersiz durum filtresi.")
        args.append(status)
        where_parts.append(f"status = ${len(args)}")
    if arama:
        args.append(f"%{arama.strip()}%")
        where_parts.append(f"(email ILIKE ${len(args)} OR name ILIKE ${len(args)})")
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    async with service_session() as conn:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM waitlist {where}", *args)
        # Durum özetleri filtreden bağımsız (özet kartları için)
        durum_rows = await conn.fetch(
            "SELECT status, COUNT(*) c FROM waitlist GROUP BY status"
        )
        args.extend([limit, offset])
        rows = await conn.fetch(
            f"""SELECT id, name, email, plan, status, invited_at, invite_code, notes, created_at
               FROM waitlist
               {where}
               ORDER BY created_at DESC
               LIMIT ${len(args) - 1} OFFSET ${len(args)}""",
            *args,
        )

    entries = [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "email": r["email"],
            "plan": r["plan"],
            "status": r["status"],
            "invited_at": r["invited_at"].isoformat() if r["invited_at"] else None,
            "invite_code": r["invite_code"],
            "notes": r["notes"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]

    durumlar = {d: 0 for d in GECERLI_DURUMLAR}
    for r in durum_rows:
        durumlar[r["status"]] = r["c"]

    return APIResponse(ok=True, data={"total": total, "durumlar": durumlar, "entries": entries})


class DavetReq(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/admin/davet", response_model=APIResponse)
async def send_invites(
    payload: DavetReq,
    admin: CurrentUser = Depends(require_admin),
):
    """Seçili bekleme listesi kayıtlarına davet e-postası gönder.

    Her kayıt için tekil davet kodu üretilir; e-posta başarıyla gönderilirse
    status='davet_edildi' + invited_at set edilir. Zaten kayıt olanlar atlanır.
    """
    from services.email import send_email, _wrap

    site = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukcuyapayzekasi.com")
    gonderilen: list[str] = []
    atlanan = 0
    basarisiz: list[str] = []

    async with service_session() as conn:
        for entry_id in payload.ids:
            try:
                row = await conn.fetchrow(
                    """SELECT id, name, email, plan, status, invite_code
                       FROM waitlist WHERE id = $1::uuid""",
                    entry_id,
                )
            except Exception:
                atlanan += 1
                continue
            if not row or row["status"] == "kayit_oldu":
                atlanan += 1
                continue

            # Mevcut kod varsa koru (tekrar davette aynı link geçerli kalsın)
            code = row["invite_code"]
            if not code:
                for _ in range(5):
                    code = secrets.token_urlsafe(8)
                    exists = await conn.fetchval(
                        "SELECT 1 FROM waitlist WHERE invite_code = $1", code
                    )
                    if not exists:
                        break

            link = f"{site}/kayit?davet={code}"
            plan_label = PLAN_ETIKET.get(row["plan"] or "", "")
            body = (
                f"<p>Merhaba {row['name']},</p>"
                "<p>Hukuk Emsal bekleme listesine katıldığınız için teşekkürler. "
                "Sıranız geldi — hesabınızı şimdi açabilirsiniz!</p>"
                + (
                    f"<p>İlgilendiğiniz plan: <strong>{plan_label}</strong>. "
                    "Kayıt sonrası panelden dilediğiniz an aboneliğinizi başlatabilirsiniz.</p>"
                    if plan_label else ""
                )
                + "<p>Aşağıdaki bağlantı size özeldir; kayıt sırasında davetiniz "
                "otomatik olarak tanınır.</p>"
            )
            ok = await send_email(
                to=row["email"],
                subject="🎉 Hukuk Emsal — Sıranız Geldi, Davetlisiniz!",
                html=_wrap("Davetlisiniz!", body, (link, "Hemen Kaydol")),
            )
            if not ok:
                basarisiz.append(row["email"])
                continue

            await conn.execute(
                """UPDATE waitlist
                   SET status = 'davet_edildi', invited_at = NOW(), invite_code = $1
                   WHERE id = $2""",
                code, row["id"],
            )
            gonderilen.append(row["email"])

    await audit(
        action="admin.waitlist_invited",
        user_id=admin.user_id,
        metadata={
            "gonderilen": len(gonderilen),
            "atlanan": atlanan,
            "basarisiz": len(basarisiz),
        },
    )

    mesaj = f"{len(gonderilen)} davet gönderildi."
    if atlanan:
        mesaj += f" {atlanan} kayıt atlandı."
    if basarisiz:
        mesaj += f" {len(basarisiz)} e-posta gönderilemedi."
    return APIResponse(ok=True, message=mesaj, data={
        "gonderilen": len(gonderilen),
        "atlanan": atlanan,
        "basarisiz": basarisiz,
    })
