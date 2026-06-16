"""İhtarname router — noter ihtarnamesi taslağı üretimi."""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.deps import rate_limit
from api.auth import CurrentUser
from api.kota import kota
from api.concurrency import run_blocking
from api.schemas import APIResponse, IhtarnameIstegi
from services.ihtarname import ihtarname_olustur, TUR_PROFILLERI
from services.uretim_gunlugu import kaydet_uretim

log = logging.getLogger("api.ihtarname")
router = APIRouter()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


@router.post("/", response_model=APIResponse,
             summary="Noter ihtarnamesi taslağı üret (Pro)")
async def ihtarname_uret(
    istek: IhtarnameIstegi,
    background: BackgroundTasks,
    _=Depends(rate_limit),
    user: CurrentUser = Depends(kota("ihtarname")),  # Yapay Zeka ihtarname: Pro veya ek paket
) -> APIResponse:
    """Tür ve taraflara göre LLM ile ihtarname taslağı üretir.

    `tur`: alacak_temerrut | kira_tahliye | cek_ihtari | fesih_ihtari |
    tahliye_30gun | genel.
    """
    if istek.tur not in TUR_PROFILLERI:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Geçersiz tur: {istek.tur!r}. "
                f"Geçerli: {list(TUR_PROFILLERI.keys())}"
            ),
        )

    try:
        sonuc = await run_blocking(
            ihtarname_olustur,
            tur=istek.tur,
            taraflar=istek.taraflar,
            alacak_detay=istek.alacak_detay,
            ek_talepler=istek.ek_talepler,
        )
    except Exception as e:
        log.exception("İhtarname üretimi başarısız")
        msg = str(e).lower()
        if "llm" in msg or ("api" in msg and "key" in msg):
            raise HTTPException(
                status_code=503,
                detail="LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.",
            )
        raise HTTPException(status_code=500, detail=f"İhtarname üretilemedi: {e}")

    if sonuc.get("hata"):
        hata_msg = str(sonuc["hata"])
        if "llm" in hata_msg.lower() or "api" in hata_msg.lower():
            raise HTTPException(
                status_code=503,
                detail="LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.",
            )
        raise HTTPException(status_code=400, detail=hata_msg)

    background.add_task(
        kaydet_uretim, user.user_id, user.tenant_id, "ihtarname", log_usage=False,
        alt_tur=istek.tur,
        baslik=f"İhtarname — {istek.tur}",
        girdi_ozeti=str(istek.taraflar),
        cikti=sonuc.get("ihtarname_metni"),
    )
    return APIResponse(ok=True, data=_json_safe(sonuc))
