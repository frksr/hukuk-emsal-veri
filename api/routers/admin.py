"""Internal admin panel — sadece role='admin' kullanıcılar.

Beta yönetimi, manuel plan upgrade, audit log, feedback yönetimi.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.audit import audit
from api.auth import CurrentUser, get_current_user
from api.db import service_session
from api.schemas import APIResponse

router = APIRouter()


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(403, "Bu sayfaya sadece admin erişebilir.")
    return user


@router.get("/dashboard", response_model=APIResponse)
async def dashboard(admin: CurrentUser = Depends(require_admin)):
    """Genel istatistikler — DAU, MAU, tier dağılımı, gelir."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    async with service_session() as conn:
        # Kullanıcı sayıları
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
        new_24h = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at > $1", day_ago
        )
        new_7d = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at > $1", week_ago
        )
        new_30d = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at > $1", month_ago
        )

        # Aktif kullanıcı
        dau = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM usage_events WHERE created_at > $1 AND user_id IS NOT NULL",
            day_ago,
        )
        mau = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM usage_events WHERE created_at > $1 AND user_id IS NOT NULL",
            month_ago,
        )

        # Tier dağılımı
        tier_dist = await conn.fetch(
            """SELECT plan_tier, COUNT(*) c FROM tenants
               WHERE is_active = TRUE GROUP BY plan_tier ORDER BY c DESC"""
        )

        # Gelir tahmini (aylık)
        monthly_revenue = await conn.fetchval(
            """SELECT COALESCE(SUM(amount_try), 0) FROM payments
               WHERE status = 'success' AND paid_at > $1""",
            month_ago,
        )

        # Beta program
        beta_count = await conn.fetchval(
            "SELECT COUNT(*) FROM tenants WHERE beta_program = TRUE"
        )

        # Feedback özet
        feedback_open = await conn.fetchval(
            "SELECT COUNT(*) FROM feedback WHERE status IN ('new', 'reviewing', 'in_progress')"
        )
        feedback_critical = await conn.fetchval(
            "SELECT COUNT(*) FROM feedback WHERE severity = 'critical' AND status IN ('new', 'reviewing')"
        )

        # Toplam UYAP doküman
        total_docs = await conn.fetchval("SELECT COUNT(*) FROM tenant_documents")
        total_queries_30d = await conn.fetchval(
            "SELECT COUNT(*) FROM tenant_queries WHERE created_at > $1", month_ago
        )

    return APIResponse(ok=True, data={
        "users": {
            "total": total_users, "new_24h": new_24h, "new_7d": new_7d, "new_30d": new_30d,
            "dau": dau, "mau": mau,
        },
        "tiers": [{"plan": r["plan_tier"], "count": r["c"]} for r in tier_dist],
        "revenue": {
            "monthly_try": float(monthly_revenue or 0),
            "beta_count": beta_count,
        },
        "feedback": {
            "open": feedback_open, "critical": feedback_critical,
        },
        "uyap": {
            "documents": total_docs, "queries_30d": total_queries_30d,
        },
    })


