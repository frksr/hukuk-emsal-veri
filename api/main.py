"""FastAPI app — production backend.

Çalıştır:
  uvicorn api.main:app --reload --port 8000

Production:
  uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
"""
from __future__ import annotations
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from api.logging_setup import configure_logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent

# Yapısal log + request_id (bkz. api/logging_setup.py).
# LOG_FORMAT=json ile Cloud Logging'de jsonPayload.request_id filtrelenebilir.
configure_logging()
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
    # RAG warmup — ARKA PLANDA. Artık container'da embedding modeli YOK
    # (embedding'ler Google API ile üretilir, vektörler Cloud SQL/pgvector'da).
    # Burada yalnızca pgvector erişimini ısıtır/kontrol ederiz; startup'ı bloklamaz.
    import asyncio as _asyncio_rag

    async def _rag_warmup():
        try:
            from services.rag import get_collection_stats
            stats = await _asyncio_rag.to_thread(get_collection_stats)
            log.info("RAG (pgvector) hazır: %s", stats)
        except Exception as e:
            log.warning(f"RAG warmup başarısız: {e}")

    _asyncio_rag.create_task(_rag_warmup())
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

    # Uptime self-check — VARSAYILAN OLARAK KAPALI.
    #
    # Bu kontrol API sürecinin İÇİNDE çalışır ve iki nedenle güvenilir değildir:
    #   1) Instance'ın kendisi tamamen düşerse döngü de durur, alarm gitmez.
    #   2) max-instances>1 iken HER instance kendi _state'iyle ayrı ayrı kontrol
    #      edip ayrı ayrı mail atar → geçici bir dalgalanmada N kat "düştü/ayakta"
    #      spam'i. ALERT_COOLDOWN yalnızca instance içinde geçerlidir.
    # Bu yüzden tek güvenilir kaynak GCP Uptime Check'tir. İç monitör yalnızca
    # UPTIME_SELFCHECK_ENABLED=1 ile ve tek instance (min=max=1) senaryosunda
    # bilinçli olarak açılmalıdır.
    _uptime_task = None
    if os.environ.get("UPTIME_SELFCHECK_ENABLED", "").strip().lower() in ("1", "true", "yes", "on"):
        async def _uptime_dongusu():
            from services.uptime_monitor import check_and_alert
            while True:
                try:
                    await check_and_alert()
                except Exception as e:
                    log.warning(f"Uptime kontrol hatası: {e}")
                await _asyncio.sleep(300)

        _uptime_task = _asyncio.create_task(_uptime_dongusu())
        log.info("Uptime izleme döngüsü başlatıldı (5 dk) — UPTIME_SELFCHECK_ENABLED açık")
    else:
        log.info("Uptime iç monitörü KAPALI (UPTIME_SELFCHECK_ENABLED set değil) — GCP Uptime Check kullanılıyor")
    yield
    log.info("API kapatılıyor")
    _hatirlatici_task.cancel()
    if _uptime_task is not None:
        _uptime_task.cancel()
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
    # API PATCH/PUT/DELETE uçları içeriyor (me.py, admin.py, notlar.py,
    # alarmlar.py, extension.py). Liste GET/POST/OPTIONS ile sınırlıyken bu
    # uçlar tarayıcıdan doğrudan çağrılamıyordu; şu an Next.js server-side
    # proxy deseni bunu maskeliyor ama backend'e doğrudan erişecek herhangi
    # bir istemci (widget, mobil webview, 3. taraf) sessizce engellenirdi.
    # Origin kısıtlaması zaten allow_origins ile yapılıyor.
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-Response-Time-ms"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_timing(request: Request, call_next):
    """Korelasyon kimliği + süre ölçümü.

    request_id contextvar'a yazıldığı için bu isteğin TÜM log satırları
    (servis katmanı dahil) otomatik olarak aynı kimliği taşır.
    """
    from api.logging_setup import new_request_id, request_id_ctx

    rid = new_request_id(request)
    token = request_id_ctx.set(rid)
    # Router/servis katmanı da erişebilsin (ör. hata yanıtına koymak için)
    request.state.request_id = rid
    if _SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.set_tag("request_id", rid)
        except Exception:
            pass

    start = time.perf_counter()
    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.0f}"
        response.headers["X-Request-Id"] = rid
        if elapsed_ms > 500:
            # Log satırı contextvar reset'ten ÖNCE yazılmalı, aksi halde
            # yavaş istek uyarısı request_id taşımaz.
            log.warning(
                "Slow: %s %s %.0fms", request.method, request.url.path, elapsed_ms,
                extra={"http_method": request.method, "http_path": request.url.path,
                       "duration_ms": round(elapsed_ms)},
            )
        return response
    finally:
        request_id_ctx.reset(token)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", "-")
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": "internal_error",
            # Kullanıcı destek talebinde bu kimliği paylaşabilir; logda
            # request_id ile aynı isteği tek grepte buluruz.
            "request_id": rid,
            "message": "Bir hata oluştu. Birkaç dakika sonra tekrar deneyin. "
                       f"(Referans: {rid})",
            "detail": str(exc) if os.environ.get("DEBUG") else None,
        },
        headers={"X-Request-Id": rid},
    )


