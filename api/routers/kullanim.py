"""Kullanım panosu — bugünkü ve dönemlik (aylık) araç bazlı kullanım + plan limitleri.

usage_events tablosundan beslenir (rate_limit._log_event her kullanımda yazar).
Limitler api/rate_limit.tool_daily_limit ile hesaplanır; admin panelden yapılan
override'lar (services.app_config.get_plan_limits) da uygulanır. Aylık pencere,
kota.py/rate_limit.py ile birebir aynı mantıkla abonelik/kayıt gününe demirlenir.

Kayıt (main.py): app.include_router(kullanim.router, prefix="/api/me/kullanim", tags=["account"])
Frontend: GET /api/proxy/me/kullanim
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from api.auth import CurrentUser, get_current_user
from api.db import db_session
from api.rate_limit import kullanici_donem_penceresi, tool_daily_limit
from api.schemas import APIResponse
from services import krediler

router = APIRouter()

# Panoda gösterilen araçlar (me.py /rapor ile aynı çekirdek liste)
ARACLAR = ["arama", "dilekce", "ihtarname", "ozet", "denetim",
           "karsi_argument", "sozlesme", "kvkk", "faiz", "zamanasimi"]

# MODUL_ETIKET'te olmayan hesaplayıcılar için Türkçe etiketler
_EK_ETIKET = {"faiz": "Faiz & Tahsilat", "zamanasimi": "Zamanaşımı"}


def _etiket(tool: str) -> str:
    return krediler.MODUL_ETIKET.get(tool) or _EK_ETIKET.get(tool, tool)


def _limit(tier: str, tool: str, override: dict | None) -> int | None:
    """Plan limitini normalize eder: None veya >= 10_000 → sınırsız (None)."""
    lim = tool_daily_limit(tier, tool, override)
    if lim is None or lim >= 10_000:
        return None
    return int(lim)


@router.get("", response_model=APIResponse, summary="Kullanım panosu (bugün + bu dönem)")
@router.get("/", response_model=APIResponse, include_in_schema=False)
async def kullanim_panosu(user: CurrentUser = Depends(get_current_user)):
    """Araç bazlı bugünkü ve dönemlik kullanım + plan limitleri.

    Dönüş: {gunluk: [{tool, etiket, used, limit}], aylik: [...]} — limit None ise
    frontend "Sınırsız" gösterir.
    """
    from services import app_config

    now = datetime.now(timezone.utc)
    gun_basi = now.replace(hour=0, minute=0, second=0, microsecond=0)
    donem_basi, donem_bitis, _ = await kullanici_donem_penceresi(
        user.user_id, user.tenant_id,
    )

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        gunluk_rows = await conn.fetch(
            """SELECT event_type, COUNT(*) c FROM usage_events
               WHERE user_id = $1 AND created_at >= $2 GROUP BY event_type""",
            user.user_id, gun_basi,
        )
        aylik_rows = await conn.fetch(
            """SELECT event_type, COUNT(*) c FROM usage_events
               WHERE user_id = $1 AND created_at >= $2 GROUP BY event_type""",
            user.user_id, donem_basi,
        )

    gunluk_map = {r["event_type"]: r["c"] for r in gunluk_rows}
    aylik_map = {r["event_type"]: r["c"] for r in aylik_rows}

    # Admin → sınırsız (enterprise); rate_limit.py ile aynı kural.
    tier = "enterprise" if user.role == "admin" else (user.tenant_plan or "free")
    override = await app_config.get_plan_limits()

    def _satirlar(kullanim_map: dict) -> list[dict]:
        return [
            {
                "tool": t,
                "etiket": _etiket(t),
                "used": int(kullanim_map.get(t, 0)),
                "limit": _limit(tier, t, override),
            }
            for t in ARACLAR
        ]

    return APIResponse(ok=True, data={
        "tier": tier,
        "gunluk": _satirlar(gunluk_map),
        "aylik": _satirlar(aylik_map),
        "donem_bitis": donem_bitis.isoformat(),
        "guncel": now.isoformat(),
    })
