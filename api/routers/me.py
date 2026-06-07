"""Kullanıcı kendi profili + kullanım + tenant + hesap silme."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from api.audit import audit
from api.auth import CurrentUser, get_current_user
from api.db import db_session
from api.schemas import APIResponse

router = APIRouter()


@router.get("/", response_model=APIResponse)
async def me(user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT email_verified, kvkk_accepted_at, marketing_consent,
                      created_at, last_login_at
               FROM users WHERE id = $1""",
            user.user_id,
        )
    return APIResponse(ok=True, data={
        "user": {
            "id": user.user_id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "email_verified": bool(row and row["email_verified"]),
            "marketing_consent": bool(row and row["marketing_consent"]),
            "created_at": row["created_at"].isoformat() if row else None,
            "last_login_at": row["last_login_at"].isoformat() if row and row["last_login_at"] else None,
        },
        "tenant": {
            "id": user.tenant_id,
            "plan": user.tenant_plan,
            "role": user.tenant_role,
        } if user.tenant_id else None,
    })


class UpdateProfileReq(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    marketing_consent: bool | None = None


@router.patch("/", response_model=APIResponse)
async def update_profile(
    payload: UpdateProfileReq,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    updates = []
    args: list = []
    if payload.name is not None:
        updates.append(f"name = ${len(args) + 1}")
        args.append(payload.name)
    if payload.marketing_consent is not None:
        updates.append(f"marketing_consent = ${len(args) + 1}")
        args.append(payload.marketing_consent)
    if not updates:
        return APIResponse(ok=True, message="Değişiklik yok.")

    args.append(user.user_id)
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        await conn.execute(
            f"UPDATE users SET {', '.join(updates)}, updated_at = NOW() "
            f"WHERE id = ${len(args)}",
            *args,
        )

    await audit(action="profile.updated", user_id=user.user_id, request=request)
    return APIResponse(ok=True, message="Profil güncellendi.")


@router.get("/usage", response_model=APIResponse)
async def usage_stats(user: CurrentUser = Depends(get_current_user)):
    """Tier'a göre limitler + gerçek kullanım."""
    from api.rate_limit import DAILY_LIMITS, UNLIMITED_TIERS

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    month_ago = now - timedelta(days=30)

    tier = user.tenant_plan or "free"
    unlimited = tier in UNLIMITED_TIERS
    limits = None if unlimited else DAILY_LIMITS.get(tier, DAILY_LIMITS["anonim"])

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        daily = await conn.fetch(
            """SELECT event_type, COUNT(*) c FROM usage_events
               WHERE user_id = $1 AND created_at > $2 GROUP BY event_type""",
            user.user_id, day_ago,
        )
        monthly = await conn.fetch(
            """SELECT event_type, COUNT(*) c FROM usage_events
               WHERE user_id = $1 AND created_at > $2 GROUP BY event_type""",
            user.user_id, month_ago,
        )

    daily_map = {r["event_type"]: r["c"] for r in daily}
    monthly_map = {r["event_type"]: r["c"] for r in monthly}

    breakdown = []
    for ev, lim in (limits or {}).items():
        used = daily_map.get(ev, 0)
        breakdown.append({
            "event_type": ev,
            "daily_used": used,
            "daily_limit": lim,
            "monthly_used": monthly_map.get(ev, 0),
            "remaining": max(lim - used, 0),
            "percent": min(100, int(used * 100 / lim)) if lim else 0,
        })

    return APIResponse(ok=True, data={
        "tier": tier,
        "unlimited": unlimited,
        "breakdown": breakdown,
        "reset_at": (now + timedelta(hours=24)).isoformat(),
    })


@router.get("/tenants", response_model=APIResponse)
async def my_tenants(user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT t.id, t.name, t.slug, t.type, t.plan_tier, tm.role,
                      t.plan_expires_at, t.trial_ends_at
               FROM tenant_members tm
               JOIN tenants t ON t.id = tm.tenant_id
               WHERE tm.user_id = $1 AND t.is_active = TRUE
               ORDER BY tm.created_at""",
            user.user_id,
        )
    return APIResponse(ok=True, data={
        "tenants": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "slug": r["slug"],
                "type": r["type"],
                "plan": r["plan_tier"],
                "role": r["role"],
                "plan_expires_at": r["plan_expires_at"].isoformat() if r["plan_expires_at"] else None,
                "trial_ends_at": r["trial_ends_at"].isoformat() if r["trial_ends_at"] else None,
            }
            for r in rows
        ],
    })


@router.get("/searches", response_model=APIResponse)
async def my_searches(
    user: CurrentUser = Depends(get_current_user),
    limit: int = 50,
    favorites_only: bool = False,
):
    """Geçmiş aramalar (Free hesap özelliği)."""
    where = "WHERE user_id = $1"
    if favorites_only:
        where += " AND is_favorite = TRUE"
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            f"""SELECT id, query, result_count, filters, is_favorite, tags, created_at
                FROM user_searches {where}
                ORDER BY created_at DESC LIMIT $2""",
            user.user_id, min(limit, 200),
        )
    return APIResponse(ok=True, data={
        "searches": [
            {
                "id": str(r["id"]),
                "query": r["query"],
                "result_count": r["result_count"],
                "filters": r["filters"],
                "is_favorite": bool(r["is_favorite"]) if "is_favorite" in r else False,
                "tags": r["tags"] if "tags" in r else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    })


@router.post("/searches/{search_id}/favorite", response_model=APIResponse)
async def toggle_favorite(
    search_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT is_favorite FROM user_searches WHERE id = $1 AND user_id = $2",
            search_id, user.user_id,
        )
        if not row:
            raise HTTPException(404, "Bulunamadı.")
        new_val = not bool(row.get("is_favorite") if row.get("is_favorite") is not None else False)
        await conn.execute(
            "UPDATE user_searches SET is_favorite = $1 WHERE id = $2",
            new_val, search_id,
        )
    return APIResponse(ok=True, data={"is_favorite": new_val})


@router.delete("/account", response_model=APIResponse)
async def delete_account(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """KVKK madde 7 — silme hakkı.
    Hesap pasifleştirilir, kişisel veriler 30 gün sonra otomatik silinir."""
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        async with conn.transaction():
            await conn.execute(
                """UPDATE users SET is_active = FALSE, email = $1, name = '[silindi]',
                          password_hash = NULL, metadata = metadata || '{"deleted_at": "' || NOW() || '"}'::jsonb
                   WHERE id = $2""",
                f"deleted-{user.user_id}@hukukemsal.tr",
                user.user_id,
            )
            await conn.execute(
                "DELETE FROM sessions WHERE user_id = $1",
                user.user_id,
            )

    await audit(
        action="account.deleted",
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        request=request,
    )
    return APIResponse(ok=True, message="Hesap silme talebiniz alındı. Verileriniz 30 gün içinde tamamen silinir.")
