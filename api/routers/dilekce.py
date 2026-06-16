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

from fastapi import BackgroundTasks
from api.concurrency import run_blocking
from api.deps import rate_limit
from api.auth import get_optional_user, CurrentUser
from api.kota import kota
from api.schemas import APIResponse, DilekceIstegi
from services.uretim_gunlugu import kaydet_uretim
from services.dilekce_emsalli import (
    DILEKCE_TURU_LABEL,
    generate_dilekce,
    generate_dilekce_stream,
    generate_dilekce_template,
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


@router.post("/sablon", response_model=APIResponse,
             summary="Hızlı şablon dilekçe (LLM'siz, ücretsiz)")
async def dilekce_sablon(
    istek: DilekceIstegi,
    background: BackgroundTasks,
    _=Depends(rate_limit),
    user: CurrentUser | None = Depends(get_optional_user),
) -> APIResponse:
    """LLM/RAG kullanmadan, form alanlarından yapılandırılmış dilekçe iskeleti üretir.

    Ücretsiz/herkese açık. Emsal atfı ve olaya özel argüman içermez (o AI modudur).
    """
    _tur_kontrol(istek.dilekce_turu)
    sonuc = await run_blocking(
        generate_dilekce_template,
        durum=istek.durum,
        dilekce_turu=istek.dilekce_turu,
        taraflar=istek.taraflar,
    )
    if user:
        background.add_task(
            kaydet_uretim, user.user_id, user.tenant_id, "dilekce",
            alt_tur=istek.dilekce_turu, baslik=f"Dilekçe (şablon) — {istek.dilekce_turu}",
            girdi_ozeti=istek.durum, cikti=sonuc.get("dilekce_metni"),
            meta={"mode": "sablon"},
        )
    return APIResponse(ok=True, data=sonuc, message=sonuc.get("uyari") or "Şablon üretildi.")


@router.post("/", response_model=APIResponse,
             summary="Emsal kararlara atıflı dilekçe taslağı üret (Pro)")
async def dilekce_uret(
    istek: DilekceIstegi,
    background: BackgroundTasks,
    _=Depends(rate_limit),
    user: CurrentUser = Depends(kota("dilekce")),  # Yapay Zeka + Emsal: Pro veya ek paket
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
    background.add_task(
        kaydet_uretim, user.user_id, user.tenant_id, "dilekce", log_usage=False,
        alt_tur=istek.dilekce_turu, baslik=f"Dilekçe — {istek.dilekce_turu}",
        girdi_ozeti=istek.durum, cikti=sonuc.get("dilekce_metni"),
    )
    return APIResponse(
        ok=True,
        data=sonuc,
        message=uyari or "Dilekçe üretildi.",
    )


@router.post("/stream",
             summary="Dilekçe taslağını SSE ile token-token üret (Pro)")
async def dilekce_stream(
    istek: DilekceIstegi,
    _=Depends(rate_limit),
    user: CurrentUser = Depends(kota("dilekce")),  # Yapay Zeka + Emsal: Pro veya ek paket
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
        metin_parcalari: list[str] = []
        hata_olustu = False
        try:
            while True:
                # Senkron generator'ı thread'de ilerlet — loop'u bloklama.
                event = await run_blocking(_next, gen)
                if event is _SENTINEL:
                    break
                if event.get("type") == "delta" and event.get("text"):
                    metin_parcalari.append(str(event["text"]))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") == "error":
                    hata_olustu = True
                if event.get("type") in ("done", "error"):
                    break
        except Exception as e:
            log.exception("Dilekçe stream hatası")
            hata_olustu = True
            payload = {"type": "error", "message": f"Akış hatası: {e}"}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        # Akış başarıyla bittiyse üretimi geçmişe kaydet (stream sonrası).
        tam_metin = "".join(metin_parcalari)
        if tam_metin and not hata_olustu:
            try:
                await kaydet_uretim(
                    user.user_id, user.tenant_id, "dilekce",
                    alt_tur=istek.dilekce_turu,
                    baslik=f"Dilekçe — {istek.dilekce_turu}",
                    girdi_ozeti=istek.durum,
                    cikti=tam_metin,
                )
            except Exception:
                log.warning("Streaming dilekçe geçmiş kaydı başarısız", exc_info=True)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx buffer'lamasın
        },
    )
