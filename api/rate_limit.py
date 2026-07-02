"""Tier bazlı rate limiting.

PostgreSQL'de usage_events tablosuna her isteği log'lar,
günlük kotayı kontrol eder.

Tier limitleri (günlük):
- anonim:        20 emsal, 3 dilekçe, hesaplayıcı sınırsız
- free:          40 emsal, 6 dilekçe, hesaplayıcı sınırsız, 5 ozet
- pro_solo:      sınırsız
- pro_solo_uyap: sınırsız + UYAP kotası
- team:          sınırsız
- team_uyap:     sınırsız + UYAP kotası
- enterprise:    sınırsız
"""
from __future__ import annotations
import calendar
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request

from api.auth import CurrentUser, get_optional_user
from api.db import service_session

# Günlük limitler
DAILY_LIMITS: dict[str, dict[str, int]] = {
    # Anonim (giriş yapmamış): Yapay Zeka araçları 0 → özellik kullanmak için kayıt şart.
    "anonim": {
        "arama": 20,
        "dilekce": 0,
        "ozet": 0,
        "ihtarname": 0,
        "denetim": 0,
        "karsi_argument": 0,
        "kvkk": 5,
        "sozlesme": 0,
        "sorgu": 0,  # UYAP — anonim için yok
        "faiz": 10_000,  # ~sınırsız
        "zamanasimi": 10_000,
        "trend": 50,
    },
    # Free (giriş yapmış ücretsiz): Yapay Zeka araçlarında küçük günlük DENEME hakkı.
    # Hak bitince Pro veya ek paket kredisi gerekir.
    "free": {
        "arama": 40,
        "dilekce": 2,
        "ozet": 2,
        "ihtarname": 2,
        "denetim": 2,
        "karsi_argument": 2,
        "kvkk": 10,
        "sozlesme": 2,
        "sorgu": 0,  # UYAP free'de yok
        "faiz": 10_000,
        "zamanasimi": 10_000,
        "trend": 100,
    },
    # Pro ve üzeri için sınırsız
}

UNLIMITED_TIERS = {"pro_solo", "pro_solo_uyap", "team", "team_uyap", "enterprise"}

# Pahalı araçlar: Pro+ planlarda bile SINIRSIZ değildir; her plan kendi günlük
# hakkına tabidir. (Sözleşme analizi tek seferde birden çok LLM çağrısı yaptığından
# maliyetli — bu yüzden pakete göre farklı günlük hak verilir.)
PER_PLAN_TOOLS = {"sozlesme"}

# Sözleşme analizi — plan bazlı günlük kullanım hakkı.
SOZLESME_LIMITS: dict[str, int] = {
    "anonim": 0,
    "free": 1,            # deneme: günde 1
    "pro_solo": 5,
    "pro_solo_uyap": 8,
    "team": 20,
    "team_uyap": 40,
    "enterprise": 200,    # pratikte sınırsız
}


def tool_daily_limit(
    tier: str, event_type: str, override: Optional[dict] = None
) -> Optional[int]:
    """Bir (plan, araç) için günlük limit. None → sınırsız.

    - override verilmiş ve override[event_type][tier] mevcutsa onu kullanır
      (değer None veya -1 ise sınırsız → None döner). DB'den gelen admin ayarı.
    - Pahalı araçlar (PER_PLAN_TOOLS): her planın kendi limiti (Pro'da bile sınırlı).
    - Diğer araçlar: Pro+ sınırsız (None); ücretsiz/anonim için DAILY_LIMITS.
    """
    if override:
        tool_map = override.get(event_type)
        if isinstance(tool_map, dict) and tier in tool_map:
            v = tool_map[tier]
            if v is None or v == -1:
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                pass  # bozuk değer → koddan gelen varsayılana düş
    if event_type in PER_PLAN_TOOLS:
        if event_type == "sozlesme":
            return SOZLESME_LIMITS.get(tier, SOZLESME_LIMITS["free"])
        # ileride başka pahalı araçlar eklenirse buraya
        return SOZLESME_LIMITS.get(tier, 1)
    if tier in UNLIMITED_TIERS:
        return None
    return DAILY_LIMITS.get(tier, DAILY_LIMITS["anonim"]).get(event_type, 10)


