"""Emsal alarmları — "bu sorguda yeni karar çıkınca e-posta ile haber ver".

Mevcut saved_search_alerts tablosunu (10_saved_decisions.sql) ve
scripts/emsal_alarm_job.py eşleştirme job'ını kullanır; bu router yalnızca
kullanıcı CRUD'unu sağlar. Pro özelliğidir (retention motoru).
"""
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import CurrentUser, get_current_user
from api.db import db_session
from api.schemas import APIResponse

log = logging.getLogger("api.alarmlar")
router = APIRouter()

MAX_ALARM = 10


def _satir(r) -> dict:
    return {
        "id": str(r["id"]),
        "sorgu": r["query"],
        "aktif": r["aktif"],
        "son_kontrol": r["son_kontrol"].isoformat() if r["son_kontrol"] else None,
        "son_bildirim": r["son_bildirim"].isoformat() if r["son_bildirim"] else None,
        "created_at": r["created_at"].isoformat(),
    }


@router.get("/", response_model=APIResponse)
async def listele(user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT id, query, aktif, son_kontrol, son_bildirim, created_at
               FROM saved_search_alerts
               WHERE user_id = $1
               ORDER BY created_at DESC""",
            user.user_id,
        )
    return APIResponse(ok=True, data={
        "alarmlar": [_satir(r) for r in rows],
        "max": MAX_ALARM,
    })


class AlarmReq(BaseModel):
    sorgu: str = Field(min_length=3, max_length=500)


@router.post("/", response_model=APIResponse)
async def olustur(payload: AlarmReq, user: CurrentUser = Depends(get_current_user)):
    sorgu = payload.sorgu.strip()
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        adet = await conn.fetchval(
            "SELECT COUNT(*) FROM saved_search_alerts WHERE user_id = $1",
            user.user_id,
        )
        if int(adet or 0) >= MAX_ALARM:
            raise HTTPException(
                400, f"En fazla {MAX_ALARM} alarm oluşturabilirsiniz. "
                     "Kullanmadığınız bir alarmı silin.",
            )
        mevcut = await conn.fetchval(
            "SELECT 1 FROM saved_search_alerts WHERE user_id = $1 AND query = $2",
            user.user_id, sorgu,
        )
        if mevcut:
            raise HTTPException(400, "Bu sorgu için zaten bir alarmınız var.")
        row = await conn.fetchrow(
            """INSERT INTO saved_search_alerts (user_id, query, aktif)
               VALUES ($1, $2, TRUE)
               RETURNING id, query, aktif, son_kontrol, son_bildirim, created_at""",
            user.user_id, sorgu,
        )
    return APIResponse(
        ok=True, data=_satir(row),
        message="Alarm kuruldu. Bu konuda yeni karar eklendiğinde e-posta göndereceğiz.",
    )


class AlarmPatchReq(BaseModel):
    aktif: bool


@router.patch("/{alarm_id}", response_model=APIResponse)
async def guncelle(
    alarm_id: str,
    payload: AlarmPatchReq,
    user: CurrentUser = Depends(get_current_user),
):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            """UPDATE saved_search_alerts SET aktif = $2
               WHERE id = $1::uuid AND user_id = $3
               RETURNING id, query, aktif, son_kontrol, son_bildirim, created_at""",
            alarm_id, payload.aktif, user.user_id,
        )
    if not row:
        raise HTTPException(404, "Alarm bulunamadı.")
    return APIResponse(ok=True, data=_satir(row))


@router.delete("/{alarm_id}", response_model=APIResponse)
async def sil(alarm_id: str, user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        silinen = await conn.fetchval(
            """DELETE FROM saved_search_alerts
               WHERE id = $1::uuid AND user_id = $2 RETURNING id""",
            alarm_id, user.user_id,
        )
    if not silinen:
        raise HTTPException(404, "Alarm bulunamadı.")
    return APIResponse(ok=True, message="Alarm silindi.")
