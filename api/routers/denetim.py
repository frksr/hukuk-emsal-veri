"""Belge Denetim endpoint'i."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from api.deps import rate_limit
from api.schemas import APIResponse

router = APIRouter()


@router.post("/text", response_model=APIResponse, summary="Metin olarak yapıştırılan belgeyi denet")
async def denetle_text(payload: dict, _: None = Depends(rate_limit)):
    """Belgeyi (dilekçe/ihtarname/sözleşme/genel) yapıştırarak gönder, AI denetimi al."""
    metin = payload.get("metin", "")
    tur = payload.get("tur", "dilekce")
    k = int(payload.get("k", 5))

    if not metin or len(metin) < 50:
        raise HTTPException(400, "Belge metni en az 50 karakter olmalı.")

    try:
        from services.belge_denetim import denetle
        result = denetle(metin, tur=tur, k=k)
        return APIResponse(ok=True, data=result)
    except Exception as e:
        msg = str(e).lower()
        if "llm" in msg or "api" in msg or "key" in msg:
            raise HTTPException(503, "LLM şu an erişilemez. .env dosyasındaki API key'leri kontrol edin.")
        raise HTTPException(500, str(e))


@router.post("/upload", response_model=APIResponse, summary="PDF/DOCX/TXT yükleyerek denet")
async def denetle_upload(
    file: UploadFile = File(...),
    tur: str = Form("dilekce"),
    _: None = Depends(rate_limit),
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
        metin = parse_dosya(content, ext)
    except Exception as e:
        raise HTTPException(400, f"Dosya parse edilemedi: {e}")

    if not metin or len(metin) < 50:
        raise HTTPException(400, "Dosyadan yeterli metin çıkarılamadı.")

    try:
        from services.belge_denetim import denetle
        result = denetle(metin, tur=tur, k=5)
        result["dosya_adi"] = file.filename
        result["dosya_boyut"] = len(content)
        return APIResponse(ok=True, data=result)
    except Exception as e:
        msg = str(e).lower()
        if "llm" in msg or "api" in msg:
            raise HTTPException(503, "LLM şu an erişilemez.")
        raise HTTPException(500, str(e))


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
