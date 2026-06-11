"""Sözleşme analizi router — PDF/DOCX/TXT upload + analiz + .docx/.pdf rapor."""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any
from fastapi import (
    APIRouter, Body, Depends, File, Form, HTTPException, UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.deps import rate_limit
from api.concurrency import run_blocking
from api.schemas import APIResponse
from services.sozlesme import parse_dosya, analiz_et, rapor_docx, rapor_pdf

log = logging.getLogger("api.sozlesme")
router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
GECERLI_UZANTILAR = {".pdf", ".docx", ".txt", ".md"}


class AnalyzeTextIstegi(BaseModel):
    metin: str = Field(..., min_length=20)
    sozlesme_turu: str = "genel"


class ReportIstegi(BaseModel):
    analiz_data: dict[str, Any] = Field(..., description="analiz_et çıktısı")


def _llm_hata_mi(s: str) -> bool:
    s = (s or "").lower()
    return "llm" in s or ("api" in s and "key" in s) or "provider" in s


@router.post("/upload", response_model=APIResponse,
             summary="Sözleşme dosyası yükle ve analiz et")
async def sozlesme_upload(
    file: UploadFile = File(...),
    sozlesme_turu: str = Form("genel"),
    _=Depends(rate_limit),
) -> APIResponse:
    """PDF/DOCX/TXT yükler, parse eder ve analiz çıktısını döner (max 10 MB)."""
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in GECERLI_UZANTILAR:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz uzantı: {ext!r}. Geçerli: {sorted(GECERLI_UZANTILAR)}",
        )

    try:
        veri = await file.read()
    except Exception as e:
        log.exception("Upload okuma hatası")
        raise HTTPException(status_code=400, detail=f"Dosya okunamadı: {e}")

    if not veri:
        raise HTTPException(status_code=400, detail="Boş dosya.")
    if len(veri) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya çok büyük (max {MAX_UPLOAD_BYTES // (1024*1024)} MB).",
        )

    try:
        metin = await run_blocking(parse_dosya, veri, ext)
    except Exception as e:
        log.exception("parse_dosya hatası")
        raise HTTPException(status_code=400, detail=f"Dosya parse edilemedi: {e}")

    if not metin or not metin.strip():
        raise HTTPException(
            status_code=422,
            detail="Dosyadan metin çıkartılamadı (boş veya OCR gerekli olabilir).",
        )

    try:
        analiz = await run_blocking(analiz_et, metin, sozlesme_turu=sozlesme_turu)
    except Exception as e:
        log.exception("analiz_et hatası")
        if _llm_hata_mi(str(e)):
            raise HTTPException(
                status_code=503,
                detail="LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.",
            )
        raise HTTPException(status_code=500, detail=f"Analiz başarısız: {e}")

    if analiz.get("hata") and _llm_hata_mi(str(analiz["hata"])):
        raise HTTPException(
            status_code=503,
            detail="LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.",
        )

    analiz["dosya_adi"] = filename
    return APIResponse(ok=True, data=analiz)


@router.post("/analyze-text", response_model=APIResponse,
             summary="Düz metinden sözleşme analizi")
async def sozlesme_analyze_text(
    istek: AnalyzeTextIstegi, _=Depends(rate_limit),
) -> APIResponse:
    """Sözleşme metnini doğrudan vererek analiz al."""
    try:
        analiz = await run_blocking(analiz_et, istek.metin, sozlesme_turu=istek.sozlesme_turu)
    except Exception as e:
        log.exception("analiz_et hatası")
        if _llm_hata_mi(str(e)):
            raise HTTPException(
                status_code=503,
                detail="LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.",
            )
        raise HTTPException(status_code=500, detail=f"Analiz başarısız: {e}")

    if analiz.get("hata") and _llm_hata_mi(str(analiz["hata"])):
        raise HTTPException(
            status_code=503,
            detail="LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.",
        )

    return APIResponse(ok=True, data=analiz)


@router.post("/report.docx", summary="Analiz sonucundan .docx rapor")
async def sozlesme_report_docx(
    istek: ReportIstegi = Body(...), _=Depends(rate_limit),
) -> StreamingResponse:
    """Analiz dict'ini alıp Word (.docx) raporu döner."""
    try:
        veri = await run_blocking(rapor_docx, istek.analiz_data)
    except RuntimeError as e:
        log.warning(f"docx üretimi başarısız (paket eksik?): {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log.exception("rapor_docx hatası")
        raise HTTPException(status_code=500, detail=f"Rapor üretilemedi: {e}")

    return StreamingResponse(
        io.BytesIO(veri),
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": 'attachment; filename="sozlesme_analizi.docx"'},
    )


@router.post("/report.pdf", summary="Analiz sonucundan .pdf rapor")
async def sozlesme_report_pdf(
    istek: ReportIstegi = Body(...), _=Depends(rate_limit),
) -> StreamingResponse:
    """Analiz dict'ini alıp PDF raporu döner."""
    try:
        veri = await run_blocking(rapor_pdf, istek.analiz_data)
    except RuntimeError as e:
        log.warning(f"pdf üretimi başarısız (paket eksik?): {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log.exception("rapor_pdf hatası")
        raise HTTPException(status_code=500, detail=f"Rapor üretilemedi: {e}")

    return StreamingResponse(
        io.BytesIO(veri),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="sozlesme_analizi.pdf"'},
    )
