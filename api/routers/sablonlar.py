"""Dilekçe şablon kütüphanesi — platform şablonları + kullanıcının kendi şablonları.

Platform şablonları (user_id IS NULL) herkese açık ve salt okunur; kullanıcı
kendi şablonlarını oluşturup düzenleyebilir. /{id}/uygula, {{degisken}}
placeholder'larını verilen değerlerle doldurup metni döndürür.
"""
from __future__ import annotations
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import CurrentUser, get_current_user
from api.db import db_session
from api.schemas import APIResponse

log = logging.getLogger("api.sablonlar")
router = APIRouter()

_DEGISKEN = re.compile(r"\{\{(\w+)\}\}")


def _satir(r) -> dict:
    degiskenler = r["degiskenler"]
    if isinstance(degiskenler, str):
        try:
            degiskenler = json.loads(degiskenler)
        except Exception:
            degiskenler = []
    return {
        "id": str(r["id"]),
        "baslik": r["baslik"],
        "kategori": r["kategori"],
        "icerik": r["icerik"],
        "degiskenler": degiskenler,
        "platform": r["user_id"] is None,
        "created_at": r["created_at"].isoformat(),
        "updated_at": r["updated_at"].isoformat(),
    }


@router.get("/", response_model=APIResponse)
async def listele(
    kategori: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """Platform şablonları + kullanıcının kendi şablonları (RLS bunu garanti eder)."""
    where = "WHERE (user_id IS NULL OR user_id = $1)"
    args: list = [user.user_id]
    if kategori:
        args.append(kategori)
        where += f" AND kategori = ${len(args)}"
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            f"""SELECT id, user_id, baslik, kategori, icerik, degiskenler,
                       created_at, updated_at
                FROM dilekce_sablonlari {where}
                ORDER BY (user_id IS NULL) DESC, kategori, baslik""",
            *args,
        )
    return APIResponse(ok=True, data={"sablonlar": [_satir(r) for r in rows]})


class SablonReq(BaseModel):
    baslik: str = Field(min_length=3, max_length=200)
    kategori: str = Field(default="genel", max_length=50)
    icerik: str = Field(min_length=20, max_length=50_000)


@router.post("/", response_model=APIResponse)
async def olustur(payload: SablonReq, user: CurrentUser = Depends(get_current_user)):
    """Kullanıcının kendi şablonu. Değişkenler içerikten otomatik çıkarılır."""
    degiskenler = sorted(set(_DEGISKEN.findall(payload.icerik)))
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO dilekce_sablonlari
               (user_id, tenant_id, baslik, kategori, icerik, degiskenler)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb)
               RETURNING id, user_id, baslik, kategori, icerik, degiskenler,
                         created_at, updated_at""",
            user.user_id, user.tenant_id, payload.baslik, payload.kategori,
            payload.icerik, json.dumps(degiskenler),
        )
    return APIResponse(ok=True, data=_satir(row), message="Şablon kaydedildi.")


class SablonPatchReq(BaseModel):
    baslik: str | None = Field(default=None, min_length=3, max_length=200)
    kategori: str | None = Field(default=None, max_length=50)
    icerik: str | None = Field(default=None, min_length=20, max_length=50_000)


@router.patch("/{sablon_id}", response_model=APIResponse)
async def guncelle(
    sablon_id: str,
    payload: SablonPatchReq,
    user: CurrentUser = Depends(get_current_user),
):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        mevcut = await conn.fetchrow(
            "SELECT id, user_id, icerik FROM dilekce_sablonlari WHERE id = $1::uuid",
            sablon_id,
        )
        if not mevcut:
            raise HTTPException(404, "Şablon bulunamadı.")
        if mevcut["user_id"] is None:
            raise HTTPException(403, "Platform şablonları düzenlenemez; kopyalayıp kendi şablonunuzu oluşturun.")

        icerik = payload.icerik if payload.icerik is not None else mevcut["icerik"]
        degiskenler = sorted(set(_DEGISKEN.findall(icerik)))
        row = await conn.fetchrow(
            """UPDATE dilekce_sablonlari
               SET baslik = COALESCE($2, baslik),
                   kategori = COALESCE($3, kategori),
                   icerik = $4,
                   degiskenler = $5::jsonb,
                   updated_at = NOW()
               WHERE id = $1::uuid
               RETURNING id, user_id, baslik, kategori, icerik, degiskenler,
                         created_at, updated_at""",
            sablon_id, payload.baslik, payload.kategori, icerik,
            json.dumps(degiskenler),
        )
    return APIResponse(ok=True, data=_satir(row), message="Şablon güncellendi.")


@router.delete("/{sablon_id}", response_model=APIResponse)
async def sil(sablon_id: str, user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        mevcut = await conn.fetchrow(
            "SELECT user_id FROM dilekce_sablonlari WHERE id = $1::uuid", sablon_id,
        )
        if not mevcut:
            raise HTTPException(404, "Şablon bulunamadı.")
        if mevcut["user_id"] is None:
            raise HTTPException(403, "Platform şablonları silinemez.")
        await conn.execute(
            "DELETE FROM dilekce_sablonlari WHERE id = $1::uuid", sablon_id,
        )
    return APIResponse(ok=True, message="Şablon silindi.")


class UygulaReq(BaseModel):
    degerler: dict[str, str] = Field(default_factory=dict)


@router.post("/{sablon_id}/uygula", response_model=APIResponse)
async def uygula(
    sablon_id: str,
    payload: UygulaReq,
    user: CurrentUser = Depends(get_current_user),
):
    """{{degisken}} placeholder'larını doldur; verilmeyenler ______ olur."""
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT icerik FROM dilekce_sablonlari
               WHERE id = $1::uuid AND (user_id IS NULL OR user_id = $2)""",
            sablon_id, user.user_id,
        )
    if not row:
        raise HTTPException(404, "Şablon bulunamadı.")

    def _doldur(m: re.Match) -> str:
        deger = (payload.degerler.get(m.group(1)) or "").strip()
        return deger if deger else "______"

    return APIResponse(ok=True, data={"icerik": _DEGISKEN.sub(_doldur, row["icerik"])})
