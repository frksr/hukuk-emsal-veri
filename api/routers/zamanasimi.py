"""Zamanaşımı router — deterministik tarih aritmetiği (LLM yok)."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from api.deps import rate_limit
from api.schemas import APIResponse, ZamanasimiIstegi
from services.zamanasimi import hesapla, list_kategoriler

log = logging.getLogger("api.zamanasimi")
router = APIRouter()


def _json_safe(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    return value


@router.post("/", response_model=APIResponse,
             summary="Zamanaşımı süresini hesapla")
async def zamanasimi_hesapla(
    istek: ZamanasimiIstegi, _=Depends(rate_limit),
) -> APIResponse:
    """Olay tarihinden başlayarak (varsa kesilme tarihleri dikkate alınır)
    bitiş, kalan gün ve durum hesaplar."""
    try:
        sonuc = hesapla(
            kategori=istek.kategori,
            alt_tip=istek.alt_tip,
            olay_tarihi=istek.olay_tarihi,
            kesilme_tarihleri=istek.kesilme_tarihleri,
        )
    except Exception as e:
        log.exception("Zamanaşımı hesabı başarısız")
        raise HTTPException(status_code=500, detail=f"Hesap başarısız: {e}")

    if sonuc.get("hata"):
        raise HTTPException(
            status_code=400,
            detail=sonuc.get("hata"),
        )

    return APIResponse(ok=True, data=_json_safe(sonuc))


@router.get("/kategoriler", response_model=APIResponse,
            summary="Tüm kategori/alt_tip kombinasyonları")
async def kategoriler() -> APIResponse:
    """Kategori → alt_tip listesi (UI dropdown'ları için)."""
    try:
        kat = list_kategoriler()
    except Exception as e:
        log.exception("Kategoriler hatası")
        raise HTTPException(status_code=500, detail=str(e))
    return APIResponse(ok=True, data=kat)
