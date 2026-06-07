"""Trend / analytics router — DuckDB tabanlı zaman serisi ve dağılımlar."""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query

from api.schemas import APIResponse
from services.trend import (
    trend_yillik,
    trend_konu_dagilimi,
    trend_mahkeme_konu_matrix,
    trend_aylik,
    filtre_secenekleri,
    trend_top_mahkemeler,
    trend_kaynak_dagilimi,
)

log = logging.getLogger("api.trend")
router = APIRouter()


@router.get("/yillik", response_model=APIResponse,
            summary="Yıllık karar sayısı (zaman serisi)")
async def yillik(
    konu_filtresi: str | None = Query(None, max_length=100),
    kaynak: str | None = Query(None, max_length=50),
    daire: str | None = Query(None, max_length=100),
) -> APIResponse:
    """Yıl bazında karar sayısı. Konu/kaynak/daire ile filtrelenebilir."""
    try:
        data = trend_yillik(konu_filtresi=konu_filtresi, kaynak=kaynak, daire=daire)
    except Exception as e:
        log.exception("trend_yillik hatası")
        raise HTTPException(status_code=500, detail=str(e))
    return APIResponse(ok=True, data=data)


@router.get("/konu-dagilimi", response_model=APIResponse,
            summary="Yıl aralığında top-10 konu dağılımı")
async def konu_dagilimi(
    yil_baslangic: int = Query(..., ge=1990, le=2100),
    yil_bitis: int = Query(..., ge=1990, le=2100),
) -> APIResponse:
    """Belirtilen yıl aralığında en sık geçen 10 topic_tags."""
    if yil_bitis < yil_baslangic:
        raise HTTPException(
            status_code=400,
            detail="yil_bitis, yil_baslangic'tan küçük olamaz.",
        )
    try:
        data = trend_konu_dagilimi(yil_baslangic, yil_bitis)
    except Exception as e:
        log.exception("trend_konu_dagilimi hatası")
        raise HTTPException(status_code=500, detail=str(e))
    return APIResponse(ok=True, data=data)


@router.get("/mahkeme-konu", response_model=APIResponse,
            summary="Mahkeme x Konu heatmap matrisi")
async def mahkeme_konu(
    top_n_mahkeme: int = Query(10, ge=3, le=30),
    top_n_konu: int = Query(10, ge=3, le=30),
) -> APIResponse:
    """Heatmap için court_chamber × topic matrisi."""
    try:
        data = trend_mahkeme_konu_matrix(
            top_n_mahkeme=top_n_mahkeme,
            top_n_konu=top_n_konu,
        )
    except Exception as e:
        log.exception("trend_mahkeme_konu_matrix hatası")
        raise HTTPException(status_code=500, detail=str(e))
    return APIResponse(ok=True, data=data)


@router.get("/aylik", response_model=APIResponse,
            summary="Aylık zaman serisi (YYYY-MM)")
async def aylik(
    konu_filtresi: str = Query("", max_length=100),
    yil_baslangic: int = Query(..., ge=1990, le=2100),
    yil_bitis: int = Query(..., ge=1990, le=2100),
) -> APIResponse:
    """Aylık karar sayımları. Konu boş bırakılırsa tüm kararlar dahil."""
    if yil_bitis < yil_baslangic:
        raise HTTPException(
            status_code=400,
            detail="yil_bitis, yil_baslangic'tan küçük olamaz.",
        )
    try:
        data = trend_aylik(konu_filtresi, yil_baslangic, yil_bitis)
    except Exception as e:
        log.exception("trend_aylik hatası")
        raise HTTPException(status_code=500, detail=str(e))
    return APIResponse(ok=True, data=data)


@router.get("/filtre-secenekleri", response_model=APIResponse,
            summary="Dropdown'lar için filtre seçenekleri")
async def filtre_options() -> APIResponse:
    """kaynak/daire/konu listeleri + yıl aralığı."""
    try:
        data = filtre_secenekleri()
    except Exception as e:
        log.exception("filtre_secenekleri hatası")
        raise HTTPException(status_code=500, detail=str(e))
    return APIResponse(ok=True, data=data)


@router.get("/kaynak-dagilimi", response_model=APIResponse,
            summary="source bazlı dağılım (pie chart)")
async def kaynak_dagilimi(
    konu_filtresi: str | None = Query(None, max_length=100),
    yil_baslangic: int | None = Query(None, ge=1990, le=2100),
    yil_bitis: int | None = Query(None, ge=1990, le=2100),
) -> APIResponse:
    """yargitay/danistay/aym vs. dağılımı."""
    if (yil_baslangic is not None and yil_bitis is not None
            and yil_bitis < yil_baslangic):
        raise HTTPException(
            status_code=400,
            detail="yil_bitis, yil_baslangic'tan küçük olamaz.",
        )
    try:
        data = trend_kaynak_dagilimi(
            konu_filtresi=konu_filtresi,
            yil_baslangic=yil_baslangic,
            yil_bitis=yil_bitis,
        )
    except Exception as e:
        log.exception("trend_kaynak_dagilimi hatası")
        raise HTTPException(status_code=500, detail=str(e))
    return APIResponse(ok=True, data=data)


@router.get("/top-mahkemeler", response_model=APIResponse,
            summary="En sık karar üreten top-N mahkeme")
async def top_mahkemeler(
    top_n: int = Query(15, ge=3, le=50),
    konu_filtresi: str | None = Query(None, max_length=100),
    kaynak: str | None = Query(None, max_length=50),
    yil_baslangic: int | None = Query(None, ge=1990, le=2100),
    yil_bitis: int | None = Query(None, ge=1990, le=2100),
) -> APIResponse:
    """court_chamber bazlı top sıralama."""
    if (yil_baslangic is not None and yil_bitis is not None
            and yil_bitis < yil_baslangic):
        raise HTTPException(
            status_code=400,
            detail="yil_bitis, yil_baslangic'tan küçük olamaz.",
        )
    try:
        data = trend_top_mahkemeler(
            top_n=top_n,
            konu_filtresi=konu_filtresi,
            kaynak=kaynak,
            yil_baslangic=yil_baslangic,
            yil_bitis=yil_bitis,
        )
    except Exception as e:
        log.exception("trend_top_mahkemeler hatası")
        raise HTTPException(status_code=500, detail=str(e))
    return APIResponse(ok=True, data=data)
