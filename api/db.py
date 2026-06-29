"""PostgreSQL bağlantı + tenant context yöneticisi."""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg

# İki ayrı bağlantı havuzu (bkz. infra/db/07_rls_hardening.sql):
#   _pool          → kullanıcı istekleri. RLS'e TABİ rol (app_user, NOBYPASSRLS).
#                    DATABASE_URL ile bağlanır. Tenant context set_config ile verilir.
#   _service_pool  → cross-tenant/sistem işleri (webhook, audit, auth bootstrap,
#                    admin, key_manager). RLS BYPASS eden rol (app_service).
#                    SERVICE_DATABASE_URL ile bağlanır; yoksa DATABASE_URL'e düşer.
#
# SERVICE_DATABASE_URL ayarlanmazsa iki havuz da aynı role bağlanır ve RLS rol
# bazlı ikinci katman DEVRE DIŞI kalır (yalnızca explicit WHERE + context'li
# db_session koruması geçerli olur). Production'da rol ayrımı yapılması önerilir.
_pool: asyncpg.Pool | None = None
_service_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL environment variable yok")
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=5,
            command_timeout=30,
            server_settings={"application_name": "hukuk-emsal-api"},
        )
    return _pool


async def init_service_pool() -> asyncpg.Pool:
    global _service_pool
    if _service_pool is None:
        dsn = os.environ.get("SERVICE_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("SERVICE_DATABASE_URL / DATABASE_URL yok")
        _service_pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=3,
            command_timeout=30,
            server_settings={"application_name": "hukuk-emsal-api-service"},
        )
    return _service_pool


async def close_pool():
    global _pool, _service_pool
    if _pool is not None:
        await _pool.close()
        _pool = None
    if _service_pool is not None:
        await _service_pool.close()
        _service_pool = None


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        await init_pool()
    return _pool  # type: ignore[return-value]


async def get_service_pool() -> asyncpg.Pool:
    if _service_pool is None:
        await init_service_pool()
    return _service_pool  # type: ignore[return-value]


@asynccontextmanager
async def service_session() -> AsyncIterator[asyncpg.Connection]:
    """RLS BYPASS eden sistem bağlantısı — cross-tenant/bootstrap işler için.

    KULLANIM ALANI (yalnızca):
      - iyzico webhook (birden çok tenant'ı günceller)
      - auth bootstrap (kullanıcının tenant üyeliklerini context OLMADAN bulma)
      - audit log yazımı
      - admin (tüm tenant'lar) ve arka plan işleri (key_manager, purge, cron)

    Kullanıcıya ait normal sorgularda KULLANMAYIN — onlar db_session(user_id,
    tenant_id) ile RLS'e tabi olmalı.
    """
    pool = await get_service_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def db_session(
    user_id: str | None = None,
    tenant_id: str | None = None,
) -> AsyncIterator[asyncpg.Connection]:
    """Bir DB connection al, RLS için tenant context ayarla.

    Kullanım:
        async with db_session(user_id=uid, tenant_id=tid) as conn:
            rows = await conn.fetch("SELECT * FROM tenant_documents")
            # RLS otomatik filtreliyor, sadece tenant_id'ye ait olanlar gelir

    Güvenlik notları:
    - Context, `set_config(..., is_local => true)` ile ayarlanır. `SET LOCAL` /
      local set_config SADECE bir transaction içinde kalıcıdır; transaction
      dışında hiçbir etkisi yoktur (PostgreSQL bu durumda sessizce yok sayar ve
      bir WARNING üretir). Bu yüzden context verildiğinde tüm blok otomatik
      olarak bir transaction içine alınır — aksi halde RLS politikalarındaki
      `current_setting('app.current_user_id', TRUE)` NULL döner ve izolasyon
      katmanı fiilen devre dışı kalırdı.
    - Değer parametre olarak ($1) geçirilir; SQL string interpolation YOK.
      (Eski `f"SET LOCAL ... = '{user_id}'"` SQL injection'a açık ve kırılgandı.)
    - RLS'in gerçekten uygulanması için backend'in tabloların OWNER'ı OLMAYAN bir
      rol ile bağlanması gerekir; ayrıca tablolarda `FORCE ROW LEVEL SECURITY`
      açık olmalıdır (bkz. infra/db/07_rls_hardening.sql).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if user_id or tenant_id:
            # SET LOCAL'in geçerli olması için transaction şart.
            async with conn.transaction():
                if user_id:
                    await conn.execute(
                        "SELECT set_config('app.current_user_id', $1, true)",
                        str(user_id),
                    )
                if tenant_id:
                    await conn.execute(
                        "SELECT set_config('app.current_tenant_id', $1, true)",
                        str(tenant_id),
                    )
                yield conn
        else:
            yield conn