@router.get("/users", response_model=APIResponse)
async def list_users(
    admin: CurrentUser = Depends(require_admin),
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    where = "WHERE is_active = TRUE"
    args: list = []
    if search:
        args.append(f"%{search}%")
        where += f" AND (email ILIKE ${len(args)} OR name ILIKE ${len(args)})"
    args.extend([limit, offset])

    async with service_session() as conn:
        rows = await conn.fetch(
            f"""SELECT u.id, u.email, u.name, u.role, u.email_verified, u.created_at,
                       u.last_login_at,
                       t.id tid, t.name tname, t.plan_tier, t.beta_program
                FROM users u
                LEFT JOIN tenant_members tm ON tm.user_id = u.id
                LEFT JOIN tenants t ON t.id = tm.tenant_id
                {where}
                ORDER BY u.created_at DESC
                LIMIT ${len(args) - 1} OFFSET ${len(args)}""",
            *args,
        )

    return APIResponse(ok=True, data={
        "users": [
            {
                "id": str(r["id"]),
                "email": r["email"],
                "name": r["name"],
                "role": r["role"],
                "email_verified": bool(r["email_verified"]),
                "created_at": r["created_at"].isoformat(),
                "last_login_at": r["last_login_at"].isoformat() if r["last_login_at"] else None,
                "tenant": {
                    "id": str(r["tid"]) if r["tid"] else None,
                    "name": r["tname"],
                    "plan": r["plan_tier"],
                    "beta": r["beta_program"],
                } if r["tid"] else None,
            }
            for r in rows
        ],
    })


class TenantUpgradeReq(BaseModel):
    plan_tier: str
    reason: str | None = None
    duration_days: int | None = None  # NULL = sınırsız
    beta_invited_by: str | None = None


@router.post("/tenants/{tenant_id}/upgrade", response_model=APIResponse)
async def manual_upgrade(
    tenant_id: str,
    payload: TenantUpgradeReq,
    admin: CurrentUser = Depends(require_admin),
):
    """Manuel tenant plan upgrade — beta hediye için."""
    valid_plans = {"free", "pro_solo", "pro_solo_uyap", "team", "team_uyap", "enterprise"}
    if payload.plan_tier not in valid_plans:
        raise HTTPException(400, "Geçersiz plan tier.")

    expires_at = None
    if payload.duration_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.duration_days)

    is_beta = payload.plan_tier != "free" and bool(payload.beta_invited_by)

    async with service_session() as conn:
        row = await conn.fetchrow("SELECT id FROM tenants WHERE id = $1::uuid", tenant_id)
        if not row:
            raise HTTPException(404, "Tenant bulunamadı.")

        await conn.execute(
            """UPDATE tenants SET
               plan_tier = $1::plan_tier,
               plan_started_at = NOW(),
               plan_expires_at = $2,
               beta_program = $3,
               beta_invited_by = $4,
               beta_signed_at = CASE WHEN $3 THEN NOW() ELSE beta_signed_at END,
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
               WHERE id = $5::uuid""",
            payload.plan_tier, expires_at, is_beta, payload.beta_invited_by, tenant_id,
        )

    await audit(
        action="admin.tenant_upgraded",
        user_id=admin.user_id,
        tenant_id=tenant_id,
        metadata={
            "plan": payload.plan_tier,
            "reason": payload.reason,
            "duration_days": payload.duration_days,
            "is_beta": is_beta,
        },
    )
    return APIResponse(ok=True, message=f"Tenant {payload.plan_tier} planına alındı.")


