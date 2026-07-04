"""Internal admin panel — sadece role='admin' kullanıcılar.

Beta yönetimi, manuel plan upgrade, audit log, feedback yönetimi.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.audit import audit
from api.auth import CurrentUser, get_current_user
from api.db import service_session
from api.schemas import APIResponse

log = logging.getLogger("api.admin")
router = APIRouter()


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(403, "Bu sayfaya sadece admin erişebilir.")
    return user


@router.get("/dashboard", response_model=APIResponse)
async def dashboard(admin: CurrentUser = Depends(require_admin)):
    """Genel istatistikler — DAU, MAU, tier dağılımı, gelir."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    async with service_session() as conn:
        # Kullanıcı sayıları
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
        new_24h = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at > $1", day_ago
        )
        new_7d = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at > $1", week_ago
        )
        new_30d = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at > $1", month_ago
        )

        # Aktif kullanıcı
        dau = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM usage_events WHERE created_at > $1 AND user_id IS NOT NULL",
            day_ago,
        )
        mau = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM usage_events WHERE created_at > $1 AND user_id IS NOT NULL",
            month_ago,
        )

        # Tier dağılımı
        tier_dist = await conn.fetch(
            """SELECT plan_tier, COUNT(*) c FROM tenants
               WHERE is_active = TRUE GROUP BY plan_tier ORDER BY c DESC"""
        )

        # Gelir tahmini (aylık)
        monthly_revenue = await conn.fetchval(
            """SELECT COALESCE(SUM(amount_try), 0) FROM payments
               WHERE status = 'success' AND paid_at > $1""",
            month_ago,
        )

        # Beta program
        beta_count = await conn.fetchval(
            "SELECT COUNT(*) FROM tenants WHERE beta_program = TRUE"
        )

        # Feedback özet
        feedback_open = await conn.fetchval(
            "SELECT COUNT(*) FROM feedback WHERE status IN ('new', 'reviewing', 'in_progress')"
        )
        feedback_critical = await conn.fetchval(
            "SELECT COUNT(*) FROM feedback WHERE severity = 'critical' AND status IN ('new', 'reviewing')"
        )

        # Toplam UYAP doküman
        total_docs = await conn.fetchval("SELECT COUNT(*) FROM tenant_documents")
        total_queries_30d = await conn.fetchval(
            "SELECT COUNT(*) FROM tenant_queries WHERE created_at > $1", month_ago
        )

    return APIResponse(ok=True, data={
        "users": {
            "total": total_users, "new_24h": new_24h, "new_7d": new_7d, "new_30d": new_30d,
            "dau": dau, "mau": mau,
        },
        "tiers": [{"plan": r["plan_tier"], "count": r["c"]} for r in tier_dist],
        "revenue": {
            "monthly_try": float(monthly_revenue or 0),
            "beta_count": beta_count,
        },
        "feedback": {
            "open": feedback_open, "critical": feedback_critical,
        },
        "uyap": {
            "documents": total_docs, "queries_30d": total_queries_30d,
        },
    })


@router.get("/health", response_model=APIResponse)
async def system_health(admin: CurrentUser = Depends(require_admin)):
    """Sistem sağlığı — DB, LLM, RAG, iyzico, mail ve arka plan (hatırlatıcı) durumu."""
    import os
    import time

    now = datetime.now(timezone.utc)
    db_ok = True
    db_ms = None
    pending = overdue = None
    try:
        t0 = time.perf_counter()
        async with service_session() as conn:
            await conn.fetchval("SELECT 1")
            pending = await conn.fetchval("SELECT COUNT(*) FROM reminders WHERE status='pending'")
            overdue = await conn.fetchval(
                "SELECT COUNT(*) FROM reminders WHERE status='pending' AND remind_at < $1",
                now - timedelta(minutes=10),
            )
        db_ms = round((time.perf_counter() - t0) * 1000)
    except Exception as e:
        db_ok = False
        db_ms = None
        log_msg = str(e)
    else:
        log_msg = None

    try:
        from llm.provider import status as llm_status
        s = llm_status()
        llm = {
            "available": bool(s.get("anthropic") or s.get("gemini")),
            "default": s.get("default"),
            "anthropic": s.get("anthropic"),
            "gemini": s.get("gemini"),
        }
    except Exception:
        llm = {"available": False}
    try:
        from services.rag import get_collection_stats
        rag = get_collection_stats()
    except Exception:
        rag = {"available": False}
    try:
        from services.billing import is_configured as iyzico_configured
        iyzico_ok = bool(iyzico_configured())
    except Exception:
        iyzico_ok = False
    try:
        from services.email import SMTP_HOST
        mail_ok = bool(SMTP_HOST)
    except Exception:
        mail_ok = bool(os.environ.get("SMTP_HOST"))

    return APIResponse(ok=True, data={
        "checked_at": now.isoformat(),
        "db": {"ok": db_ok, "latency_ms": db_ms, "error": log_msg},
        "llm": llm,
        "rag": rag,
        "iyzico": {"configured": iyzico_ok},
        "mail": {"configured": mail_ok},
        # Geciken bekleyen hatırlatıcı çoksa gönderim döngüsü tıkanmış olabilir.
        "reminders": {"pending": pending, "overdue": overdue},
    })


