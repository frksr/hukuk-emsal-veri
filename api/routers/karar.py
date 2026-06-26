"""Karar detay sayfaları için public endpoint'ler (programatik SEO).

- GET /api/karar/liste        → sayfalı karar listesi (sitemap + listing)
- GET /api/karar/benzer/{id}  → ilgili kararlar (iç linkleme / SEO)
- Detay için mevcut /api/arama/full/{id} kullanılır.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Path, Query

from api.cache import TTLCache
from api.concurrency import run_blocking
from api.schemas import APIResponse
from services.rag import list_decisions, related_decisions

log = logging.getLogger("api.karar")
router = APIRouter()

_liste_cache = TTLCache(maxsize=128, ttl=21600)  # 6 saat
_benzer_cache = TTLCache(maxsize=512, ttl=21600)  # 6 saat

MAX_LIMIT = 1000


@router.get("/liste", response_model=APIResponse,
            summary="Public karar listesi (sayfalı)")
async def karar_liste(
    limit: int = Query(100, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    source: str | None = Query(None, max_length=30),
) -> APIResponse:
    """Anonimleştirme kontrolünden geçen kararların kimlik/meta listesi.

    Karar detay sayfaları ve sitemap üretimi bu endpoint'i kullanır.
    """
    key = _liste_cache.make_key(limit, offset, source)
    data = _liste_cache.get(key)
    if data is None:
        try:
            data = await run_blocking(
                list_decisions, limit=limit, offset=offset, source=source)
        except Exception as e:
            log.exception("Karar listesi hatası")
            raise HTTPException(status_code=500, detail=str(e))
        if data:
            _liste_cache.set(key, data)
    return APIResponse(ok=True, data=data, message=f"{len(data)} karar")


@router.get("/benzer/{decision_id}", response_model=APIResponse,
            summary="İlgili kararlar (aynı daire/kaynak)")
async def karar_benzer(
    decision_id: str = Path(..., min_length=1, max_length=200),
    limit: int = Query(6, ge=1, le=20),
) -> APIResponse:
    """Karar detay sayfalarındaki 'İlgili Kararlar' iç linkleme bloğunu besler.

    Aynı daireden (yoksa aynı kaynaktan) anonimleştirme kontrolünü geçmiş
    kararları döndürür. Maliyetsiz (parquet metadata, LLM yok), 6 saat cache.
    """
    key = _benzer_cache.make_key(decision_id, limit)
    data = _benzer_cache.get(key)
    if data is None:
        try:
            data = await run_blocking(
                related_decisions, decision_id, limit=limit)
        except Exception as e:
            log.exception("Benzer karar hatası")
            raise HTTPException(status_code=500, detail=str(e))
        if data:
            _benzer_cache.set(key, data)
    return APIResponse(ok=True, data=data, message=f"{len(data)} ilgili karar")
