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


# --- E-posta doğrulama: 6 haneli KOD (birincil) + tek-tık LİNK (yedek) ---------
import hashlib

CODE_EXPIRE_MINUTES = 10        # kod kısa ömürlü (best practice)
MAX_CODE_ATTEMPTS = 5           # brute-force koruması: 5 yanlış → kod iptal
RESEND_COOLDOWN_SECONDS = 60    # spam koruması: gönderimler arası bekleme
DAILY_SEND_CAP = 10             # 24 saatte azami gönderim


def _gen_code() -> str:
    """Kriptografik güvenli 6 haneli kod (000000–999999)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


async def _kod_olustur_gonder(conn, user_id: str, email: str, name) -> None:
    """Doğrulama kaydı oluşturur (hash'li kod + link token) ve e-posta gönderir.

    Cooldown ve günlük tavanı uygular. RuntimeError fırlatırsa çağıran 429 döner.
    """
    from services.email import send_verification_email

    now = datetime.now(timezone.utc)
    son = await conn.fetchrow(
        """SELECT created_at FROM email_verifications
           WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1""",
        user_id,
    )
    if son and (now - son["created_at"]).total_seconds() < RESEND_COOLDOWN_SECONDS:
        raise RuntimeError("cooldown")
    gunluk = await conn.fetchval(
        """SELECT COUNT(*) FROM email_verifications
           WHERE user_id = $1 AND created_at > $2""",
        user_id, now - timedelta(hours=24),
    )
    if int(gunluk or 0) >= DAILY_SEND_CAP:
        raise RuntimeError("daily_cap")

    code = _gen_code()
    link_token = _token()
    expires = now + timedelta(minutes=CODE_EXPIRE_MINUTES)
    # Önceki bekleyen (kullanılmamış) kodları geçersiz kıl.
    await conn.execute(
        "UPDATE email_verifications SET consumed_at = NOW() "
        "WHERE user_id = $1 AND consumed_at IS NULL",
        user_id,
    )
    await conn.execute(
        """INSERT INTO email_verifications
           (user_id, email, code_hash, link_token, expires_at)
           VALUES ($1, $2, $3, $4, $5)""",
        user_id, email, _hash_code(code), link_token, expires,
    )
    await send_verification_email(
        email, name, code, token=link_token, expires_minutes=CODE_EXPIRE_MINUTES,
    )


@router.post("/send-code", response_model=APIResponse)
async def send_code(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Giriş yapmış kullanıcıya 6 haneli doğrulama kodu (+ link) gönderir."""
    async with service_session() as conn:
        verified = await conn.fetchval(
            "SELECT email_verified IS NOT NULL FROM users WHERE id = $1",
            user.user_id,
        )
        if verified:
            return APIResponse(ok=True, message="E-postanız zaten doğrulanmış.")
        try:
            await _kod_olustur_gonder(conn, user.user_id, user.email, user.name)
        except RuntimeError as e:
            if str(e) == "cooldown":
                raise HTTPException(429, "Çok sık talep ettiniz. Lütfen biraz bekleyin.")
            raise HTTPException(429, "Günlük doğrulama e-postası sınırına ulaşıldı.")

    await audit(action="email.code_sent", user_id=user.user_id, request=request)
    return APIResponse(ok=True, message="Doğrulama kodu e-postanıza gönderildi.")


# Geriye dönük uyum: eski "resend-verification" çağrıları send-code gibi davranır.
@router.post("/resend-verification", response_model=APIResponse)
async def resend_verification(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    return await send_code(request, user)


class VerifyCodeReq(BaseModel):
    code: str = Field(min_length=6, max_length=6)


@router.post("/verify-code", response_model=APIResponse)
async def verify_code(
    payload: VerifyCodeReq,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Kullanıcının girdiği 6 haneli kodu doğrular."""
    kod = payload.code.strip()
    if not kod.isdigit() or len(kod) != 6:
        raise HTTPException(400, "Kod 6 haneli olmalı.")

    async with service_session() as conn:
        already = await conn.fetchval(
            "SELECT email_verified IS NOT NULL FROM users WHERE id = $1", user.user_id,
        )
        if already:
            return APIResponse(ok=True, message="E-postanız zaten doğrulanmış.")

        row = await conn.fetchrow(
            """SELECT id, code_hash, expires_at, attempts FROM email_verifications
               WHERE user_id = $1 AND consumed_at IS NULL
               ORDER BY created_at DESC LIMIT 1""",
            user.user_id,
        )
        if not row:
            raise HTTPException(400, "Aktif kod yok. Yeni kod isteyin.")
        if row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(400, "Kodun süresi doldu. Yeni kod isteyin.")
        if row["attempts"] >= MAX_CODE_ATTEMPTS:
            await conn.execute(
                "UPDATE email_verifications SET consumed_at = NOW() WHERE id = $1",
                row["id"],
            )
            raise HTTPException(429, "Çok fazla hatalı deneme. Yeni kod isteyin.")

        # Sabit-zamanlı karşılaştırma (timing attack koruması).
        if not secrets.compare_digest(row["code_hash"], _hash_code(kod)):
            await conn.execute(
                "UPDATE email_verifications SET attempts = attempts + 1 WHERE id = $1",
                row["id"],
            )
            kalan = MAX_CODE_ATTEMPTS - (row["attempts"] + 1)
            await audit(action="email.verify_failed", user_id=user.user_id,
                        request=request, success=False)
            raise HTTPException(
                400,
                f"Kod hatalı. {kalan} deneme hakkınız kaldı." if kalan > 0
                else "Kod hatalı. Yeni kod isteyin.",
            )

        async with conn.transaction():
            await conn.execute(
                "UPDATE users SET email_verified = NOW() WHERE id = $1", user.user_id,
            )
            await conn.execute(
                "UPDATE email_verifications SET consumed_at = NOW() WHERE id = $1",
                row["id"],
            )

    await audit(action="email.verified", user_id=user.user_id, request=request)
    return APIResponse(ok=True, message="E-posta doğrulandı.")


class VerifyEmailReq(BaseModel):
    token: str


@router.post("/verify-email", response_model=APIResponse)
async def verify_email(payload: VerifyEmailReq, request: Request):
    """Tek-tık link ile doğrulama (e-postadaki 'Tek Tıkla Doğrula' butonu)."""
    async with service_session() as conn:
        row = await conn.fetchrow(
            """SELECT id, user_id, email, expires_at, consumed_at
               FROM email_verifications WHERE link_token = $1""",
            payload.token,
        )
        if not row:
            raise HTTPException(400, "Geçersiz doğrulama bağlantısı.")
        if row["consumed_at"]:
            # Zaten doğrulanmışsa kullanıcıyı bilgilendir (link tekrar tıklandı).
            verified = await conn.fetchval(
                "SELECT email_verified IS NOT NULL FROM users WHERE id = $1",
                row["user_id"],
            )
            if verified:
                return APIResponse(ok=True, message="E-postanız zaten doğrulanmış.")
            raise HTTPException(400, "Bu bağlantı kullanılmış. Yeni kod isteyin.")
        if row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(400, "Bağlantı süresi dolmuş. Yeni kod isteyin.")

        async with conn.transaction():
            await conn.execute(
                "UPDATE users SET email_verified = NOW() WHERE id = $1", row["user_id"],
            )
            await conn.execute(
                "UPDATE email_verifications SET consumed_at = NOW() WHERE id = $1",
                row["id"],
            )

    await audit(action="email.verified", user_id=str(row["user_id"]), request=request,
                metadata={"via": "link"})
    return APIResponse(ok=True, message="E-posta doğrulandı.")


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
