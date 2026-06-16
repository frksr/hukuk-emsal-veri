"""Kullanıcı notları router — kişisel çalışma alanı.

CRUD + bağlamsal eşleştirme (/ilgili): bir araç sayfasındaki konuya/sorguya uyan
notları 'hatırlatma' olarak göstermek için kullanılır.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user, CurrentUser
from api.db import db_session
from api.schemas import APIResponse

log = logging.getLogger("api.notlar")
router = APIRouter()


class NotIstegi(BaseModel):
    baslik: str | None = Field(default=None, max_length=300)
    icerik: str = Field(..., min_length=1, max_length=20000)
    etiketler: list[str] = Field(default_factory=list)
    pinned: bool = False


def _row(r) -> dict:
    return {
        "id": str(r["id"]),
        "baslik": r["baslik"],
        "icerik": r["icerik"],
        "etiketler": list(r["etiketler"]) if r["etiketler"] else [],
        "pinned": bool(r["pinned"]),
        "created_at": r["created_at"].isoformat(),
        "updated_at": r["updated_at"].isoformat(),
    }


def _temiz_etiket(etiketler: list[str]) -> list[str]:
    out, seen = [], set()
    for e in etiketler or []:
        e = (e or "").strip().lower()
        if e and e not in seen:
            seen.add(e)
            out.append(e)
    return out[:20]


@router.get("/", response_model=APIResponse, summary="Notları listele")
async def list_notes(user: CurrentUser = Depends(get_current_user), limit: int = 200):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT * FROM user_notes WHERE user_id = $1
               ORDER BY pinned DESC, updated_at DESC LIMIT $2""",
            user.user_id, min(limit, 500),
        )
    return APIResponse(ok=True, data={"notlar": [_row(r) for r in rows]})


@router.get("/ilgili", response_model=APIResponse, summary="Konuyla ilgili notlar (bağlamsal ipucu)")
async def ilgili_notlar(q: str, user: CurrentUser = Depends(get_current_user), limit: int = 5):
    """Sorgu/konu metniyle eşleşen notları döndürür (etiket kesişimi veya içerik araması)."""
    kelimeler = [w for w in (q or "").lower().replace(",", " ").split() if len(w) >= 3][:8]
    if not kelimeler:
        return APIResponse(ok=True, data={"notlar": []})
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT * FROM user_notes
               WHERE user_id = $1
                 AND ( etiketler && $2::text[] OR icerik ILIKE ANY($3::text[]) )
               ORDER BY pinned DESC, updated_at DESC LIMIT $4""",
            user.user_id,
            kelimeler,
            [f"%{w}%" for w in kelimeler],
            min(limit, 20),
        )
    return APIResponse(ok=True, data={"notlar": [_row(r) for r in rows]})


@router.post("/", response_model=APIResponse, summary="Not oluştur")
async def create_note(istek: NotIstegi, user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        r = await conn.fetchrow(
            """INSERT INTO user_notes (user_id, tenant_id, baslik, icerik, etiketler, pinned)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            user.user_id, user.tenant_id, istek.baslik, istek.icerik,
            _temiz_etiket(istek.etiketler), istek.pinned,
        )
    return APIResponse(ok=True, data=_row(r))


@router.patch("/{not_id}", response_model=APIResponse, summary="Notu güncelle")
async def update_note(not_id: str, istek: NotIstegi, user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        r = await conn.fetchrow(
            """UPDATE user_notes
               SET baslik = $2, icerik = $3, etiketler = $4, pinned = $5, updated_at = NOW()
               WHERE id = $1 RETURNING *""",
            not_id, istek.baslik, istek.icerik, _temiz_etiket(istek.etiketler), istek.pinned,
        )
    if not r:
        raise HTTPException(404, "Not bulunamadı.")
    return APIResponse(ok=True, data=_row(r))


@router.delete("/{not_id}", response_model=APIResponse, summary="Notu sil")
async def delete_note(not_id: str, user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        await conn.execute("DELETE FROM user_notes WHERE id = $1", not_id)
    return APIResponse(ok=True, data={"ok": True})
