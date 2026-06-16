"""KVKK uyum router — checklist üretimi ve uyum skoru hesabı."""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from api.concurrency import run_blocking
from api.deps import rate_limit
from api.auth import get_optional_user, CurrentUser
from api.schemas import APIResponse, KVKKIstegi
from services.uretim_gunlugu import kaydet_kullanim

# AI özelliklerinin açık olduğu ücretli plan tier'ları
_PAID_TIERS = {"pro_solo", "pro_solo_uyap", "team", "team_uyap", "enterprise"}
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
    istek: KVKKIstegi,
    background: BackgroundTasks,
    _=Depends(rate_limit),
    user: CurrentUser | None = Depends(get_optional_user),
) -> APIResponse:
    """Temel + sektörel + veri türü maddelerinden oluşan KVKK uyum checklist'i.

    Temel (kural tabanlı) checklist herkese açık; `llm_ek` (AI ile sektöre özel ek
    maddeler) yalnızca ücretli planlarda çalışır.
    """
    if istek.llm_ek and (user is None or (user.tenant_plan or "free") not in _PAID_TIERS):
        raise HTTPException(
            status_code=402,
            detail="AI ile sektöre özel ek maddeler Pro aboneliğe özeldir. "
                   "Yükseltme: /fiyatlandirma",
        )
    if istek.sektor not in SEKTOR_ETIKETLERI:
        log.info(f"Bilinmeyen sektor {istek.sektor!r} → 'diger' kullanılacak")

    try:
        sonuc = await run_blocking(
            checklist_uret,
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

    if user:
        background.add_task(kaydet_kullanim, user.user_id, user.tenant_id, "kvkk",
                            {"sektor": istek.sektor, "llm_ek": bool(istek.llm_ek)})
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
