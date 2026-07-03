"""Belge Denetim endpoint'i."""
from __future__ import annotations
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form

from api.deps import rate_limit
from api.auth import CurrentUser
from api.kota import kota
from api.concurrency import run_blocking
from api.schemas import APIResponse
from services.uretim_gunlugu import kaydet_uretim

log = logging.getLogger("api.denetim")
router = APIRouter()


@router.post("/text", response_model=APIResponse, summary="Metin olarak yapıştırılan belgeyi denet")
async def denetle_text(
    payload: dict,
    background: BackgroundTasks,
    _: None = Depends(rate_limit),
    user: CurrentUser = Depends(kota("denetim")),  # Yapay Zeka denetim: Pro veya ek paket
):
    """Belgeyi (dilekçe/ihtarname/sözleşme/genel) yapıştırarak gönder, AI denetimi al."""
    metin = payload.get("metin", "")
    tur = payload.get("tur", "dilekce")
    k = int(payload.get("k", 5))

    if not metin or len(metin) < 50:
        raise HTTPException(400, "Belge metni en az 50 karakter olmalı.")

    try:
        from services.belge_denetim import denetle
        result = await run_blocking(denetle, metin, tur=tur, k=k)
        background.add_task(
            kaydet_uretim, user.user_id, user.tenant_id, "denetim", log_usage=False,
            alt_tur=tur, baslik=f"Belge denetimi — {tur}",
            girdi_ozeti=metin, cikti=str(result)[:8000],
        )
        return APIResponse(ok=True, data=result)
    except Exception as e:
        msg = str(e).lower()
        if "llm" in msg or "api" in msg or "key" in msg:
            log.warning(f"Belge denetimi LLM erişim hatası: {e}")
            raise HTTPException(503, "LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.")
        log.exception("Belge denetimi başarısız")
        raise HTTPException(500, "Belge denetlenemedi. Lütfen tekrar deneyin.")


@router.post("/upload", response_model=APIResponse, summary="PDF/DOCX/TXT yükleyerek denet")
async def denetle_upload(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    tur: str = Form("dilekce"),
    _: None = Depends(rate_limit),
    user: CurrentUser = Depends(kota("denetim")),  # Yapay Zeka denetim: Pro veya ek paket
):
    """Dosya yükleyerek denet — sözleşme analizi için kullanılan parse mantığı."""
    if file.filename:
        ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    else:
        ext = ""

    if ext not in {"pdf", "docx", "txt", "md"}:
        raise HTTPException(400, "Desteklenmeyen dosya türü. PDF, DOCX, TXT veya MD olmalı.")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Dosya 10 MB'dan büyük.")

    try:
        from services.sozlesme import parse_dosya
        metin = await run_blocking(parse_dosya, content, ext)
    except Exception as e:
        raise HTTPException(400, f"Dosya parse edilemedi: {e}")

    if not metin or len(metin) < 50:
        raise HTTPException(400, "Dosyadan yeterli metin çıkarılamadı.")

    try:
        from services.belge_denetim import denetle
        result = await run_blocking(denetle, metin, tur=tur, k=5)
        result["dosya_adi"] = file.filename
        result["dosya_boyut"] = len(content)
        background.add_task(
            kaydet_uretim, user.user_id, user.tenant_id, "denetim", log_usage=False,
            alt_tur=tur, baslik=f"Belge denetimi (dosya) — {file.filename}",
            girdi_ozeti=file.filename, cikti=str(result)[:8000],
        )
        return APIResponse(ok=True, data=result)
    except Exception as e:
        msg = str(e).lower()
        if "llm" in msg or "api" in msg or "key" in msg:
            log.warning(f"Belge denetimi (dosya) LLM erişim hatası: {e}")
            raise HTTPException(503, "LLM şu an erişilemez. Birkaç dakika sonra tekrar deneyin.")
        log.exception("Belge denetimi (dosya) başarısız")
        raise HTTPException(500, "Belge denetlenemedi. Lütfen tekrar deneyin.")


@router.get("/turler", summary="Desteklenen belge türleri")
async def turler():
    return APIResponse(ok=True, data={
        "turler": [
            {"value": "dilekce", "label": "Dilekçe (genel)"},
            {"value": "dava_dilekce", "label": "Dava Dilekçesi"},
            {"value": "cevap_dilekce", "label": "Cevap Dilekçesi"},
            {"value": "ihtarname", "label": "İhtarname"},
            {"value": "sozlesme", "label": "Sözleşme"},
            {"value": "genel", "label": "Genel Hukuki Belge"},
        ],
    })
