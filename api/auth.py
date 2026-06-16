"""Auth + tenant context middleware.

NextAuth.js JWT'sini doğrular, kullanıcıyı + aktif tenant'ı çözer.

Frontend tarafı:
  Next.js her isteğe `Authorization: Bearer <NEXTAUTH_JWT>` ekliyor.
  JWT, NEXTAUTH_SECRET ile imzalı; backend aynı secret ile verify ediyor.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Annotated, Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request

from api.db import service_session


class CurrentUser:
    def __init__(
        self,
        user_id: str,
        email: str,
        name: Optional[str],
        role: str,
        tenant_id: Optional[str] = None,
        tenant_plan: Optional[str] = None,
        tenant_role: Optional[str] = None,
        email_verified: bool = False,
    ):
        self.user_id = user_id
        self.email = email
        self.name = name
        self.role = role
        self.tenant_id = tenant_id
        self.tenant_plan = tenant_plan
        self.tenant_role = tenant_role
        self.email_verified = email_verified


def _decode_jwt(token: str) -> dict:
    secret = os.environ.get("NEXTAUTH_SECRET")
    if not secret:
        raise RuntimeError("NEXTAUTH_SECRET env eksik")
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Oturum süresi dolmuş, yeniden giriş yapın.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Geçersiz oturum.")


async def get_current_user(
    request: Request,
    authorization: Annotated[Optional[str], Header()] = None,
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-Id")] = None,
) -> CurrentUser:
    """Auth zorunlu endpoint'ler için dependency."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Yetkilendirme gerekli.")

    token = authorization.split(" ", 1)[1].strip()
    payload = _decode_jwt(token)

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(401, "Token geçersiz.")

    # Auth bootstrap: kullanıcı + tenant üyeliklerini context OLUŞMADAN ÖNCE
    # çözmek gerekir (kim olduğunu burada belirliyoruz) → service_session.
    async with service_session() as conn:
        user_row = await conn.fetchrow(
            "SELECT id, email, name, role, is_active, email_verified FROM users WHERE id = $1",
            user_id,
        )
        if not user_row or not user_row["is_active"]:
            raise HTTPException(401, "Kullanıcı bulunamadı veya pasif.")

        # Aktif tenant: header'da gelen tenant_id veya kullanıcının ilk üyeliği
        tenant_id = x_tenant_id
        tenant_plan: Optional[str] = None
        tenant_role: Optional[str] = None

        if tenant_id:
            # Üyelik doğrula
            mem = await conn.fetchrow(
                """SELECT tm.role, t.plan_tier FROM tenant_members tm
                   JOIN tenants t ON t.id = tm.tenant_id
                   WHERE tm.tenant_id = $1 AND tm.user_id = $2
                     AND t.is_active = TRUE""",
                tenant_id,
                user_id,
            )
            if not mem:
                raise HTTPException(403, "Bu tenant'a üye değilsin.")
            tenant_role = mem["role"]
            tenant_plan = mem["plan_tier"]
        else:
            # İlk tenant üyeliğini bul
            mem = await conn.fetchrow(
                """SELECT tm.tenant_id, tm.role, t.plan_tier FROM tenant_members tm
                   JOIN tenants t ON t.id = tm.tenant_id
                   WHERE tm.user_id = $1 AND t.is_active = TRUE
                   ORDER BY tm.created_at LIMIT 1""",
                user_id,
            )
            if mem:
                tenant_id = str(mem["tenant_id"])
                tenant_role = mem["role"]
                tenant_plan = mem["plan_tier"]

    return CurrentUser(
        user_id=str(user_row["id"]),
        email=user_row["email"],
        name=user_row["name"],
        role=user_row["role"],
        tenant_id=tenant_id,
        tenant_plan=tenant_plan,
        tenant_role=tenant_role,
        email_verified=bool(user_row["email_verified"]),
    )


async def get_optional_user(
    request: Request,
    authorization: Annotated[Optional[str], Header()] = None,
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-Id")] = None,
) -> Optional[CurrentUser]:
    """Auth opsiyonel — public endpoint'lerde tier kontrolü için."""
    if not authorization:
        return None
    try:
        return await get_current_user(request, authorization, x_tenant_id)
    except HTTPException:
        return None


def require_plan(min_tier: str):
    """Plan tier guard. Kullanım:

        @router.post("/pro-feature", dependencies=[Depends(require_plan("pro_solo"))])
    """
    TIER_ORDER = {
        "free": 0,
        "pro_solo": 1,
        "pro_solo_uyap": 2,
        "team": 3,
        "team_uyap": 4,
        "enterprise": 5,
    }
    required = TIER_ORDER.get(min_tier, 99)

    async def check(user: CurrentUser = Depends(get_current_user)):
        current = TIER_ORDER.get(user.tenant_plan or "free", 0)
        if current < required:
            raise HTTPException(
                402,
                f"Bu özellik için {min_tier} planı gerekli. Yükseltme: /app/ayarlar/abonelik",
            )
        return user

    return check


def require_uyap(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """UYAP modülü gerektiren endpoint'ler için."""
    UYAP_PLANS = {"pro_solo_uyap", "team_uyap", "enterprise"}
    if (user.tenant_plan or "free") not in UYAP_PLANS:
        raise HTTPException(
            402,
            "UYAP entegrasyonu sadece UYAP eklentili pakette mevcut. "
            "Yükseltme: /app/ayarlar/abonelik",
        )
    return user
