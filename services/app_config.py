"""Dinamik uygulama konfigürasyonu (app_config tablosu).

Plan limitleri ve ek paket kataloğu gibi GLOBAL ayarlar kod yerine DB'den okunur;
admin panelden düzenlenince ~CACHE_TTL saniye içinde yansır.

- get(key, default): TTL cache'li okuma. DB hatasında default'a düşer.
- set_value(key, value): upsert + cache tazeleme.
- get_plan_limits(): "plan_limits" key'i, {tool: {tier: int|null}} şekli (yoksa {}).
- get_credit_packs(): "credit_packs" key'i (yoksa None → kod default'u kullanılır).

Hatalarda sessizce default'a düşer; uygulamayı asla bozmaz.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from api.db import service_session

log = logging.getLogger("services.app_config")

# Modül seviyesi TTL cache. Her key için (deger, son_okuma_ts).
CACHE_TTL = 30  # saniye
_cache: dict[str, tuple[Any, float]] = {}


def _fresh(key: str) -> bool:
    entry = _cache.get(key)
    return bool(entry) and (time.monotonic() - entry[1]) < CACHE_TTL


async def get(key: str, default: Any = None, force: bool = False) -> Any:
    """Bir config key'inin değerini döndürür (cache + DB fallback).

    force=True: process-içi cache'i atlayıp her zaman DB'den okur. Backend
    birden fazla worker process'iyle çalışıyor (bkz. railway.json
    "--workers 4") — her worker'ın kendi belleğinde AYRI bir _cache sözlüğü
    var. Bir worker set_value() ile yazınca yalnızca KENDİ cache'ini
    tazeler; admin panelin "Kaydet" sonrası yaptığı yeniden-okuma isteği
    round-robin ile FARKLI bir worker'a düşerse, o worker hâlâ eski değeri
    (TTL dolana kadar, en fazla CACHE_TTL saniye) döndürür — admin panelde
    "kaydettim ama sayfayı yenileyince eskisine dönüyor" görüntüsüne yol
    açar. Admin'in kendi düzenleme ekranını her zaman force=True ile
    okutuyoruz ki kayıttan hemen sonra hangi worker'a düşerse düşsün güncel
    veriyi görsün.
    """
    if not force and _fresh(key):
        return _cache[key][0]
    try:
        async with service_session() as conn:
            val = await conn.fetchval(
                "SELECT value FROM app_config WHERE key = $1", key,
            )
    except Exception as e:
        log.warning("app_config okuma hatası (%s): %s", key, e)
        # DB erişilemiyorsa: bayat cache varsa onu, yoksa default'u döndür.
        entry = _cache.get(key)
        return entry[0] if entry else default

    if val is None:
        # Key yok → default. (Cache'lemeyiz ki eklenince hızlı yansısın.)
        return default

    # asyncpg JSONB'yi str olarak verebilir → parse et.
    if isinstance(val, str):
        import json as _json
        try:
            val = _json.loads(val)
        except Exception:
            val = default
    _cache[key] = (val, time.monotonic())
    return val


async def set_value(key: str, value: dict) -> None:
    """Bir config key'ini upsert eder ve cache'i tazeler."""
    import json as _json
    try:
        async with service_session() as conn:
            await conn.execute(
                """INSERT INTO app_config (key, value, updated_at)
                   VALUES ($1, $2::jsonb, NOW())
                   ON CONFLICT (key)
                   DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
                key, _json.dumps(value, ensure_ascii=False),
            )
        _cache[key] = (value, time.monotonic())
    except Exception as e:
        log.error("app_config yazma hatası (%s): %s", key, e)
        # Cache'i temizle ki sonraki okuma DB'den taze gelsin.
        _cache.pop(key, None)
        raise


async def get_plan_limits(force: bool = False) -> dict:
    """Plan limit override'ı. Şekil: {tool: {tier: int|null}}. Yoksa {}."""
    val = await get("plan_limits", {}, force=force)
    return val if isinstance(val, dict) else {}


async def get_credit_packs(force: bool = False) -> Optional[dict]:
    """Ek paket kataloğu override'ı. Yoksa None → kod default'u kullanılır."""
    val = await get("credit_packs", None, force=force)
    if val is None:
        return None
    return val if isinstance(val, dict) else None