@router.get("/issues", response_model=APIResponse)
async def system_issues(admin: CurrentUser = Depends(require_admin), limit: int = 25):
    """Hata/aksaklık akışı — başarısız ödeme/hatırlatıcı/webhook/üretim + audit hataları."""
    now = datetime.now(timezone.utc)
    d1 = now - timedelta(hours=24)
    d7 = now - timedelta(days=7)
    saatlik = now - timedelta(hours=1)
    lim = min(int(limit), 100)

    def _iso(x):
        return x.isoformat() if x else None

    async with service_session() as conn:
        failed_payments = await conn.fetch(
            "SELECT id, tenant_id, amount_try, status, created_at FROM payments "
            "WHERE status <> 'success' AND created_at > $1 ORDER BY created_at DESC LIMIT $2",
            d7, lim,
        )
        failed_reminders = await conn.fetch(
            "SELECT id, baslik, status, remind_at, created_at FROM reminders "
            "WHERE status='failed' ORDER BY created_at DESC LIMIT $1", lim,
        )
        webhook_err = await conn.fetch(
            "SELECT id, event_type, process_error, processed, received_at AS created_at FROM webhook_events "
            "WHERE process_error IS NOT NULL OR processed = FALSE ORDER BY received_at DESC LIMIT $1", lim,
        )
        pending_orders = await conn.fetch(
            "SELECT id, pack_key, amount_try, status, created_at FROM credit_orders "
            "WHERE status='pending' AND created_at < $1 ORDER BY created_at DESC LIMIT $2", saatlik, lim,
        )
        audit_fail = await conn.fetch(
            "SELECT id, action, user_id, ip_address, created_at FROM audit_log "
            "WHERE success = FALSE AND created_at > $1 ORDER BY created_at DESC LIMIT $2", d1, lim,
        )
        c_fp = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE status <> 'success' AND created_at > $1", d7)
        c_fr = await conn.fetchval("SELECT COUNT(*) FROM reminders WHERE status='failed'")
        c_we = await conn.fetchval("SELECT COUNT(*) FROM webhook_events WHERE process_error IS NOT NULL OR processed = FALSE")
        c_po = await conn.fetchval("SELECT COUNT(*) FROM credit_orders WHERE status='pending' AND created_at < $1", saatlik)
        c_af = await conn.fetchval("SELECT COUNT(*) FROM audit_log WHERE success = FALSE AND created_at > $1", d1)

    return APIResponse(ok=True, data={
        "ozet": {
            "failed_payments_7d": c_fp or 0,
            "failed_reminders": c_fr or 0,
            "webhook_errors": c_we or 0,
            "pending_orders": c_po or 0,
            "audit_failures_24h": c_af or 0,
        },
        "failed_payments": [
            {"id": str(r["id"]), "tenant_id": str(r["tenant_id"]) if r["tenant_id"] else None,
             "amount_try": float(r["amount_try"] or 0), "status": r["status"], "created_at": _iso(r["created_at"])}
            for r in failed_payments
        ],
        "failed_reminders": [
            {"id": str(r["id"]), "baslik": r["baslik"], "status": r["status"],
             "remind_at": _iso(r["remind_at"]), "created_at": _iso(r["created_at"])}
            for r in failed_reminders
        ],
        "webhook_errors": [
            {"id": str(r["id"]), "event_type": r["event_type"], "process_error": r["process_error"],
             "processed": r["processed"], "created_at": _iso(r["created_at"])}
            for r in webhook_err
        ],
        "pending_orders": [
            {"id": str(r["id"]), "pack_key": r["pack_key"], "amount_try": float(r["amount_try"] or 0),
             "status": r["status"], "created_at": _iso(r["created_at"])}
            for r in pending_orders
        ],
        "audit_failures": [
            {"id": r["id"], "action": r["action"], "user_id": str(r["user_id"]) if r["user_id"] else None,
             "ip_address": str(r["ip_address"]) if r["ip_address"] else None, "created_at": _iso(r["created_at"])}
            for r in audit_fail
        ],
    })


# ---------------------------------------------------------------------------
# Tahmini Yapay Zeka maliyeti (₺/istek). GERÇEK fatura değil — kaba bir tahmin.
# Sağlayıcı/model fiyatları değiştikçe burayı güncelleyin. Düşük, makul değerler:
# her AI isteğinin tipik token tüketimine göre kabaca hesaplanmış ortalama maliyet.
# (Hesaplayıcılar — faiz/zamanasimi — ve saf emsal arama LLM kullanmaz → maliyet 0.)
# ---------------------------------------------------------------------------
TAHMINI_MALIYET_TRY: dict[str, float] = {
    "dilekce": 0.90,         # uzun üretim
    "ihtarname": 0.55,
    "ozet": 0.35,
    "denetim": 0.60,
    "karsi_argument": 0.70,
    "sozlesme": 0.95,        # uzun belge analizi
    "kvkk": 0.25,
    "sorgu": 0.80,           # RAG + bağlam (UYAP)
    # LLM kullanmayanlar (gösterim için 0):
    "arama": 0.0, "faiz": 0.0, "zamanasimi": 0.0, "trend": 0.0,
}
_VARSAYILAN_AI_MALIYET = 0.50  # kataloğa eklenmemiş yeni AI event_type için

# Google embedding (gemini-embedding-001) fiyatı — 2026 itibarıyla doğrulanmış.
# Kaynak: ai.google.dev/gemini-api/docs/pricing — $0.15 / 1M girdi token (standart).
# Çıktı token'ı yok (embedding'in kendisi "çıktı" sayılmıyor, ücretlendirilmiyor).
# Token sayısı loglanmıyor (yalnızca karakter) → kabaca 1 token ≈ 4 karakter
# varsayımıyla tahmin ediliyor. Bu da GERÇEK fatura değil, TAHMİNİ bir değerdir.
_EMBEDDING_USD_PER_1M_TOKEN = 0.15
_EMBEDDING_KARAKTER_PER_TOKEN = 4


