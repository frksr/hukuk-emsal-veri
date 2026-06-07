"""KVKK uyum router — checklist üretimi ve uyum skoru hesabı."""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import rate_limit
from api.schemas import APIResponse, KVKKIstegi
from services.kvkk import (
    checklist_uret,
    uyum_skoru_hesapla,
    list_sektorler,
    list_veri_turleri,
    SEKTOR_ETIKETLERI,
)

log = logging.getLogger("api.kvkk")
router = APIRouter()


class UyumSkoruIstegi(BaseModel):
    """Uyum skoru hesabı için: checklist maddeleri + tamamlanan no'lar."""
    maddeler: list[dict[str, Any]] = Field(..., min_length=1)
    tamamlananlar: list[int] = Field(default_factory=list)


@router.post("/checklist", response_model=APIResponse,
             summary="Sektör + veri türlerine göre KVKK checklist üret")
async def kvkk_checklist(
    istek: KVKKIstegi, _=Depends(rate_limit),
) -> APIResponse:
    """Temel + sektörel + veri türü maddelerinden oluşan KVKK uyum checklist'i."""
    if istek.sektor not in SEKTOR_ETIKETLERI:
        log.info(f"Bilinmeyen sektor {istek.sektor!r} → 'diger' kullanılacak")

    try:
        sonuc = checklist_uret(
            sektor=istek.sektor,
            veri_turleri=istek.veri_turleri,
            llm_ek=istek.llm_ek,
        )
    except Exception as e:
        log.exception("KVKK checklist üretimi başarısız")
        msg = str(e).lower()
        if istek.llm_ek and ("llm" in msg or ("api" in msg and "key" in msg)):
            raise HTTPException(
                status_code=503,
                detail="LLM şu an erişilemez. llm_ek=false ile tekrar deneyin.",
            )
        raise HTTPException(status_code=500, detail=f"Checklist üretilemedi: {e}")

    return APIResponse(ok=True, data=sonuc)


@router.post("/uyum-skoru", response_model=APIResponse,
             summary="Tamamlanan maddelere göre uyum skoru hesapla")
async def kvkk_uyum_skoru(
    istek: UyumSkoruIstegi = Body(...), _=Depends(rate_limit),
) -> APIResponse:
    """0-100 ağırlıklı uyum skoru (yuksek=3, orta=2, dusuk=1)."""
    try:
        skor = uyum_skoru_hesapla(istek.maddeler, istek.tamamlananlar)
    except Exception as e:
        log.exception("Uyum skoru hesabı başarısız")
        raise HTTPException(status_code=500, detail=f"Skor hesaplanamadı: {e}")

    return APIResponse(
        ok=True,
        data={
            "skor": int(skor),
            "tamamlanan_sayi": len(istek.tamamlananlar or []),
            "toplam_madde": len(istek.maddeler),
        },
    )


@router.get("/sektorler", response_model=APIResponse,
            summary="Desteklenen sektör listesi")
async def kvkk_sektorler() -> APIResponse:
    """KVKK checklist için sektör anahtarları + label'ları + veri türleri."""
    return APIResponse(
        ok=True,
        data={
            "sektorler": list_sektorler(),
            "sektor_label": dict(SEKTOR_ETIKETLERI),
            "veri_turleri": list_veri_turleri(),
        },
    )
