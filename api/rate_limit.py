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
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request

from api.auth import CurrentUser, get_optional_user
from api.db import service_session

# Günlük limitler
DAILY_LIMITS: dict[str, dict[str, int]] = {
    "anonim": {
        "arama": 20,
        "dilekce": 3,
        "ozet": 2,
        "ihtarname": 2,
        "denetim": 2,
        "karsi_argument": 2,
        "kvkk": 5,
        "sozlesme": 2,
        "sorgu": 0,  # UYAP — anonim için yok
        "faiz": 10_000,  # ~sınırsız
        "zamanasimi": 10_000,
        "trend": 50,
    },
    "free": {
        "arama": 40,
        "dilekce": 6,
        "ozet": 5,
        "ihtarname": 4,
        "denetim": 4,
        "karsi_argument": 4,
        "kvkk": 10,
        "sozlesme": 3,
        "sorgu": 0,  # UYAP free'de yok
        "faiz": 10_000,
        "zamanasimi": 10_000,
        "trend": 100,
    },
    # Pro ve üzeri için sınırsız
}

UNLIMITED_TIERS = {"pro_solo", "pro_solo_uyap", "team", "team_uyap", "enterprise"}


def _client_ip(request: Request) -> str:
    # Vercel/Cloudflare X-Forwarded-For
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


async def _current_count(
    event_type: str,
    user_id: Optional[str],
    ip: str,
) -> int:
    """Son 24 saatte bu user/IP'den bu event kaç kere atılmış?"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
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


async def _log_event(
    event_type: str,
    user_id: Optional[str],
    tenant_id: Optional[str],
    ip: str,
    user_agent: str,
):
    async with service_session() as conn:
        await conn.execute(
            """INSERT INTO usage_events
               (user_id, tenant_id, event_type, ip_address, user_agent)
               VALUES ($1, $2, $3, $4, $5)""",
            user_id, tenant_id, event_type, ip, user_agent[:500] if user_agent else None,
        )


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

        ip = _client_ip(request)
        ua = request.headers.get("user-agent", "")

        # Pro+ sınırsız
        if tier not in UNLIMITED_TIERS:
            limit_map = DAILY_LIMITS.get(tier, DAILY_LIMITS["anonim"])
            limit = limit_map.get(event_type, 10)
            current = await _current_count(event_type, user_id, ip)
            if current >= limit:
                raise HTTPException(
                    429,
                    {
                        "error": "rate_limit_exceeded",
                        "message": (
                            f"Günlük {event_type} limitiniz ({limit}) doldu. "
                            "Ücretsiz hesap açın veya yarın tekrar deneyin."
                        ),
                        "limit": limit,
                        "tier": tier,
                        "reset_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                    },
                )

        # Log et
        await _log_event(event_type, user_id, tenant_id, ip, ua)

    return check
