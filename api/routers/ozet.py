"""Karar özeti router — sade Türkçe ile karar özetleme."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException

from api.deps import rate_limit
from api.concurrency import run_blocking
from api.schemas import APIResponse, OzetIstegi, OzetIstegiID
from services.karar_ozet import ozet_uret
from services.rag import get_full_decision

log = logging.getLogger("api.ozet")
router = APIRouter()

GECERLI_UZUNLUK = {"kisa", "orta", "detayli"}


def _llm_hata_mi(hata_msg: str) -> bool:
    m = (hata_msg or "").lower()
    return ("llm" in m) or ("api" in m and "key" in m) or ("provider" in m)


@router.post("/text", response_model=APIResponse,
             summary="Serbest metinden karar özeti üret")
async def ozet_metinden(
    istek: OzetIstegi, _=Depends(rate_limit),
) -> APIResponse:
    """Verilen karar metnini sade Türkçe ile özetler."""
    if istek.uzunluk not in GECERLI_UZUNLUK:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz uzunluk: {istek.uzunluk!r}. Geçerli: {sorted(GECERLI_UZUNLUK)}",
        )
    try:
        sonuc = await run_blocking(ozet_uret, istek.karar_metni, uzunluk=istek.uzunluk)
    except Exception as e:
        log.exception("Özet üretimi başarısız")
        raise HTTPException(status_code=500, detail=f"Özet üretilemedi: {e}")

    if sonuc.get("hata") and _llm_hata_mi(str(sonuc["hata"])):
        raise HTTPException(
            status_code=503,
            detail="LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.",
        )

    return APIResponse(ok=True, data=sonuc)


@router.post("/by-id", response_model=APIResponse,
             summary="Decision ID'den karar özeti üret")
async def ozet_by_id(
    istek: OzetIstegiID, _=Depends(rate_limit),
) -> APIResponse:
    """Decision ID ile parquet'ten kararı çekip özetler."""
    if istek.uzunluk not in GECERLI_UZUNLUK:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz uzunluk: {istek.uzunluk!r}. Geçerli: {sorted(GECERLI_UZUNLUK)}",
        )

    try:
        karar = await run_blocking(get_full_decision, istek.decision_id)
    except Exception as e:
        log.exception("get_full_decision hatası")
        raise HTTPException(status_code=500, detail=str(e))

    if not karar:
        raise HTTPException(
            status_code=404,
            detail=f"Karar bulunamadı: {istek.decision_id}",
        )

    metin = (
        karar.get("text")
        or karar.get("full_text")
        or karar.get("metin")
        or karar.get("content")
        or ""
    )
    if not metin or not str(metin).strip():
        raise HTTPException(
            status_code=422,
            detail="Karar bulundu ama metin alanı boş.",
        )

    try:
        sonuc = await run_blocking(ozet_uret, str(metin), uzunluk=istek.uzunluk)
    except Exception as e:
        log.exception("Özet üretimi başarısız (by-id)")
        raise HTTPException(status_code=500, detail=f"Özet üretilemedi: {e}")

    if sonuc.get("hata") and _llm_hata_mi(str(sonuc["hata"])):
        raise HTTPException(
            status_code=503,
            detail="LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.",
        )

    sonuc["decision_id"] = istek.decision_id
    return APIResponse(ok=True, data=sonuc)
