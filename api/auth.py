"""Auth + tenant context middleware.

NextAuth.js JWT'sini doğrular, kullanıcıyı + aktif tenant'ı çözer.

Frontend tarafı:
  Next.js her isteğe `Authorization: Bearer <NEXTAUTH_JWT>` ekliyor.
  JWT, NEXTAUTH_SECRET ile imzalı; backend aynı secret ile verify ediyor.

UYAP tarayıcı eklentisi tarafı:
  Eklenti, Next.js'in oturum cookie'sine erişemez (httpOnly + farklı origin,
  chrome-extension://...). Bunun yerine panelden üretilen, `uyapext_` önekli
  bir kişisel erişim anahtarı kullanır (bkz. api/routers/extension.py). Bu
  token'lar NEXTAUTH_SECRET ile imzalı DEĞİLDİR — DB'de sha256 hash'i olarak
  saklanır ve burada prefix'ine bakılarak JWT yolundan ayrıştırılır.
"""
from __future__ import annotations
import hashlib
import os
from typing import Annotated, Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request

from api.db import service_session

EXTENSION_TOKEN_PREFIX = "uyapext_"


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
        restricted: bool = False,
    ):
        self.user_id = user_id
        self.email = email
        self.name = name
        self.role = role
        self.tenant_id = tenant_id
        self.tenant_plan = tenant_plan
        self.tenant_role = tenant_role
        self.email_verified = email_verified
        # Admin panelden "kısıtla" ile işaretlenmiş hesap — askıya alma (is_active)
        # kadar sert değil: giriş yapabilir, verilerini görebilir ama kredi
        # tüketen modülleri (AI üretim, emsal arama) kullanamaz (bkz. api/kota.py).
        self.restricted = restricted


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


async def _resolve_extension_token(token: str) -> Optional[CurrentUser]:
    """`uyapext_...` token'ını doğrular. Geçersiz/iptal edilmişse None döner."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    async with service_session() as conn:
        row = await conn.fetchrow(
            """SELECT et.id AS token_id, u.id AS user_id, u.email, u.name, u.role,
                      u.is_active, u.email_verified, u.restricted_at,
                      t.id AS tenant_id, t.plan_tier, t.is_active AS tenant_active,
                      tm.role AS tenant_role
               FROM extension_tokens et
               JOIN users u ON u.id = et.user_id
               JOIN tenants t ON t.id = et.tenant_id
               LEFT JOIN tenant_members tm ON tm.tenant_id = et.tenant_id AND tm.user_id = et.user_id
               WHERE et.token_hash = $1 AND et.revoked_at IS NULL""",
            token_hash,
        )
        if not row or not row["is_active"] or not row["tenant_active"]:
            return None
        await conn.execute(
            "UPDATE extension_tokens SET last_used_at = NOW() WHERE id = $1",
            row["token_id"],
        )
    return CurrentUser(
        user_id=str(row["user_id"]),
        email=row["email"],
        name=row["name"],
        role=row["role"],
        tenant_id=str(row["tenant_id"]),
        tenant_plan=row["plan_tier"],
        tenant_role=row["tenant_role"] or "member",
        email_verified=bool(row["email_verified"]),
        restricted=bool(row["restricted_at"]),
    )


async def get_current_user(
    request: Request,
    authorization: Annotated[Optional[str], Header()] = None,
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-Id")] = None,
) -> CurrentUser:
    """Auth zorunlu endpoint'ler için dependency."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Yetkilendirme gerekli.")

    token = authorization.split(" ", 1)[1].strip()

    if token.startswith(EXTENSION_TOKEN_PREFIX):
        ext_user = await _resolve_extension_token(token)
        if not ext_user:
            raise HTTPException(401, "Geçersiz veya iptal edilmiş eklenti anahtarı.")
        return ext_user

    payload = _decode_jwt(token)

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(401, "Token geçersiz.")

    # Auth bootstrap: kullanıcı + tenant üyeliklerini context OLUŞMADAN ÖNCE
    # çözmek gerekir (kim olduğunu burada belirliyoruz) → service_session.
    async with service_session() as conn:
        user_row = await conn.fetchrow(
            "SELECT id, email, name, role, is_active, email_verified, restricted_at "
            "FROM users WHERE id = $1",
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
            # Birincil tenant üyeliğini bul — owner rolü önce, sonra en eski üyelik.
            # NOT: admin panelin kullanıcı listesi de AYNI kuralla (owner önce,
            # sonra en eski) "birincil tenant"ı seçiyor (bkz. admin.py list_users).
            # Burada sadece "en eski üyelik" kullanılsaydı, birden fazla tenant'a
            # üye bir kullanıcı için admin panelin gösterdiği/güncellediği tenant
            # ile bu kullanıcının OTURUMUNUN bağlı olduğu tenant FARKLI olabilirdi
            # — admin planı değiştirir ama kullanıcı hep başka bir tenant'ın
            # planını görür (kullanıcı panelinde hiç değişmiyormuş gibi görünür).
            mem = await conn.fetchrow(
                """SELECT tm.tenant_id, tm.role, t.plan_tier FROM tenant_members tm
                   JOIN tenants t ON t.id = tm.tenant_id
                   WHERE tm.user_id = $1 AND t.is_active = TRUE
                   ORDER BY (tm.role = 'owner') DESC, tm.created_at ASC LIMIT 1""",
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
        restricted=bool(user_row["restricted_at"]),
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
                f"Bu özellik için {min_tier} planı gerekli. Yükseltme: /panel/ayarlar/abonelik",
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
            "Yükseltme: /panel/ayarlar/abonelik",
        )
    return user


def require_role(*roles: str):
    """Belirtilen rollerden birine sahip olmayı zorunlu kılan dependency üretir.

    Örn: `Depends(require_role("admin", "editor"))`
    """
    allowed = set(roles)

    def check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(
                403, "Bu işlem için yetkiniz yok."
            )
        return user

    return check


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Yalnızca admin. Eskiden bu fonksiyon admin.py, icerik.py, newsletter.py ve
    waitlist.py'de birebir kopyalanmıştı; ileride ek bir koruma katmanı (MFA,
    IP allowlist, ek audit) gerektiğinde dört dosyanın senkron güncellenmesi
    gerekiyordu. Tek kaynağa taşındı."""
    if user.role != "admin":
        raise HTTPException(403, "Bu işlem yalnızca admin kullanıcılara açık.")
    return user