@router.get("/analytics", response_model=APIResponse)
async def analytics(admin: CurrentUser = Depends(require_admin)):
    """Kapsamlı analitik — müşteriler, gelir, kredi, AI istekleri, araç kullanımı,
    sağlayıcı dağılımı, tahmini maliyet ve en aktif müşteriler. Hepsi gerçek tablolardan.
    """
    from services.krediler import MODUL_ETIKET

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Hangi event_type'lar "Yapay Zeka isteği" sayılır (LLM kullanan modüller).
    AI_EVENTS = (
        "dilekce", "ihtarname", "ozet", "denetim",
        "karsi_argument", "sozlesme", "kvkk", "sorgu",
    )

    def _iso(x):
        return x.isoformat() if x else None

    async with service_session() as conn:
        # ---- a) Müşteriler -------------------------------------------------
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
        new_24h = await conn.fetchval("SELECT COUNT(*) FROM users WHERE created_at > $1", day_ago)
        new_7d = await conn.fetchval("SELECT COUNT(*) FROM users WHERE created_at > $1", week_ago)
        new_30d = await conn.fetchval("SELECT COUNT(*) FROM users WHERE created_at > $1", month_ago)
        dau = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM usage_events WHERE created_at > $1 AND user_id IS NOT NULL",
            day_ago,
        )
        mau = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM usage_events WHERE created_at > $1 AND user_id IS NOT NULL",
            month_ago,
        )
        tier_rows = await conn.fetch(
            """SELECT plan_tier, COUNT(*) c FROM tenants
               WHERE is_active = TRUE GROUP BY plan_tier ORDER BY c DESC"""
        )

        # ---- b) Gelir & paket alımları -------------------------------------
        # Abonelik ödemeleri (30g, başarılı).
        sub_row = await conn.fetchrow(
            """SELECT COUNT(*) c, COALESCE(SUM(amount_try),0) toplam FROM payments
               WHERE status = 'success' AND COALESCE(paid_at, created_at) > $1""",
            month_ago,
        )
        # Ek paket alımları (credit_orders) — ödenmiş/yüklenmiş say.
        pack_row = await conn.fetchrow(
            """SELECT COUNT(*) c, COALESCE(SUM(amount_try),0) toplam FROM credit_orders
               WHERE (status = 'paid' OR granted = TRUE) AND created_at > $1""",
            month_ago,
        )
        # En çok satılan ek paketler (30g).
        pack_top = await conn.fetch(
            """SELECT pack_key, COUNT(*) adet, COALESCE(SUM(amount_try),0) toplam
               FROM credit_orders
               WHERE (status = 'paid' OR granted = TRUE) AND created_at > $1
               GROUP BY pack_key ORDER BY adet DESC LIMIT 10""",
            month_ago,
        )

        # ---- c) Kredi kullanımları (modül bazlı) ---------------------------
        # purchase/grant = +delta (satın alınan/yüklenen), consume = -delta (tüketilen).
        kredi_rows = await conn.fetch(
            """SELECT module,
                      COALESCE(SUM(CASE WHEN delta > 0 THEN delta ELSE 0 END),0) satin_alinan,
                      COALESCE(SUM(CASE WHEN delta < 0 THEN -delta ELSE 0 END),0) tuketilen
               FROM credit_transactions
               GROUP BY module
               ORDER BY tuketilen DESC"""
        )

        # ---- d) Yapay Zeka istek sayısı + 7g günlük trend ------------------
        ai_total = await conn.fetchval(
            "SELECT COUNT(*) FROM usage_events WHERE event_type = ANY($1::text[]) AND COALESCE(metadata->>'mode','') <> 'sablon'",
            list(AI_EVENTS),
        )
        ai_30d = await conn.fetchval(
            "SELECT COUNT(*) FROM usage_events WHERE event_type = ANY($1::text[]) AND COALESCE(metadata->>'mode','') <> 'sablon' AND created_at > $2",
            list(AI_EVENTS), month_ago,
        )
        ai_trend = await conn.fetch(
            """SELECT (created_at AT TIME ZONE 'UTC')::date d, COUNT(*) c
               FROM usage_events
               WHERE event_type = ANY($1::text[]) AND COALESCE(metadata->>'mode','') <> 'sablon' AND created_at > $2
               GROUP BY d ORDER BY d""",
            list(AI_EVENTS), week_ago,
        )

        # ---- e) En çok kullanılan araçlar (toplam + 30g) -------------------
        tool_total = await conn.fetch(
            "SELECT event_type, COUNT(*) c FROM usage_events GROUP BY event_type ORDER BY c DESC"
        )
        tool_30d_rows = await conn.fetch(
            """SELECT event_type, COUNT(*) c FROM usage_events
               WHERE created_at > $1 GROUP BY event_type""",
            month_ago,
        )
        tool_30d_map = {r["event_type"]: r["c"] for r in tool_30d_rows}

        # ---- f) En aktif müşteriler (ilk 10) -------------------------------
        aktif_rows = await conn.fetch(
            """SELECT ue.user_id, u.email, u.name, COUNT(*) c,
                      MAX(ue.created_at) son
               FROM usage_events ue
               JOIN users u ON u.id = ue.user_id
               WHERE ue.user_id IS NOT NULL
               GROUP BY ue.user_id, u.email, u.name
               ORDER BY c DESC LIMIT 10"""
        )

        # ---- h) Sağlayıcı dağılımı (AI events, metadata->>'provider') ------
        # Eski kayıtların provider'ı yok → 'bilinmiyor' altında toplanır.
        provider_rows = await conn.fetch(
            """SELECT COALESCE(NULLIF(metadata->>'provider',''), 'bilinmiyor') provider,
                      COUNT(*) c
               FROM usage_events
               WHERE event_type = ANY($1::text[]) AND COALESCE(metadata->>'mode','') <> 'sablon'
               GROUP BY provider ORDER BY c DESC""",
            list(AI_EVENTS),
        )
        provider_30d_rows = await conn.fetch(
            """SELECT COALESCE(NULLIF(metadata->>'provider',''), 'bilinmiyor') provider,
                      COUNT(*) c
               FROM usage_events
               WHERE event_type = ANY($1::text[]) AND COALESCE(metadata->>'mode','') <> 'sablon' AND created_at > $2
               GROUP BY provider ORDER BY c DESC""",
            list(AI_EVENTS), month_ago,
        )

        # ---- i) Embedding API kullanımı (Google embedding, RAG arama/indeksleme) --
        # Not: embedding_usage_log tablosu RAG'ın senkron psycopg havuzundan
        # (services/pg.py, services/embeddings.py) yazılır; asyncpg havuzuyla
        # (burada) aynı fiziksel veritabanına bağlı olduğundan normal okunur.
        # Migration 26 henüz uygulanmamışsa (tablo yok) TÜM /analytics'i 500'e
        # düşürmesin diye try/except ile korunuyor — sıfırlanmış veri döner.
        _embed_bos = {"istek": 0, "karakter": 0}
        embed_total_row: dict = {"istek": 0, "ogeler": 0, "karakter": 0}
        embed_24h_row: dict = dict(_embed_bos)
        embed_7d_row: dict = dict(_embed_bos)
        embed_30d_row: dict = dict(_embed_bos)
        embed_type_rows: list = []
        try:
            embed_total_row = await conn.fetchrow(
                """SELECT COUNT(*) istek, COALESCE(SUM(item_count),0) ogeler,
                          COALESCE(SUM(char_count),0) karakter
                   FROM embedding_usage_log"""
            )
            embed_24h_row = await conn.fetchrow(
                """SELECT COUNT(*) istek, COALESCE(SUM(char_count),0) karakter
                   FROM embedding_usage_log WHERE created_at > $1""",
                day_ago,
            )
            embed_7d_row = await conn.fetchrow(
                """SELECT COUNT(*) istek, COALESCE(SUM(char_count),0) karakter
                   FROM embedding_usage_log WHERE created_at > $1""",
                week_ago,
            )
            embed_30d_row = await conn.fetchrow(
                """SELECT COUNT(*) istek, COALESCE(SUM(char_count),0) karakter
                   FROM embedding_usage_log WHERE created_at > $1""",
                month_ago,
            )
            embed_type_rows = await conn.fetch(
                """SELECT request_type, COUNT(*) c FROM embedding_usage_log
                   GROUP BY request_type ORDER BY c DESC"""
            )
        except Exception:
            log.warning(
                "embedding_usage_log okunamadı (migration 26 uygulanmamış olabilir) — "
                "embedding kullanım verisi sıfır dönüyor.", exc_info=True,
            )

        # ---- g0) Maliyet için AI-only olay sayıları (sablon dilekçe hariç) --
        # tool_total/tool_30d sablon olaylarını da içerir; maliyet onlara dahil
        # edilmemeli. Bu yüzden maliyet için ayrı, sablon-hariç sayım haritası.
        ai_cost_total_rows = await conn.fetch(
            """SELECT event_type, COUNT(*) c FROM usage_events
               WHERE event_type = ANY($1::text[]) AND COALESCE(metadata->>'mode','') <> 'sablon'
               GROUP BY event_type""",
            list(AI_EVENTS),
        )
        ai_cost_30d_rows = await conn.fetch(
            """SELECT event_type, COUNT(*) c FROM usage_events
               WHERE event_type = ANY($1::text[]) AND COALESCE(metadata->>'mode','') <> 'sablon'
                     AND created_at > $2
               GROUP BY event_type""",
            list(AI_EVENTS), month_ago,
        )

    # ---- g) Tahmini Yapay Zeka maliyeti (toplam + 30g) --------------------
    def _maliyet(rows_map: dict[str, int]) -> dict:
        kalemler = []
        toplam = 0.0
        for et, adet in rows_map.items():
            if et not in TAHMINI_MALIYET_TRY and et not in AI_EVENTS:
                continue  # LLM kullanmayan araçları maliyet listesinden çıkar
            birim = TAHMINI_MALIYET_TRY.get(et, _VARSAYILAN_AI_MALIYET)
            tutar = round(birim * int(adet), 2)
            if tutar <= 0:
                continue
            toplam += tutar
            kalemler.append({
                "event_type": et,
                "etiket": MODUL_ETIKET.get(et, et),
                "adet": int(adet),
                "birim_try": birim,
                "tutar_try": tutar,
            })
        kalemler.sort(key=lambda x: x["tutar_try"], reverse=True)
        return {"toplam_try": round(toplam, 2), "kalemler": kalemler}

    tool_total_map = {r["event_type"]: r["c"] for r in tool_total}
    # Maliyet, sablon-hariç AI-only sayımlardan hesaplanır (sablon dilekçe dahil değil).
    ai_cost_total_map = {r["event_type"]: r["c"] for r in ai_cost_total_rows}
    ai_cost_30d_map = {r["event_type"]: r["c"] for r in ai_cost_30d_rows}
    maliyet_toplam = _maliyet(ai_cost_total_map)
    maliyet_30g = _maliyet(ai_cost_30d_map)

    # ---- i) Embedding maliyeti (TAHMİNİ — karakter → token yaklaşıklaması) ---
    def _embed_maliyet_usd(karakter: int) -> float:
        tahmini_token = (int(karakter or 0)) / _EMBEDDING_KARAKTER_PER_TOKEN
        return round(tahmini_token / 1_000_000 * _EMBEDDING_USD_PER_1M_TOKEN, 4)

    sub_count = int(sub_row["c"] or 0)
    sub_toplam = float(sub_row["toplam"] or 0)
    pack_count = int(pack_row["c"] or 0)
    pack_toplam = float(pack_row["toplam"] or 0)

    return APIResponse(ok=True, data={
        "generated_at": now.isoformat(),
        # a) Müşteriler
        "musteriler": {
            "toplam_aktif": total_users or 0,
            "yeni_24s": new_24h or 0,
            "yeni_7g": new_7d or 0,
            "yeni_30g": new_30d or 0,
            "dau": dau or 0,
            "mau": mau or 0,
            "plan_dagilimi": [{"plan": r["plan_tier"], "adet": r["c"]} for r in tier_rows],
        },
        # b) Gelir & paket alımları (30g)
        "gelir": {
            "abonelik_adet": sub_count,
            "abonelik_toplam_try": round(sub_toplam, 2),
            "ek_paket_adet": pack_count,
            "ek_paket_toplam_try": round(pack_toplam, 2),
            "tahmini_aylik_gelir_try": round(sub_toplam + pack_toplam, 2),
            "en_cok_satilan_paketler": [
                {"pack_key": r["pack_key"], "adet": r["adet"], "toplam_try": float(r["toplam"] or 0)}
                for r in pack_top
            ],
        },
        # c) Kredi kullanımları
        "krediler": [
            {
                "module": r["module"],
                "etiket": MODUL_ETIKET.get(r["module"], r["module"]),
                "satin_alinan": int(r["satin_alinan"] or 0),
                "tuketilen": int(r["tuketilen"] or 0),
            }
            for r in kredi_rows
        ],
        # d) Yapay Zeka istek sayısı + trend
        "ai_istekleri": {
            "toplam": ai_total or 0,
            "son_30g": ai_30d or 0,
            "gunluk_trend_7g": [
                {"tarih": str(r["d"]), "adet": r["c"]} for r in ai_trend
            ],
        },
        # e) En çok kullanılan araçlar
        "araclar": [
            {
                "event_type": r["event_type"],
                "etiket": MODUL_ETIKET.get(r["event_type"], r["event_type"]),
                "toplam": r["c"],
                "son_30g": tool_30d_map.get(r["event_type"], 0),
            }
            for r in tool_total
        ],
        # f) En aktif müşteriler
        "en_aktif_musteriler": [
            {
                "user_id": str(r["user_id"]),
                "email": r["email"],
                "name": r["name"],
                "islem_sayisi": r["c"],
                "son_islem": _iso(r["son"]),
            }
            for r in aktif_rows
        ],
        # g) Tahmini Yapay Zeka maliyeti (TAHMİNİ — gerçek fatura değil)
        "tahmini_maliyet": {
            "tahmini": True,
            "para_birimi": "TRY",
            "toplam": maliyet_toplam,
            "son_30g": maliyet_30g,
        },
        # h) Sağlayıcı dağılımı
        "saglayici_dagilimi": {
            "toplam": [{"provider": r["provider"], "adet": r["c"]} for r in provider_rows],
            "son_30g": [{"provider": r["provider"], "adet": r["c"]} for r in provider_30d_rows],
        },
        # i) Embedding API kullanımı (Google gemini-embedding-001, RAG arama/indeksleme)
        "embedding_kullanimi": {
            "tahmini": True,
            "para_birimi": "USD",
            "model": "gemini-embedding-001",
            "toplam": {
                "istek": int(embed_total_row["istek"] or 0),
                "oge": int(embed_total_row["ogeler"] or 0),
                "karakter": int(embed_total_row["karakter"] or 0),
                "tahmini_maliyet_usd": _embed_maliyet_usd(embed_total_row["karakter"]),
            },
            "son_24s": {
                "istek": int(embed_24h_row["istek"] or 0),
                "tahmini_maliyet_usd": _embed_maliyet_usd(embed_24h_row["karakter"]),
            },
            "son_7g": {
                "istek": int(embed_7d_row["istek"] or 0),
                "tahmini_maliyet_usd": _embed_maliyet_usd(embed_7d_row["karakter"]),
            },
            "son_30g": {
                "istek": int(embed_30d_row["istek"] or 0),
                "tahmini_maliyet_usd": _embed_maliyet_usd(embed_30d_row["karakter"]),
            },
            "tur_dagilimi": [
                {"request_type": r["request_type"], "adet": r["c"]} for r in embed_type_rows
            ],
        },
    })


