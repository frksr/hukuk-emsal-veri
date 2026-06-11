"""Dilekçe router — emsal bağlamlı dilekçe üretimi.

İki mod:
  POST /            → klasik (tek yanıt, JSON)
  POST /stream      → SSE streaming (token-token; önerilen)
"""
from __future__ import annotations

import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.concurrency import run_blocking
from api.deps import rate_limit
from api.schemas import APIResponse, DilekceIstegi
from services.dilekce_emsalli import (
    DILEKCE_TURU_LABEL,
    generate_dilekce,
    generate_dilekce_stream,
)

log = logging.getLogger("api.dilekce")
router = APIRouter()

_SENTINEL = object()


def _tur_kontrol(dilekce_turu: str) -> None:
    if dilekce_turu not in DILEKCE_TURU_LABEL:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Geçersiz dilekce_turu: {dilekce_turu!r}. "
                f"Geçerli: {list(DILEKCE_TURU_LABEL.keys())}"
            ),
        )


@router.post("/", response_model=APIResponse,
             summary="Emsal kararlara atıflı dilekçe taslağı üret")
async def dilekce_uret(
    istek: DilekceIstegi, _=Depends(rate_limit),
) -> APIResponse:
    """Kullanıcının olay anlatımına göre RAG + LLM ile dilekçe üretir.

    `dilekce_turu`: itirazin_iptali | ihalenin_feshi | menfi_tespit | tahsilat | genel.
    """
    _tur_kontrol(istek.dilekce_turu)

    try:
        # LLM çağrısı senkron — event loop'u bloklamasın diye thread'e al.
        sonuc = await run_blocking(
            generate_dilekce,
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


@router.post("/stream",
             summary="Dilekçe taslağını SSE ile token-token üret")
async def dilekce_stream(
    istek: DilekceIstegi, _=Depends(rate_limit),
) -> StreamingResponse:
    """Server-Sent Events akışı.

    Event sırası:
      data: {"type":"meta", "kullanilan_emsaller":[...], "uyari":"", "demo":false}
      data: {"type":"delta", "text":"..."}   (çok kez)
      data: {"type":"done"}
    Hata: {"type":"error", "message":"..."}
    """
    _tur_kontrol(istek.dilekce_turu)

    def _next(gen):
        return next(gen, _SENTINEL)

    async def event_source():
        gen = generate_dilekce_stream(
            durum=istek.durum,
            dilekce_turu=istek.dilekce_turu,
            taraflar=istek.taraflar,
            k=istek.k,
        )
        try:
            while True:
                # Senkron generator'ı thread'de ilerlet — loop'u bloklama.
                event = await run_blocking(_next, gen)
                if event is _SENTINEL:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
        except Exception as e:
            log.exception("Dilekçe stream hatası")
            payload = {"type": "error", "message": f"Akış hatası: {e}"}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx buffer'lamasın
        },
    )
