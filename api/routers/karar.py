"""Karar detay sayfaları için public endpoint'ler (programatik SEO).

- GET /api/karar/liste     → sayfalı karar listesi (sitemap + listing)
- Detay için mevcut /api/arama/full/{id} kullanılır.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query

from api.cache import TTLCache
from api.concurrency import run_blocking
from api.schemas import APIResponse
from services.rag import list_decisions

log = logging.getLogger("api.karar")
router = APIRouter()

_liste_cache = TTLCache(maxsize=128, ttl=21600)  # 6 saat

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