@router.get("/audit-log", response_model=APIResponse)
async def audit_log(
    admin: CurrentUser = Depends(require_admin),
    action: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
):
    where_parts = []
    args: list = []
    if action:
        args.append(action)
        where_parts.append(f"action = ${len(args)}")
    if user_id:
        args.append(user_id)
        where_parts.append(f"user_id = ${len(args)}::uuid")
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    args.append(limit)

    async with service_session() as conn:
        rows = await conn.fetch(
            f"""SELECT id, user_id, tenant_id, action, resource, ip_address,
                       success, metadata, created_at
                FROM audit_log {where}
                ORDER BY created_at DESC LIMIT ${len(args)}""",
            *args,
        )

    return APIResponse(ok=True, data={
        "logs": [
            {
                "id": r["id"],
                "user_id": str(r["user_id"]) if r["user_id"] else None,
                "tenant_id": str(r["tenant_id"]) if r["tenant_id"] else None,
                "action": r["action"],
                "resource": r["resource"],
                "ip_address": str(r["ip_address"]) if r["ip_address"] else None,
                "success": r["success"],
                "metadata": r["metadata"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    })


@router.get("/feedback", response_model=APIResponse)
async def list_feedback(
    admin: CurrentUser = Depends(require_admin),
    status: str | None = None,
    severity: str | None = None,
    limit: int = 100,
):
    where_parts = []
    args: list = []
    if status:
        args.append(status)
        where_parts.append(f"f.status = ${len(args)}")
    if severity:
        args.append(severity)
        where_parts.append(f"f.severity = ${len(args)}")
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    args.append(limit)

    async with service_session() as conn:
        rows = await conn.fetch(
            f"""SELECT f.*, u.email user_email, u.name user_name
                FROM feedback f
                LEFT JOIN users u ON u.id = f.user_id
                {where}
                ORDER BY
                  CASE f.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                                  WHEN 'normal' THEN 2 ELSE 3 END,
                  f.created_at DESC
                LIMIT ${len(args)}""",
            *args,
        )

    return APIResponse(ok=True, data={
        "feedback": [
            {
                "id": str(r["id"]),
                "user": {"email": r["user_email"], "name": r["user_name"]} if r["user_email"] else None,
                "type": r["feedback_type"],
                "severity": r["severity"],
                "subject": r["subject"],
                "message": r["message"],
                "page_url": r["page_url"],
                "status": r["status"],
                "admin_note": r["admin_note"],
                "created_at": r["created_at"].isoformat(),
                "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
            }
            for r in rows
        ],
    })


class FeedbackUpdateReq(BaseModel):
    status: str | None = None
    admin_note: str | None = None


@router.patch("/feedback/{feedback_id}", response_model=APIResponse)
async def update_feedback(
    feedback_id: str,
    payload: FeedbackUpdateReq,
    admin: CurrentUser = Depends(require_admin),
):
    updates = []
    args: list = []
    if payload.status:
        args.append(payload.status)
        updates.append(f"status = ${len(args)}")
        if payload.status == "resolved":
            updates.append("resolved_at = NOW()")
    if payload.admin_note is not None:
        args.append(payload.admin_note)
        updates.append(f"admin_note = ${len(args)}")
    if not updates:
        return APIResponse(ok=True, message="Değişiklik yok.")

    args.append(feedback_id)
    async with service_session() as conn:
        await conn.execute(
            f"UPDATE feedback SET {', '.join(updates)} WHERE id = ${len(args)}::uuid",
            *args,
        )
    return APIResponse(ok=True, message="Geri bildirim güncellendi.")


@router.post("/beta-invite", response_model=APIResponse)
async def beta_invite(
    payload: dict,
    admin: CurrentUser = Depends(require_admin),
):
    """Hızlı beta invite — email + plan + süre."""
    from services.email import send_email, _wrap

    email = payload.get("email")
    plan = payload.get("plan_tier", "pro_solo_uyap")
    days = int(payload.get("duration_days", 180))

    if not email:
        raise HTTPException(400, "Email zorunlu.")

    site = "https://hukukemsal.tr"
    body = (
        f"<p>Merhaba,</p>"
        f"<p><strong>{admin.name or admin.email}</strong> sizi Hukuk Emsal Beta programına davet etti.</p>"
        f"<p>Beta avukat olarak <strong>{days} gün ücretsiz {plan}</strong> erişiminiz olacak.</p>"
        f"<p>Karşılığında: haftalık 15dk geri bildirim görüşmesi, ürünün lansmanında "
        f"kurucu kullanıcı olarak gösterilme.</p>"
        f"<p>Aşağıdaki bağlantıdan kayıt olun, hesap açtığınızda planınız otomatik aktif olacak.</p>"
    )
    await send_email(
        to=email,
        subject="🎁 Hukuk Emsal Beta Programı — Davetlisiniz",
        html=_wrap("Beta Davetiyesi", body, (f"{site}/kayit?ref=beta", "Hemen Kaydol")),
    )

    # Davet metadata'sı (tenant kuruluna kadar bekler, admin sonra manuel upgrade yapar)
    await audit(
        action="admin.beta_invite_sent",
        user_id=admin.user_id,
        metadata={"email": email, "plan": plan, "duration_days": days},
    )
    return APIResponse(ok=True, message=f"Beta davetiyesi {email} adresine gönderildi.")
