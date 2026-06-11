"""Belge export router — AI çıktısını .docx / .udf (UYAP) olarak indir."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api.concurrency import run_blocking
from api.deps import rate_limit
from services.export_belge import belge_docx, belge_udf, guvenli_dosya_adi

log = logging.getLogger("api.export")
router = APIRouter()

MAX_METIN = 200_000  # ~200KB metin üst sınırı


class ExportIstegi(BaseModel):
    metin: str = Field(..., min_length=1, max_length=MAX_METIN)
    baslik: str | None = Field(None, max_length=200)
    dosya_adi: str | None = Field(None, max_length=100)


@router.post("/docx", summary="Metni Word (.docx) olarak indir")
async def export_docx(istek: ExportIstegi, _=Depends(rate_limit)) -> Response:
    try:
        veri = await run_blocking(belge_docx, istek.metin, istek.baslik)
    except Exception as e:
        log.exception("DOCX export hatası")
        raise HTTPException(status_code=500, detail=f"DOCX üretilemedi: {e}")
    ad = guvenli_dosya_adi(istek.dosya_adi or istek.baslik or "belge", "docx")
    return Response(
        content=veri,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{ad}"'},
    )


@router.post("/udf", summary="Metni UYAP belgesi (.udf) olarak indir")
async def export_udf(istek: ExportIstegi, _=Depends(rate_limit)) -> Response:
    """UYAP Doküman Editörü'nde açılabilen .udf üretir.

    Avukat iş akışı: taslağı indir → UYAP'a doğrudan yükle.
    """
    try:
        veri = await run_blocking(belge_udf, istek.metin, istek.baslik)
    except Exception as e:
        log.exception("UDF export hatası")
        raise HTTPException(status_code=500, detail=f"UDF üretilemedi: {e}")
    ad = guvenli_dosya_adi(istek.dosya_adi or istek.baslik or "belge", "udf")
    return Response(
        content=veri,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{ad}"'},
    )
