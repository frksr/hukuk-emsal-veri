"""Dilekçe router — emsal bağlamlı dilekçe üretimi."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException

from api.deps import rate_limit
from api.schemas import APIResponse, DilekceIstegi
from services.dilekce_emsalli import generate_dilekce, DILEKCE_TURU_LABEL

log = logging.getLogger("api.dilekce")
router = APIRouter()


@router.post("/", response_model=APIResponse,
             summary="Emsal kararlara atıflı dilekçe taslağı üret")
async def dilekce_uret(
    istek: DilekceIstegi, _=Depends(rate_limit),
) -> APIResponse:
    """Kullanıcının olay anlatımına göre RAG + LLM ile dilekçe üretir.

    `dilekce_turu`: itirazin_iptali | ihalenin_feshi | menfi_tespit | tahsilat | genel.
    """
    if istek.dilekce_turu not in DILEKCE_TURU_LABEL:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Geçersiz dilekce_turu: {istek.dilekce_turu!r}. "
                f"Geçerli: {list(DILEKCE_TURU_LABEL.keys())}"
            ),
        )

    try:
        sonuc = generate_dilekce(
            durum=istek.durum,
            dilekce_turu=istek.dilekce_turu,
            taraflar=istek.taraflar,
            k=istek.k,
        )
    except Exception as e:
        msg = str(e).lower()
        if "api" in msg and ("key" in msg or "auth" in msg) or "llm" in msg:
            log.warning(f"LLM hatası: {e}")
            raise HTTPException(
                status_code=503,
                detail="LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.",
            )
        log.exception("Dilekçe üretimi başarısız")
        raise HTTPException(status_code=500, detail=f"Dilekçe üretilemedi: {e}")

    uyari = sonuc.get("uyari") or ""
    return APIResponse(
        ok=True,
        data=sonuc,
        message=uyari or "Dilekçe üretildi.",
    )
