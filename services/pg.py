"""RAG vektör araması için senkron Postgres (psycopg3) bağlantı havuzu.

Neden ayrı/sync havuz?
- RAG arama fonksiyonları (services.rag.search, tenant_rag.search_tenant) senkron
  ve `run_blocking` (thread) ile çağrılıyor. asyncpg loop'a bağlıdır; thread içinde
  yeniden kullanılamaz. Bu yüzden RAG katmanı için izole, sync `psycopg` havuzu
  kullanılır. Uygulamanın asıl asyncpg havuzu (api/db.py) olduğu gibi kalır.

Env:
    RAG_DATABASE_URL  (yoksa DATABASE_URL)
    RAG_PG_MIN_SIZE   (vars. 1)
    RAG_PG_MAX_SIZE   (vars. 5)
"""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager

_pool = None
_lock = threading.Lock()


def _dsn() -> str:
    dsn = os.environ.get("RAG_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("RAG_DATABASE_URL / DATABASE_URL yok")
    return dsn


def get_pool():
    """Lazy, thread-safe singleton psycopg_pool.ConnectionPool."""
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                from psycopg_pool import ConnectionPool
                from pgvector.psycopg import register_vector

                def _configure(conn):
                    # Her bağlantıda pgvector tipini kaydet.
                    register_vector(conn)

                _pool = ConnectionPool(
                    conninfo=_dsn(),
                    min_size=int(os.environ.get("RAG_PG_MIN_SIZE", "1")),
                    max_size=int(os.environ.get("RAG_PG_MAX_SIZE", "5")),
                    kwargs={"autocommit": True},
                    configure=_configure,
                    open=True,
                )
    return _pool


@contextmanager
def connection():
    """Havuzdan bir bağlantı al (autocommit)."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
