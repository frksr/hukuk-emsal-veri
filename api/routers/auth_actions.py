"""Auth ile ilgili stateful action'lar (verify, password reset, change password).

NOT: Login/logout NextAuth tarafında (Next.js'te). Buradakiler backend-side
state management gereken işlemler.
"""
from __future__ import annotations
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from api.audit import audit
from api.auth import CurrentUser, get_current_user
from api.db import service_session
from api.schemas import APIResponse

router = APIRouter()

VERIFICATION_TOKEN_HOURS = 24
PASSWORD_RESET_TOKEN_HOURS = 1


def _token() -> str:
    return secrets.token_urlsafe(32)


class ForgotPasswordReq(BaseModel):
    email: EmailStr


@router.post("/forgot-password", response_model=APIResponse)
async def forgot_password(payload: ForgotPasswordReq, request: Request):
    """Şifre sıfırlama e-postası gönder. Her zaman aynı yanıt (enumeration koruma)."""
    from services.email import send_password_reset_email

    async with service_session() as conn:
        user = await conn.fetchrow(
            "SELECT id, name FROM users WHERE email = $1 AND is_active = TRUE",
            payload.email,
        )
        if user:
            token = _token()
            expires = datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_TOKEN_HOURS)
            await conn.execute(
                """INSERT INTO password_resets (user_id, token, expires_at)
                   VALUES ($1, $2, $3)""",
                user["id"], token, expires,
            )
            await send_password_reset_email(payload.email, user["name"], token)
            await audit(
                action="password.reset_requested",
                user_id=str(user["id"]),
                request=request,
                metadata={"email": payload.email},
            )

    # Her zaman aynı yanıt — enumeration attack'a karşı
    return APIResponse(
        ok=True,
        message="Eğer bu e-posta sistemimize kayıtlıysa, sıfırlama bağlantısı gönderildi.",
    )


class ResetPasswordReq(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/reset-password", response_model=APIResponse)
async def reset_password(payload: ResetPasswordReq, request: Request):
    """Token ile yeni şifre belirle."""
    async with service_session() as conn:
        reset_row = await conn.fetchrow(
            """SELECT pr.id, pr.user_id, pr.expires_at, pr.used_at, u.email
               FROM password_resets pr
               JOIN users u ON u.id = pr.user_id
               WHERE pr.token = $1""",
            payload.token,
        )
        if not reset_row:
            raise HTTPException(400, "Geçersiz veya kullanılmış bağlantı.")
        if reset_row["used_at"]:
            raise HTTPException(400, "Bu bağlantı daha önce kullanılmış.")
        if reset_row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(400, "Bağlantı süresi dolmuş. Yeniden talep edin.")

        new_hash = bcrypt.hashpw(payload.new_password.encode(), bcrypt.gensalt(12)).decode()
        async with conn.transaction():
            await conn.execute(
                "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2",
                new_hash, reset_row["user_id"],
            )
            await conn.execute(
                "UPDATE password_resets SET used_at = NOW() WHERE id = $1",
                reset_row["id"],
            )
            # Tüm mevcut session'ları geçersiz kıl
            await conn.execute(
                "DELETE FROM sessions WHERE user_id = $1",
                reset_row["user_id"],
            )

    await audit(
        action="password.reset_completed",
        user_id=str(reset_row["user_id"]),
        request=request,
    )
    return APIResponse(ok=True, message="Şifre güncellendi. Yeniden giriş yapabilirsiniz.")


class VerifyEmailReq(BaseModel):
    token: str


@router.post("/verify-email", response_model=APIResponse)
async def verify_email(payload: VerifyEmailReq, request: Request):
    async with service_session() as conn:
        row = await conn.fetchrow(
            """SELECT identifier, expires FROM verification_tokens WHERE token = $1""",
            payload.token,
        )
        if not row:
            raise HTTPException(400, "Geçersiz doğrulama bağlantısı.")
        if row["expires"] < datetime.now(timezone.utc):
            raise HTTPException(400, "Bağlantı süresi dolmuş. Yeniden talep edin.")

        async with conn.transaction():
            await conn.execute(
                "UPDATE users SET email_verified = NOW() WHERE email = $1",
                row["identifier"],
            )
            await conn.execute(
                "DELETE FROM verification_tokens WHERE token = $1",
                payload.token,
            )

    await audit(action="email.verified", request=request, metadata={"email": row["identifier"]})
    return APIResponse(ok=True, message="E-posta doğrulandı.")


@router.post("/resend-verification", response_model=APIResponse)
async def resend_verification(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    from services.email import send_verification_email

    async with service_session() as conn:
        verified = await conn.fetchval(
            "SELECT email_verified IS NOT NULL FROM users WHERE id = $1",
            user.user_id,
        )
        if verified:
            return APIResponse(ok=True, message="E-postanız zaten doğrulanmış.")

        # Eski tokenları temizle, yenisini at
        await conn.execute(
            "DELETE FROM verification_tokens WHERE identifier = $1",
            user.email,
        )
        token = _token()
        expires = datetime.now(timezone.utc) + timedelta(hours=VERIFICATION_TOKEN_HOURS)
        await conn.execute(
            """INSERT INTO verification_tokens (identifier, token, expires)
               VALUES ($1, $2, $3)""",
            user.email, token, expires,
        )

    await send_verification_email(user.email, user.name, token)
    await audit(
        action="email.verification_resent",
        user_id=user.user_id,
        request=request,
    )
    return APIResponse(ok=True, message="Doğrulama e-postası gönderildi.")


class ChangePasswordReq(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/change-password", response_model=APIResponse)
async def change_password(
    payload: ChangePasswordReq,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Mevcut şifre ile yeni şifre belirle (oturum açıkken)."""
    async with service_session() as conn:
        row = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1",
            user.user_id,
        )
        if not row or not row["password_hash"]:
            raise HTTPException(400, "Bu hesap için şifre değişimi mevcut değil.")
        if not bcrypt.checkpw(payload.current_password.encode(), row["password_hash"].encode()):
            await audit(
                action="password.change_failed",
                user_id=user.user_id,
                request=request,
                success=False,
            )
            raise HTTPException(400, "Mevcut şifre hatalı.")

        new_hash = bcrypt.hashpw(payload.new_password.encode(), bcrypt.gensalt(12)).decode()
        await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2",
            new_hash, user.user_id,
        )

    await audit(action="password.changed", user_id=user.user_id, request=request)
    return APIResponse(ok=True, message="Şifre güncellendi.")
