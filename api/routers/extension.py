"""UYAP tarayıcı eklentisi için kişisel erişim anahtarı yönetimi.

Eklenti (bkz. extension/) avukatın NextAuth oturumuna erişemediğinden, panelden
üretilen bir "uyapext_..." token'ı kullanır. Bu router yalnızca token
üretme/listeleme/iptal etme uçlarını sağlar — token'ın KENDİSİYLE yapılan
dosya yükleme/listeleme istekleri zaten mevcut /api/uyap/* uçlarından,
api/auth.py'deki extension token doğrulama dalı (_resolve_extension_token)
sayesinde geçer; ayrı upload endpoint'i gerekmez.
"""
from __future__ import annotations
import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from api.audit import audit
from api.auth import CurrentUser, EXTENSION_TOKEN_PREFIX, require_uyap
from api.db import db_session
from api.schemas import APIResponse

log = logging.getLogger("api.extension")
router = APIRouter()

MAX_TOKENS_PER_USER = 5


@router.post("/tokens", response_model=APIResponse)
async def generate_token(
    request: Request,
    user: CurrentUser = Depends(require_uyap),
):
    """Yeni eklenti anahtarı üret.

    Ham token yalnızca BU yanıtta döner ve bir daha gösterilmez (yalnızca
    hash'i saklanır) — kaybedilirse yenisi üretilip eskisi iptal edilmelidir.
    """
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        active_count = await conn.fetchval(
            "SELECT COUNT(*) FROM extension_tokens WHERE user_id = $1 AND revoked_at IS NULL",
            user.user_id,
        )
        if active_count >= MAX_TOKENS_PER_USER:
            raise HTTPException(
                400,
                f"En fazla {MAX_TOKENS_PER_USER} aktif eklenti anahtarınız olabilir. "
                "Kullanmadığınız bir anahtarı iptal edip tekrar deneyin.",
            )

        raw_token = f"{EXTENSION_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        row = await conn.fetchrow(
            """INSERT INTO extension_tokens (tenant_id, user_id, name, token_hash, token_prefix)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING id, created_at""",
            user.tenant_id, user.user_id, "UYAP Eklentisi",
            token_hash, raw_token[:20],
        )

    await audit(
        action="extension_token.created",
        user_id=user.user_id, tenant_id=user.tenant_id,
        resource=f"extension_token:{row['id']}", request=request,
    )

    return APIResponse(ok=True, data={
        "id": str(row["id"]),
        "token": raw_token,  # yalnızca bu yanıtta gösterilir
        "created_at": row["created_at"].isoformat(),
    })


@router.get("/tokens", response_model=APIResponse)
async def list_tokens(user: CurrentUser = Depends(require_uyap)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT id, name, token_prefix, last_used_at, created_at, revoked_at
               FROM extension_tokens
               WHERE user_id = $1
               ORDER BY created_at DESC""",
            user.user_id,
        )
    return APIResponse(ok=True, data={
        "tokens": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "prefix": r["token_prefix"],
                "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
                "created_at": r["created_at"].isoformat(),
                "revoked": r["revoked_at"] is not None,
            }
            for r in rows
        ],
    })


@router.delete("/tokens/{token_id}", response_model=APIResponse)
async def revoke_token(
    token_id: str,
    request: Request,
    user: CurrentUser = Depends(require_uyap),
):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT id FROM extension_tokens
               WHERE id = $1::uuid AND user_id = $2 AND revoked_at IS NULL""",
            token_id, user.user_id,
        )
        if not row:
            raise HTTPException(404, "Anahtar bulunamadı veya zaten iptal edilmiş.")
        await conn.execute(
            "UPDATE extension_tokens SET revoked_at = NOW() WHERE id = $1::uuid",
            token_id,
        )

    await audit(
        action="extension_token.revoked",
        user_id=user.user_id, tenant_id=user.tenant_id,
        resource=f"extension_token:{token_id}", request=request,
    )
    return APIResponse(ok=True, message="Anahtar iptal edildi.")