@router.get("/users", response_model=APIResponse)
async def list_users(
    admin: CurrentUser = Depends(require_admin),
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    # NOT: is_active hem users hem tenants'ta var → tablo adıyla nitelendir
    # (aksi halde "ambiguous column" hatası → endpoint 500 → liste boş görünür).
    where = "WHERE u.is_active = TRUE"
    args: list = []
    if search:
        args.append(f"%{search}%")
        where += f" AND (u.email ILIKE ${len(args)} OR u.name ILIKE ${len(args)})"
    args.extend([limit, offset])

    async with service_session() as conn:
        # NOT: bir kullanıcı birden fazla tenant_members satırına sahip olabilir
        # (ör. hem kendi çalışma alanı hem davet edildiği bir ekip). Doğrudan
        # LEFT JOIN yapılırsa Postgres eşleşen satırlardan HANGİSİNİ döndüreceğini
        # garanti etmez — bu da admin panelde "plan değiştirdim, sayfayı
        # yeniledim eski haline döndü" görüntüsüne yol açar (aslında plan doğru
        # güncellenmiştir, ama liste her seferinde farklı bir tenant satırına
        # eşleşip eski/başka bir tenant'ın plan_tier'ını gösterebilir).
        # Bunun önüne geçmek için her kullanıcı için TEK ve HER ZAMAN AYNI
        # "birincil tenant"ı (owner rolü öncelikli, sonra en eski üyelik)
        # deterministik biçimde seçiyoruz.
        rows = await conn.fetch(
            f"""WITH primary_tenant AS (
                    SELECT DISTINCT ON (tm.user_id) tm.user_id, tm.tenant_id
                    FROM tenant_members tm
                    ORDER BY tm.user_id, (tm.role = 'owner') DESC, tm.created_at ASC
                )
                SELECT u.id, u.email, u.name, u.role, u.email_verified, u.created_at,
                       u.last_login_at,
                       t.id tid, t.name tname, t.plan_tier, t.beta_program
                FROM users u
                LEFT JOIN primary_tenant pt ON pt.user_id = u.id
                LEFT JOIN tenants t ON t.id = pt.tenant_id
                {where}
                ORDER BY (u.role = 'admin') DESC, u.created_at DESC
                LIMIT ${len(args) - 1} OFFSET ${len(args)}""",
            *args,
        )

    return APIResponse(ok=True, data={
        "users": [
            {
                "id": str(r["id"]),
                "email": r["email"],
                "name": r["name"],
                "role": r["role"],
                "email_verified": bool(r["email_verified"]),
                "created_at": r["created_at"].isoformat(),
                "last_login_at": r["last_login_at"].isoformat() if r["last_login_at"] else None,
                "tenant": {
                    "id": str(r["tid"]) if r["tid"] else None,
                    "name": r["tname"],
                    "plan": r["plan_tier"],
                    "beta": r["beta_program"],
                } if r["tid"] else None,
            }
            for r in rows
        ],
    })


class TenantUpgradeReq(BaseModel):
    plan_tier: str
    reason: str | None = None
    duration_days: int | None = None  # NULL = sınırsız
    beta_invited_by: str | None = None


@router.post("/tenants/{tenant_id}/upgrade", response_model=APIResponse)
async def manual_upgrade(
    tenant_id: str,
    payload: TenantUpgradeReq,
    admin: CurrentUser = Depends(require_admin),
):
    """Manuel tenant plan upgrade — beta hediye için."""
    valid_plans = {"free", "pro_solo", "pro_solo_uyap", "team", "team_uyap", "enterprise"}
    if payload.plan_tier not in valid_plans:
        raise HTTPException(400, "Geçersiz plan tier.")

    expires_at = None
    if payload.duration_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.duration_days)

    is_beta = payload.plan_tier != "free" and bool(payload.beta_invited_by)

    async with service_session() as conn:
        row = await conn.fetchrow("SELECT id FROM tenants WHERE id = $1::uuid", tenant_id)
        if not row:
            raise HTTPException(404, "Tenant bulunamadı.")

        await conn.execute(
            """UPDATE tenants SET
               plan_tier = $1::plan_tier,
               plan_started_at = NOW(),
               plan_expires_at = $2,
               beta_program = $3,
               beta_invited_by = $4,
               beta_signed_at = CASE WHEN $3 THEN NOW() ELSE beta_signed_at END,
               max_uyap_documents = CASE
                 WHEN $1::text = 'pro_solo_uyap' THEN 50
                 WHEN $1::text = 'team_uyap' THEN 250
                 WHEN $1::text = 'enterprise' THEN 100000
                 ELSE 0
               END,
               max_monthly_queries = CASE
                 WHEN $1::text = 'pro_solo_uyap' THEN 200
                 WHEN $1::text = 'team_uyap' THEN 1000
                 WHEN $1::text = 'enterprise' THEN 100000
                 ELSE 0
               END,
               max_users = CASE
                 WHEN $1::text LIKE 'team%' THEN 5
                 WHEN $1::text = 'enterprise' THEN 50
                 ELSE 1
               END
               WHERE id = $5::uuid""",
            payload.plan_tier, expires_at, is_beta, payload.beta_invited_by, tenant_id,
        )

        # NOT: /billing/current, tenant'ın en son 'active' subscriptions kaydıyla
        # tenants.plan_tier'ı otomatik senkronlar ("kendi kendine onarım" —
        # ödeme başarılı olduğu halde tenant güncellenmemiş eski/yarım
        # aktivasyonları düzeltmek için). Ama bu tabloyu burada güncellemezsek,
        # kullanıcı panelini her açtığında o eski subscription kaydı yüzünden
        # planı SESSİZCE eski haline geri alıyor — admin'in manuel değişikliği
        # "hiç işlememiş" gibi görünüyor. Var olan aktif abonelik varsa onu da
        # yeni plana eşitliyoruz ki iki tablo çelişmesin.
        await conn.execute(
            """UPDATE subscriptions SET plan_tier = $1::plan_tier, updated_at = NOW()
               WHERE tenant_id = $2::uuid AND status = 'active'""",
            payload.plan_tier, tenant_id,
        )

    await audit(
        action="admin.tenant_upgraded",
        user_id=admin.user_id,
        tenant_id=tenant_id,
        metadata={
            "plan": payload.plan_tier,
            "reason": payload.reason,
            "duration_days": payload.duration_days,
            "is_beta": is_beta,
        },
    )
    return APIResponse(ok=True, message=f"Tenant {payload.plan_tier} planına alındı.")


