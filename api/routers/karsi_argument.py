"""Karşı argüman router — kullanıcının tezine karşı argüman + rebuttal üretir."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException

from api.deps import rate_limit
from api.concurrency import run_blocking
from api.schemas import APIResponse, KarsiArgumentIstegi
from services.karsi_argument import karsi_argument_uret

log = logging.getLogger("api.karsi_argument")
router = APIRouter()


@router.post("/", response_model=APIResponse,
             summary="Kullanıcı tezine karşı argümanları üret")
async def karsi_argument(
    istek: KarsiArgumentIstegi, _=Depends(rate_limit),
) -> APIResponse:
    """RAG ile anti-tez emsalleri bulup LLM ile karşı argümanları + rebuttal üretir.

    Demo modu (LLM yok) durumunda sadece emsalleri listeler, `demo_modu=True`
    bayrağını döner — 503 atmaz çünkü RAG kısmı çalışır.
    """
    try:
        sonuc = await run_blocking(
            karsi_argument_uret,
            kendi_tezi=istek.kendi_tezi,
            dava_turu=istek.dava_turu,
            k=istek.k,
        )
    except Exception as e:
        log.exception("Karşı argüman üretimi başarısız")
        msg = str(e).lower()
        if "llm" in msg or ("api" in msg and "key" in msg):
            raise HTTPException(
                status_code=503,
                detail="LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.",
            )
        raise HTTPException(status_code=500, detail=f"Üretim başarısız: {e}")

    uyari = sonuc.get("uyari") or sonuc.get("ozet_uyari") or ""
    return APIResponse(ok=True, data=sonuc, message=uyari)
