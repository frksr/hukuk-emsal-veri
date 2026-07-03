"""Karşı argüman router — kullanıcının tezine karşı argüman + rebuttal üretir."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException

from fastapi import BackgroundTasks
from api.deps import rate_limit
from api.auth import CurrentUser
from api.kota import kota
from api.concurrency import run_blocking
from api.schemas import APIResponse, KarsiArgumentIstegi
from services.karsi_argument import karsi_argument_uret
from services.uretim_gunlugu import kaydet_uretim

log = logging.getLogger("api.karsi_argument")
router = APIRouter()


@router.post("/", response_model=APIResponse,
             summary="Kullanıcı tezine karşı argümanları üret")
async def karsi_argument(
    istek: KarsiArgumentIstegi,
    background: BackgroundTasks,
    _=Depends(rate_limit),
    user: CurrentUser = Depends(kota("karsi_argument")),  # Yapay Zeka: Pro veya ek paket
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
        raise HTTPException(status_code=500, detail="Üretim başarısız. Lütfen tekrar deneyin.")

    uyari = sonuc.get("uyari") or sonuc.get("ozet_uyari") or ""
    background.add_task(
        kaydet_uretim, user.user_id, user.tenant_id, "karsi_argument", log_usage=False,
        alt_tur=istek.dava_turu, baslik="Karşı argüman",
        girdi_ozeti=istek.kendi_tezi, cikti=str(sonuc.get("muhtemel_karsi_argumanlar"))[:8000],
    )
    return APIResponse(ok=True, data=sonuc, message=uyari)