@app.get("/api/health")
async def health():
    """Liveness — process ayakta mı? Bağımlılıklara BAKMAZ.

    Load balancer'ın "bu instance'ı yeniden başlat" kararı için. DB geçici
    olarak erişilemez olduğunda tüm instance'ların birden restart edilmesini
    istemeyiz; o durum readiness'in işidir (aşağıya bakınız).
    """
    from services.rag import get_collection_stats
    from llm.provider import status as llm_status
    return {
        "ok": True,
        "service": "hukuk-emsal-api",
        "version": "1.0.0",
        "rag": get_collection_stats(),
        "llm": llm_status(),
    }


@app.get("/api/ready")
async def ready():
    """Readiness — bu instance gerçekten trafik alabilir mi?

    Eskiden yalnızca /api/health vardı ve DB'ye hiç dokunmuyordu: Postgres
    erişilemez olduğunda tüm istekler 500 dönerken load balancer hâlâ 200 OK
    görüyor, instance sağlıksız işaretlenmiyordu. Uptime izleme ve LB
    readiness probe'u bu ucu kullanmalıdır.
    """
    from api.db import get_pool

    detail: dict = {"service": "hukuk-emsal-api", "version": "1.0.0"}
    try:
        pool = await get_pool()
        t0 = time.perf_counter()
        async with pool.acquire() as conn:
            await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=3.0)
        detail["db"] = {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000)}
    except Exception as e:
        log.error("Readiness DB kontrolü başarısız: %s", e)
        detail["db"] = {"ok": False, "error": type(e).__name__}
        detail["ok"] = False
        return JSONResponse(status_code=503, content=detail)

    detail["ok"] = True
    return detail


# Router'ları kaydet
from api.routers import (
    arama, dilekce, ozet, faiz, zamanasimi,
    ihtarname, trend, karsi_argument, kvkk, sozlesme,
    denetim, me, auth_actions, billing, uyap, admin, feedback,
    export, karar, v1, notlar, hatirlatici, waitlist, icerik,
    kullanim, sablonlar, alarmlar, publisher, extension, newsletter,
)

app.include_router(arama.router, prefix="/api/arama", tags=["arama"])
app.include_router(dilekce.router, prefix="/api/dilekce", tags=["dilekce"])
app.include_router(denetim.router, prefix="/api/denetim", tags=["denetim"])
app.include_router(ozet.router, prefix="/api/ozet", tags=["ozet"])
app.include_router(me.router, prefix="/api/me", tags=["account"])
app.include_router(auth_actions.router, prefix="/api/auth", tags=["auth"])
app.include_router(billing.router, prefix="/api/billing", tags=["billing"])
app.include_router(uyap.router, prefix="/api/uyap", tags=["uyap"])
app.include_router(extension.router, prefix="/api/extension", tags=["extension"])
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
app.include_router(icerik.router, prefix="/api/icerik", tags=["icerik"])
app.include_router(publisher.router, prefix="/api/publisher", tags=["publisher"])
app.include_router(kullanim.router, prefix="/api/me/kullanim", tags=["account"])
app.include_router(sablonlar.router, prefix="/api/sablonlar", tags=["sablonlar"])
app.include_router(alarmlar.router, prefix="/api/alarmlar", tags=["alarmlar"])
app.include_router(newsletter.router, prefix="/api/newsletter", tags=["newsletter"])