def _client_ip(request: Request) -> str:
    # Vercel/Cloudflare X-Forwarded-For
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def donem_baslangici() -> datetime:
    """İçinde bulunulan AYIN başı (UTC). Takvim-ayı penceresi — anonim/yedek."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def donem_bitisi() -> datetime:
    """Bir sonraki ayın başı — takvim-ayı penceresinin sıfırlanma anı (yedek)."""
    b = donem_baslangici()
    if b.month == 12:
        return b.replace(year=b.year + 1, month=1)
    return b.replace(month=b.month + 1)


def _ayli(anchor: datetime, y: int, m: int) -> datetime:
    """anchor.day gününü (ay kısa ise son güne kırparak) y/m ayına taşır, 00:00 UTC."""
    son = calendar.monthrange(y, m)[1]
    return datetime(y, m, min(anchor.day, son), 0, 0, 0, 0, tzinfo=timezone.utc)


def donem_baslangici_anchor(anchor: datetime, now: Optional[datetime] = None) -> datetime:
    """Aboneliğin/kaydın 'gününe' demirlenmiş AYLIK pencerenin başı.

    Örn. ayın 17'sinde abone olduysa pencere her ayın 17'sinde yenilenir.
    `anchor`'dan yalnızca GÜN bilgisi kullanılır; en son aylık yıldönümü (<= now) döner.
    """
    now = now or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    cand = _ayli(anchor, now.year, now.month)
    if cand > now:
        # Bu ayki yıldönümü henüz gelmedi → bir önceki ay.
        y, m = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
        cand = _ayli(anchor, y, m)
    return cand


def donem_bitisi_anchor(anchor: datetime, now: Optional[datetime] = None) -> datetime:
    """Demirli aylık pencerenin bitişi = bir sonraki yıldönümü (kotanın sıfırlanacağı an)."""
    now = now or datetime.now(timezone.utc)
    bas = donem_baslangici_anchor(anchor, now)
    y, m = (bas.year + 1, 1) if bas.month == 12 else (bas.year, bas.month + 1)
    return _ayli(anchor, y, m)


async def kullanici_donem_penceresi(
    user_id: Optional[str], tenant_id: Optional[str],
) -> tuple[datetime, datetime, bool]:
    """Kullanıcının içinde bulunduğu kota penceresi: (baslangic, bitis, odeme_aktif).

    - Ücretli (aktif abonelik): pencere abonelik gününe demirlenir. Demir noktası
      subscriptions.current_period_start (yoksa started_at). Webhook her yenilemede
      current_period_start'ı günceller; gelmese bile gün-bazlı yıldönümüne taşınır.
    - Aktif abonelik yoksa: pencere kullanıcının KAYIT gününe demirlenir (free).
    - odeme_aktif: ücretli kullanıcı için son dönem ödemesi alındı mı (status='active').
      Ödeme alınamadıysa tenant zaten 'free'e düşürülür; bu bayrak bilgi amaçlıdır.
    """
    now = datetime.now(timezone.utc)
    anchor: Optional[datetime] = None
    odeme_aktif = True
    try:
        async with service_session() as conn:
            if tenant_id:
                row = await conn.fetchrow(
                    """SELECT status, current_period_start, started_at
                       FROM subscriptions
                       WHERE tenant_id = $1 AND status = 'active'
                       ORDER BY created_at DESC LIMIT 1""",
                    tenant_id,
                )
                if row:
                    anchor = row["current_period_start"] or row["started_at"]
                    odeme_aktif = True
            if anchor is None and user_id:
                anchor = await conn.fetchval(
                    "SELECT created_at FROM users WHERE id = $1", user_id,
                )
    except Exception:
        anchor = None
    if anchor is None:
        return donem_baslangici(), donem_bitisi(), odeme_aktif
    bas = donem_baslangici_anchor(anchor, now)
    bit = donem_bitisi_anchor(anchor, now)
    return (bas, bit, odeme_aktif)


async def _current_count(
    event_type: str,
    user_id: Optional[str],
    ip: str,
    cutoff: Optional[datetime] = None,
) -> int:
    """Pencere başından (cutoff) beri bu user/IP'den bu event kaç kere atılmış?

    cutoff verilmezse takvim ayı başı kullanılır (yedek/anonim).
    """
    if cutoff is None:
        cutoff = donem_baslangici()
    # Sistem-seviyesi sayaç (anonim kullanıcılar dahil) → service_session.
    async with service_session() as conn:
        if user_id:
            row = await conn.fetchrow(
                """SELECT COUNT(*) c FROM usage_events
                   WHERE user_id = $1 AND event_type = $2 AND created_at > $3""",
                user_id, event_type, cutoff,
            )
        else:
            row = await conn.fetchrow(
                """SELECT COUNT(*) c FROM usage_events
                   WHERE ip_address = $1 AND user_id IS NULL
                     AND event_type = $2 AND created_at > $3""",
                ip, event_type, cutoff,
            )
        return int(row["c"]) if row else 0


# LLM (Yapay Zeka) kullanan modüller — bu olaylarda usage_events.metadata'ya
# o an aktif/varsayılan LLM sağlayıcısı yazılır (analitik: sağlayıcı dağılımı).
# Hesaplayıcılar (faiz, zamanasimi) ve saf emsal arama LLM kullanmaz → dahil değil.
AI_MODULES: frozenset[str] = frozenset({
    "dilekce", "ihtarname", "ozet", "denetim",
    "karsi_argument", "sozlesme", "kvkk", "sorgu",
})


def _ai_provider_meta(event_type: str) -> dict:
    """AI modülleri için {'provider': <varsayılan sağlayıcı>} döndürür.

    Yalnızca hangi LLM sağlayıcısının VARSAYILAN olduğunu kaydeder (API çağrısı
    yapmaz). Sağlayıcı okunamazsa boş dict döner — log yine de yazılır.
    """
    if event_type not in AI_MODULES:
        return {}
    try:
        from llm.provider import _get_default_provider
        return {"provider": _get_default_provider()}
    except Exception:
        return {}


async def _log_event(
    event_type: str,
    user_id: Optional[str],
    tenant_id: Optional[str],
    ip: str,
    user_agent: str,
    metadata: Optional[dict] = None,
):
    import json as _json

    meta = dict(metadata) if metadata else {}
    # AI modüllerinde sağlayıcıyı ekle (zaten verilmemişse).
    if "provider" not in meta:
        meta.update(_ai_provider_meta(event_type))

    async with service_session() as conn:
        await conn.execute(
            """INSERT INTO usage_events
               (user_id, tenant_id, event_type, ip_address, user_agent, metadata)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb)""",
            user_id, tenant_id, event_type, ip,
            user_agent[:500] if user_agent else None,
            _json.dumps(meta, ensure_ascii=False),
        )


async def atomik_kota_kullan(
    event_type: str,
    user_id: Optional[str],
    tenant_id: Optional[str],
    ip: str,
    user_agent: str,
    limit: Optional[int],
    cutoff: datetime,
    log_et: bool = True,
) -> bool:
    """Kota sayımı + usage_event kaydını TEK transaction'da, advisory lock
    altında yapar → eşzamanlı isteklerle limit AŞILAMAZ (TOCTOU kapatıldı).

    - limit None → sınırsız; yalnızca (log_et ise) log yazılır, True döner.
    - limit doldu → hiçbir şey yazılmaz, False döner (çağıran 402/429 üretir
      veya kredi yoluna düşer).
    - log_et=False → sayım/kilit yapılır ama event yazılmaz (AI modüllerinde
      event'i router'ın kaydet_uretim'i yazar; kilit yine de eşzamanlı
      kontrolleri sıralar).
    """
    import json as _json

    kilit_anahtari = f"kota:{user_id or ip}:{event_type}"

    meta = _ai_provider_meta(event_type)

    async with service_session() as conn:
        async with conn.transaction():
            # Aynı kullanıcı+araç için kontroller sıralansın (transaction sonunda
            # otomatik bırakılır).
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1))", kilit_anahtari
            )

            if limit is not None:
                if user_id:
                    current = await conn.fetchval(
                        """SELECT COUNT(*) FROM usage_events
                           WHERE user_id = $1 AND event_type = $2 AND created_at > $3""",
                        user_id, event_type, cutoff,
                    )
                else:
                    current = await conn.fetchval(
                        """SELECT COUNT(*) FROM usage_events
                           WHERE ip_address = $1 AND user_id IS NULL
                             AND event_type = $2 AND created_at > $3""",
                        ip, event_type, cutoff,
                    )
                if int(current or 0) >= limit:
                    return False

            if log_et:
                await conn.execute(
                    """INSERT INTO usage_events
                       (user_id, tenant_id, event_type, ip_address, user_agent, metadata)
                       VALUES ($1, $2, $3, $4, $5, $6::jsonb)""",
                    user_id, tenant_id, event_type, ip,
                    user_agent[:500] if user_agent else None,
                    _json.dumps(meta, ensure_ascii=False),
                )
    return True


def rate_limit_for(event_type: str):
    """Decorator factory. Kullanım:

        @router.post("/", dependencies=[Depends(rate_limit_for("arama"))])
        async def search(...):
            ...
    """
    async def check(
        request: Request,
        user: Optional[CurrentUser] = Depends(get_optional_user),
    ):
        tier = "anonim"
        user_id = None
        tenant_id = None
        if user:
            user_id = user.user_id
            tenant_id = user.tenant_id
            tier = user.tenant_plan or "free"
            # Admin → sınırsız (sistemi izleyen ana kullanıcı).
            if getattr(user, "role", None) == "admin":
                tier = "enterprise"

        ip = _client_ip(request)
        ua = request.headers.get("user-agent", "")

        # Pro+ sınırsız
        limit: Optional[int] = None
        bas, bitis, _ = await kullanici_donem_penceresi(user_id, tenant_id)
        if tier not in UNLIMITED_TIERS:
            limit_map = DAILY_LIMITS.get(tier, DAILY_LIMITS["anonim"])
            limit = limit_map.get(event_type, 10)

        # Sayım + log atomik (eşzamanlı isteklerle limit aşılamaz).
        izin = await atomik_kota_kullan(
            event_type, user_id, tenant_id, ip, ua, limit, bas, log_et=True
        )
        if not izin:
            raise HTTPException(
                429,
                {
                    "error": "rate_limit_exceeded",
                    "message": (
                        f"Dönemlik {event_type} limitiniz ({limit}) doldu. "
                        "Üst pakete geçin, ek paket alın veya yenileme tarihinde tekrar deneyin."
                    ),
                    "limit": limit,
                    "tier": tier,
                    "reset_at": bitis.isoformat(),
                },
            )

    return check
