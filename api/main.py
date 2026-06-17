"""FastAPI app — production backend.

Çalıştır:
  uvicorn api.main:app --reload --port 8000

Production:
  uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
"""
from __future__ import annotations
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("api")

# Sentry — SENTRY_DSN set ise hata/performans izleme aktif olur.
import os as _os
_SENTRY_DSN = _os.environ.get("SENTRY_DSN", "")
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            environment=_os.environ.get("APP_ENV", "production"),
            release=_os.environ.get("APP_RELEASE"),
            integrations=[StarletteIntegration(), FastApiIntegration()],
            traces_sample_rate=float(_os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            # KVKK: PII'yi Sentry'ye göndermeyiz (request body/headers maskelenir).
            send_default_pii=False,
        )
        log.info("Sentry aktif (env=%s)", _os.environ.get("APP_ENV", "production"))
    except Exception as e:
        log.warning("Sentry başlatılamadı: %s", e)
else:
    log.info("SENTRY_DSN yok — hata izleme devre dışı.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    log.info("API başlatılıyor...")
    # DB pool
    try:
        from api.db import init_pool, close_pool
        await init_pool()
        log.info("Postgres pool hazır")
    except Exception as e:
        log.warning(f"DB başlatma başarısız: {e}")
    # Waitlist tablosu — yoksa oluştur (migration'a gerek kalmadan)
    try:
        from api.db import service_session
        async with service_session() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS waitlist (
                    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name       TEXT NOT NULL,
                    email      TEXT NOT NULL,
                    plan       TEXT,
                    ip         TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE UNIQUE INDEX IF NOT EXISTS waitlist_email_uniq ON waitlist(email);
                CREATE INDEX IF NOT EXISTS waitlist_created_idx ON waitlist(created_at DESC);
            """)
        log.info("Waitlist tablosu hazır")
    except Exception as e:
        log.warning(f"Waitlist tablo oluşturma başarısız: {e}")
    # Embedding modelini önceden yükle
    try:
        from services.rag import _load_model, _load_collection
        _load_model()
        _load_collection()
        log.info("RAG model + Chroma yüklendi")
    except Exception as e:
        log.warning(f"RAG warmup başarısız: {e}")
    # Hatırlatıcı dispatch — hafif arka plan döngüsü (60 sn'de bir bekleyenleri gönderir).
    import asyncio as _asyncio

    async def _hatirlatici_dongusu():
        from services.hatirlatici_gonderim import bekleyen_hatirlaticilari_gonder
        while True:
            try:
                await bekleyen_hatirlaticilari_gonder()
            except Exception as e:
                log.warning(f"Hatırlatıcı dispatch hatası: {e}")
            await _asyncio.sleep(60)

    _hatirlatici_task = _asyncio.create_task(_hatirlatici_dongusu())
    log.info("Hatırlatıcı dispatch döngüsü başlatıldı (60 sn)")
    yield
    log.info("API kapatılıyor")
    _hatirlatici_task.cancel()
    try:
        from api.db import close_pool
        await close_pool()
    except Exception:
        pass


app = FastAPI(
    title="Hukuk Emsal API",
    description=(
        "Türk hukuk emsal karar arama + AI destekli hukuki araçlar. "
        "İcra, tahsilat, ihtar konularında uzmanlaşmış."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS — production'da spesifik origin'lere kısıtla
import os
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8501,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.0f}"
    if elapsed_ms > 500:
        log.warning(f"Slow: {request.method} {request.url.path} {elapsed_ms:.0f}ms")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception(f"Unhandled error on {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": "internal_error",
            "message": "Bir hata oluştu. Birkaç dakika sonra tekrar deneyin.",
            "detail": str(exc) if os.environ.get("DEBUG") else None,
        },
    )


@app.get("/api/health")
async def health():
    """Health check — load balancer / uptime monitoring için."""
    from services.rag import get_collection_stats
    from llm.provider import status as llm_status
    return {
        "ok": True,
        "service": "hukuk-emsal-api",
        "version": "1.0.0",
        "rag": get_collection_stats(),
        "llm": llm_status(),
    }


# Router'ları kaydet
from api.routers import (
    arama, dilekce, ozet, faiz, zamanasimi,
    ihtarname, trend, karsi_argument, kvkk, sozlesme,
    denetim, me, auth_actions, billing, uyap, admin, feedback,
    export, karar, v1, notlar, hatirlatici, waitlist,
)

app.include_router(arama.router, prefix="/api/arama", tags=["arama"])
app.include_router(dilekce.router, prefix="/api/dilekce", tags=["dilekce"])
app.include_router(denetim.router, prefix="/api/denetim", tags=["denetim"])
app.include_router(ozet.router, prefix="/api/ozet", tags=["ozet"])
app.include_router(me.router, prefix="/api/me", tags=["account"])
app.include_router(auth_actions.router, prefix="/api/auth", tags=["auth"])
app.include_router(billing.router, prefix="/api/billing", tags=["billing"])
app.include_router(uyap.router, prefix="/api/uyap", tags=["uyap"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(faiz.router, prefix="/api/faiz", tags=["hesaplayici"])
app.include_router(zamanasimi.router, prefix="/api/zamanasimi", tags=["hesaplayici"])
app.include_router(ihtarname.router, prefix="/api/ihtarname", tags=["ihtarname"])
app.include_router(trend.router, prefix="/api/trend", tags=["analytics"])
app.include_router(karsi_argument.router, prefix="/api/karsi-argument", tags=["v3"])
app.include_router(kvkk.router, prefix="/api/kvkk", tags=["v3"])
app.include_router(sozlesme.router, prefix="/api/sozlesme", tags=["v3"])
app.include_router(notlar.router, prefix="/api/notlar", tags=["notlar"])
app.include_router(hatirlatici.router, prefix="/api/hatirlatici", tags=["hatirlatici"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(karar.router, prefix="/api/karar", tags=["karar"])
app.include_router(v1.router, prefix="/api/v1", tags=["public-api"])
app.include_router(waitlist.router, prefix="/api/waitlist", tags=["waitlist"])