@router.get("/audit-log", response_model=APIResponse)
async def audit_log(
    admin: CurrentUser = Depends(require_admin),
    action: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
):
    where_parts = []
    args: list = []
    if action:
        args.append(action)
        where_parts.append(f"a.action = ${len(args)}")
    if user_id:
        args.append(user_id)
        where_parts.append(f"a.user_id = ${len(args)}::uuid")
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    args.append(limit)

    async with service_session() as conn:
        rows = await conn.fetch(
            f"""SELECT a.id, a.user_id, a.tenant_id, a.action, a.resource, a.ip_address,
                       a.success, a.metadata, a.created_at,
                       u.email AS user_email, u.name AS user_name
                FROM audit_log a
                LEFT JOIN users u ON u.id = a.user_id
                {where}
                ORDER BY a.created_at DESC LIMIT ${len(args)}""",
            *args,
        )

    return APIResponse(ok=True, data={
        "logs": [
            {
                "id": r["id"],
                "user_id": str(r["user_id"]) if r["user_id"] else None,
                "user_email": r["user_email"],
                "user_name": r["user_name"],
                "tenant_id": str(r["tenant_id"]) if r["tenant_id"] else None,
                "action": r["action"],
                "resource": r["resource"],
                "ip_address": str(r["ip_address"]) if r["ip_address"] else None,
                "success": r["success"],
                "metadata": r["metadata"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    })


@router.get("/feedback", response_model=APIResponse)
async def list_feedback(
    admin: CurrentUser = Depends(require_admin),
    status: str | None = None,
    severity: str | None = None,
    limit: int = 100,
):
    where_parts = []
    args: list = []
    if status:
        args.append(status)
        where_parts.append(f"f.status = ${len(args)}")
    if severity:
        args.append(severity)
        where_parts.append(f"f.severity = ${len(args)}")
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    args.append(limit)

    async with service_session() as conn:
        rows = await conn.fetch(
            f"""SELECT f.*, u.email user_email, u.name user_name
                FROM feedback f
                LEFT JOIN users u ON u.id = f.user_id
                {where}
                ORDER BY
                  CASE f.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                                  WHEN 'normal' THEN 2 ELSE 3 END,
                  f.created_at DESC
                LIMIT ${len(args)}""",
            *args,
        )

    return APIResponse(ok=True, data={
        "feedback": [
            {
                "id": str(r["id"]),
                "user": {"email": r["user_email"], "name": r["user_name"]} if r["user_email"] else None,
                "type": r["feedback_type"],
                "severity": r["severity"],
                "subject": r["subject"],
                "message": r["message"],
                "page_url": r["page_url"],
                "status": r["status"],
                "admin_note": r["admin_note"],
                "created_at": r["created_at"].isoformat(),
                "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
            }
            for r in rows
        ],
    })


class FeedbackUpdateReq(BaseModel):
    status: str | None = None
    admin_note: str | None = None


@router.patch("/feedback/{feedback_id}", response_model=APIResponse)
async def update_feedback(
    feedback_id: str,
    payload: FeedbackUpdateReq,
    admin: CurrentUser = Depends(require_admin),
):
    updates = []
    args: list = []
    if payload.status:
        args.append(payload.status)
        updates.append(f"status = ${len(args)}")
        if payload.status == "resolved":
            updates.append("resolved_at = NOW()")
    if payload.admin_note is not None:
        args.append(payload.admin_note)
        updates.append(f"admin_note = ${len(args)}")
    if not updates:
        return APIResponse(ok=True, message="Değişiklik yok.")

    args.append(feedback_id)
    async with service_session() as conn:
        await conn.execute(
            f"UPDATE feedback SET {', '.join(updates)} WHERE id = ${len(args)}::uuid",
            *args,
        )
    return APIResponse(ok=True, message="Geri bildirim güncellendi.")


# ---------------------------------------------------------------------------
# Paketler & Limitler — plan limitleri ve ek paket kataloğu (DB-override'lı).
# Admin panelden düzenlenir; ~30 sn cache TTL içinde uygulamaya yansır.
# ---------------------------------------------------------------------------

# Düzenlenebilir tier listesi (anonim hariç — anonimde plan satın alınmaz).
_CONFIG_TIERS = [
    "free", "pro_solo", "pro_solo_uyap", "team", "team_uyap", "enterprise",
]
# Limit düzenlenebilir araçlar.
_CONFIG_TOOLS = [
    "arama", "dilekce", "ihtarname", "ozet", "denetim",
    "karsi_argument", "sozlesme", "kvkk",
]


@router.get("/config", response_model=APIResponse)
async def get_config(admin: CurrentUser = Depends(require_admin)):
    """Paketler & Limitler UI'ı için tüm konfigürasyon.

    - tiers / tools: düzenlenebilir liste (etiketli).
    - plan_limits: kaydedilmiş override (DB) — {tool: {tier: int|null}}.
    - etkin_limitler: her (tool, tier) için ŞU AN geçerli limit (override yoksa
      koddan gelen varsayılan; null = sınırsız).
    - credit_packs: dinamik ek paket kataloğu (DB override varsa o, yoksa kod).
    """
    from api.rate_limit import tool_daily_limit
    from services import app_config, krediler

    # force=True: bu ekran admin'in az önce kaydettiği değeri HEMEN görmesi
    # gereken tek yer — worker-başına bellek cache'ini atlayıp DB'den taze
    # okur (bkz. app_config.get docstring'i: 4 worker process'i olduğu için
    # bir worker'ın yazdığı değer diğerlerine ~30sn'ye kadar yansımayabilir).
    override = await app_config.get_plan_limits(force=True)

    etkin: dict[str, dict[str, int | None]] = {}
    for tool in _CONFIG_TOOLS:
        etkin[tool] = {}
        for tier in _CONFIG_TIERS:
            etkin[tool][tier] = tool_daily_limit(tier, tool, override)

    paketler = await krediler.aktif_paketler(force=True)
    packs = {
        k: {
            "ad": p.get("ad", ""),
            "aciklama": p.get("aciklama", ""),
            "modul": p.get("modul"),
            "krediler": p.get("krediler") or {},
            "amount": float(p.get("amount") or 0),
        }
        for k, p in paketler.items()
    }

    return APIResponse(ok=True, data={
        "tiers": [{"key": t, "label": t} for t in _CONFIG_TIERS],
        "tools": [
            {"key": t, "label": krediler.MODUL_ETIKET.get(t, t)}
            for t in _CONFIG_TOOLS
        ],
        "plan_limits": override,        # kaydedilmiş override (boş olabilir)
        "etkin_limitler": etkin,        # şu an geçerli efektif limitler
        "credit_packs": packs,          # dinamik katalog
    })


@router.put("/config/plan-limits", response_model=APIResponse)
async def set_plan_limits(
    payload: dict,
    admin: CurrentUser = Depends(require_admin),
):
    """Plan limit override'ını kaydet. Body: {tool: {tier: int|null}}.

    Bilinmeyen tool/tier yok sayılır; değer int veya null/-1 (sınırsız) olmalı.
    """
    temiz: dict[str, dict] = {}
    for tool, tier_map in (payload or {}).items():
        if tool not in _CONFIG_TOOLS or not isinstance(tier_map, dict):
            continue
        ic: dict[str, int | None] = {}
        for tier, val in tier_map.items():
            if tier not in _CONFIG_TIERS:
                continue
            if val is None:
                ic[tier] = None
                continue
            if isinstance(val, bool):
                continue  # bool'u sayı sayma
            if isinstance(val, (int, float)):
                v = int(val)
                ic[tier] = None if v < 0 else v
        if ic:
            temiz[tool] = ic

    from services import app_config
    await app_config.set_value("plan_limits", temiz)
    await audit(
        action="admin.config.plan_limits_updated",
        user_id=admin.user_id,
        metadata={"tools": list(temiz.keys())},
    )
    return APIResponse(ok=True, message="Plan limitleri güncellendi.", data={"plan_limits": temiz})


@router.put("/config/credit-packs", response_model=APIResponse)
async def set_credit_packs(
    payload: dict,
    admin: CurrentUser = Depends(require_admin),
):
    """Ek paket kataloğunu kaydet. Body: {key: {ad, aciklama, modul, krediler, amount}}.

    Tüm katalog gönderilir (ekle/çıkar). Geçersiz paketler atlanır.
    """
    temiz: dict[str, dict] = {}
    for key, p in (payload or {}).items():
        if not key or not isinstance(p, dict):
            continue
        krediler_map = p.get("krediler") or {}
        if not isinstance(krediler_map, dict):
            continue
        ic_krediler: dict[str, int] = {}
        for m, n in krediler_map.items():
            if isinstance(n, bool):
                continue
            if isinstance(n, (int, float)) and int(n) > 0:
                ic_krediler[str(m)] = int(n)
        if not ic_krediler:
            continue  # kredisi olmayan paket anlamsız → atla
        try:
            amount = float(p.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        modul = p.get("modul")
        temiz[str(key)] = {
            "ad": str(p.get("ad") or key)[:200],
            "aciklama": str(p.get("aciklama") or "")[:500],
            "modul": str(modul) if modul else None,
            "krediler": ic_krediler,
            "amount": round(amount, 2),
        }

    if not temiz:
        raise HTTPException(400, "En az bir geçerli paket gerekli.")

    from services import app_config
    await app_config.set_value("credit_packs", temiz)
    await audit(
        action="admin.config.credit_packs_updated",
        user_id=admin.user_id,
        metadata={"packs": list(temiz.keys())},
    )
    return APIResponse(ok=True, message="Ek paket kataloğu güncellendi.", data={"credit_packs": temiz})


@router.post("/beta-invite", response_model=APIResponse)
async def beta_invite(
    payload: dict,
    admin: CurrentUser = Depends(require_admin),
):
    """Hızlı beta invite — email + plan + süre."""
    from services.email import send_email, _wrap

    email = payload.get("email")
    plan = payload.get("plan_tier", "pro_solo_uyap")
    days = int(payload.get("duration_days", 180))

    if not email:
        raise HTTPException(400, "Email zorunlu.")

    site = "https://hukukcuyapayzekasi.com"
    body = (
        f"<p>Merhaba,</p>"
        f"<p><strong>{admin.name or admin.email}</strong> sizi Hukuk Emsal Beta programına davet etti.</p>"
        f"<p>Beta avukat olarak <strong>{days} gün ücretsiz {plan}</strong> erişiminiz olacak.</p>"
        f"<p>Karşılığında: haftalık 15dk geri bildirim görüşmesi, ürünün lansmanında "
        f"kurucu kullanıcı olarak gösterilme.</p>"
        f"<p>Aşağıdaki bağlantıdan kayıt olun, hesap açtığınızda planınız otomatik aktif olacak.</p>"
    )
    await send_email(
        to=email,
        subject="🎁 Hukuk Emsal Beta Programı — Davetlisiniz",
        html=_wrap("Beta Davetiyesi", body, (f"{site}/kayit?ref=beta", "Hemen Kaydol")),
    )

    # Davet metadata'sı (tenant kuruluna kadar bekler, admin sonra manuel upgrade yapar)
    await audit(
        action="admin.beta_invite_sent",
        user_id=admin.user_id,
        metadata={"email": email, "plan": plan, "duration_days": days},
    )
    return APIResponse(ok=True, message=f"Beta davetiyesi {email} adresine gönderildi.")
