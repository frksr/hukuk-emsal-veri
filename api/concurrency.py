"""Blocking (senkron) çağrıları event loop dışında çalıştırma yardımcısı.

SORUN: Router'lar `async def` — içlerinde senkron LLM/RAG/DuckDB çağrısı
yapılırsa TÜM event loop bloklanır: tek worker'da bir dilekçe üretimi
(15-30 sn) sırasında /health dahil bütün istekler bekler.

ÇÖZÜM: Senkron çağrıları anyio'nun worker thread'ine taşı:

    from api.concurrency import run_blocking
    sonuc = await run_blocking(generate_dilekce, durum=..., k=...)

Not: Thread havuzu kapasitesi anyio varsayılanıdır (40). LLM çağrıları
uzun sürdüğü için gerekirse `ANYIO_THREAD_LIMIT` env ile artırılabilir.
"""
from __future__ import annotations

import functools
import os
from typing import Any, Callable, TypeVar

import anyio
import anyio.to_thread

T = TypeVar("T")

_LIMIT = int(os.environ.get("ANYIO_THREAD_LIMIT", "0"))
_limiter = anyio.CapacityLimiter(_LIMIT) if _LIMIT > 0 else None


async def run_blocking(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Senkron `func`'ı worker thread'de çalıştır, sonucu await et."""
    call = functools.partial(func, *args, **kwargs)
    if _limiter is not None:
        return await anyio.to_thread.run_sync(call, limiter=_limiter)
    return await anyio.to_thread.run_sync(call)
