"""Public API v1 — API key ile programatik erişim (enterprise/entegrasyon).

Auth: `X-API-Key: he_live_...` header'ı.
Kota: anahtar başına günlük limit (api_keys.daily_quota), api_key_usage'da sayılır.

Pilot kapsam: emsal arama. Diğer endpoint'ler (dilekçe, özet) talebe göre açılır.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException

from api.concurrency import run_blocking
from api.db import service_session
from api.schemas import APIResponse, AramaIstegi, EmsalKarar
from services.rag import search

log = logging.getLogger("api.v1")
router = APIRouter()


class ApiKeyContext:
    def __init__(self, key_id: str, user_id: str, daily_quota: int):
        self.key_id = key_id
        self.user_id = user_id
        self.daily_quota = daily_quota


async def require_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> ApiKeyContext:
    """API anahtarını doğrula + günlük kotayı düş."""
    if not x_api_key or not x_api_key.startswith("he_"):
        raise HTTPException(401, "X-API-Key header'ı gerekli.")

    key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
    async with service_session() as conn:
        row = await conn.fetchrow(
            """SELECT id, user_id, daily_quota FROM api_keys
               WHERE key_hash = $1 AND aktif = TRUE""",
            key_hash,
        )
        if not row:
            raise HTTPException(401, "Geçersiz veya iptal edilmiş API anahtarı.")

        # Günlük kota — atomik upsert + kontrol
        usage = await conn.fetchrow(
            """INSERT INTO api_key_usage (key_id, gun, adet)
               VALUES ($1, $2, 1)
               ON CONFLICT (key_id, gun) DO UPDATE SET adet = api_key_usage.adet + 1
               RETURNING adet""",
            row["id"], date.today(),
        )
        if usage["adet"] > row["daily_quota"]:
            raise HTTPException(
                429,
                f"Günlük API kotası aşıldı ({row['daily_quota']} istek/gün). "
                "Limit artışı için satis@hukukcuyapayzekasi.com",
            )
        await conn.execute(
            "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1", row["id"])

    return ApiKeyContext(str(row["id"]), str(row["user_id"]), row["daily_quota"])


@router.post("/arama", response_model=APIResponse,
             summary="Emsal karar ara (API key ile)")
async def v1_arama(
    istek: AramaIstegi,
    ctx: ApiKeyContext = Depends(require_api_key),
) -> APIResponse:
    """RAG tabanlı emsal arama — web arayüzüyle aynı motor."""
    where = None
    f = {}
    if istek.source:
        f["source"] = istek.source
    if istek.court_chamber:
        f["court_chamber"] = istek.court_chamber
    if len(f) == 1:
        where = f
    elif len(f) > 1:
        where = {"$and": [{k: v} for k, v in f.items()]}

    try:
        ham = await run_blocking(search, istek.query, k=istek.k, where=where)
    except Exception as e:
        log.exception("v1 arama hatası")
        raise HTTPException(500, f"Arama başarısız: {e}")

    sonuc = []
    for it in ham:
        meta = it.get("meta") or {}
        sonuc.append({
            "chunk_id": str(it.get("chunk_id", "")),
            "text": it.get("text", ""),
            "similarity": float(it.get("similarity", 0) or 0),
            "decision_id": meta.get("id") or meta.get("decision_id"),
            "source": meta.get("source"),
            "court_chamber": meta.get("court_chamber"),
            "case_no": meta.get("case_no"),
            "decision_no": meta.get("decision_no"),
            "decision_date": meta.get("decision_date"),
        })
    return APIResponse(ok=True, data=sonuc, message=f"{len(sonuc)} sonuç")
