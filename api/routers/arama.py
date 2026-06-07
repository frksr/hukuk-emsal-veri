"""Arama (RAG) router — Chroma tabanlı emsal karar arama."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Path, Request

from api.auth import CurrentUser, get_optional_user
from api.db import db_session
from api.rate_limit import rate_limit_for
from api.schemas import APIResponse, AramaIstegi, EmsalKarar
from services.rag import search, get_collection_stats, get_full_decision

log = logging.getLogger("api.arama")
router = APIRouter()


def _to_emsal_karar(item: dict) -> dict:
    """services.rag.search çıktısını EmsalKarar şeması uyumlu dict'e çevirir."""
    meta = item.get("meta") or {}
    return {
        "chunk_id": str(item.get("chunk_id", "")),
        "text": item.get("text", "") or "",
        "similarity": float(item.get("similarity", 0.0) or 0.0),
        "decision_id": meta.get("id") or meta.get("decision_id"),
        "source": meta.get("source") or meta.get("kaynak"),
        "court_chamber": meta.get("court_chamber") or meta.get("mahkeme") or meta.get("daire"),
        "case_no": meta.get("case_no") or meta.get("esas_no") or meta.get("esas"),
        "decision_no": meta.get("decision_no") or meta.get("karar_no") or meta.get("karar"),
        "decision_date": meta.get("decision_date") or meta.get("karar_tarihi") or meta.get("tarih"),
        "topic_tags": meta.get("topic_tags"),
        "source_url": meta.get("source_url") or meta.get("url"),
    }


@router.post("/", response_model=APIResponse, summary="RAG ile emsal karar ara")
async def arama_yap(
    istek: AramaIstegi,
    request: Request,
    user: CurrentUser | None = Depends(get_optional_user),
    _=Depends(rate_limit_for("arama")),
) -> APIResponse:
    """Verilen sorgu için top-k emsal karar döndürür.

    Filtreleme: `source` (yargitay/danistay/aym) ve `court_chamber` (daire) opsiyonel.
    Auth opsiyonel — giriş yapmış kullanıcılarda günlük limit artar ve geçmiş kaydedilir.
    """
    where: dict | None = None
    filtreler: dict = {}
    if istek.source:
        filtreler["source"] = istek.source
    if istek.court_chamber:
        filtreler["court_chamber"] = istek.court_chamber
    if filtreler:
        if len(filtreler) == 1:
            where = filtreler
        else:
            where = {"$and": [{k: v} for k, v in filtreler.items()]}

    try:
        ham = search(istek.query, k=istek.k, where=where)
    except Exception as e:
        log.exception("RAG araması başarısız")
        raise HTTPException(status_code=500, detail=f"Arama başarısız: {e}")

    karar_list = [_to_emsal_karar(it) for it in ham]
    try:
        validated = [EmsalKarar(**k).model_dump() for k in karar_list]
    except Exception:
        validated = karar_list

    # Geçmişe kaydet (kayıtlı kullanıcı için)
    if user:
        try:
            import json
            async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
                await conn.execute(
                    """INSERT INTO user_searches (user_id, query, result_count, filters)
                       VALUES ($1, $2, $3, $4::jsonb)""",
                    user.user_id, istek.query, len(validated),
                    json.dumps(filtreler),
                )
        except Exception as e:
            log.warning(f"Arama geçmişi kaydedilemedi: {e}")

    return APIResponse(ok=True, data=validated, message=f"{len(validated)} sonuç")


@router.get("/stats", response_model=APIResponse, summary="Koleksiyon istatistikleri")
async def stats() -> APIResponse:
    """Chroma koleksiyonundaki chunk sayısı ve hazır olma durumu."""
    try:
        s = get_collection_stats()
    except Exception as e:
        log.exception("Stats hatası")
        raise HTTPException(status_code=500, detail=str(e))
    return APIResponse(ok=bool(s.get("available", False)), data=s)


@router.get("/full/{decision_id}", response_model=APIResponse,
            summary="Tam karar metni")
async def full_karar(
    decision_id: str = Path(..., min_length=1, max_length=200),
) -> APIResponse:
    """Parquet'ten verilen decision_id için tam karar metnini çeker."""
    try:
        karar = get_full_decision(decision_id)
    except Exception as e:
        log.exception("Full decision hatası")
        raise HTTPException(status_code=500, detail=str(e))

    if not karar:
        raise HTTPException(status_code=404, detail=f"Karar bulunamadı: {decision_id}")
    return APIResponse(ok=True, data=karar)
