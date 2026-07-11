"""Uptime self-check — arka plan döngüsü (api/main.py lifespan'inden çağrılır).

ÖNEMLİ SINIRLAMA: Bu kontrol API sürecinin İÇİNDE çalışır. API instance'ının
kendisi çöker / Cloud Run tarafından durdurulursa bu döngü de onunla birlikte
durur ve alarm maili GÖNDERİLEMEZ. Yani "API instance ayakta kalamıyor" tipi
kesintiyi (örn. başlayıp saniyeler içinde kapatılan revizyon) bu mekanizma
HER ZAMAN yakalayamaz — bunun garantisi için API'den BAĞIMSIZ çalışan bir
izleme şart (GCP Console → Monitoring → Uptime Checks, ya da UptimeRobot).
Bkz. DR_RUNBOOK.md.

Bu modülün yakaladığı senaryolar:
  - API ayaktayken frontend (SITE_URL) erişilemez oluyorsa
  - API ayaktayken site 5xx dönüyorsa
  - Kesinti düzeldiğinde otomatik "düzeldi" bildirimi
"""
from __future__ import annotations

import logging
import os
import time

import httpx

from services.email import send_email

log = logging.getLogger("services.uptime_monitor")

SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukcuyapayzekasi.com")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL") or os.environ.get("FEEDBACK_ADMIN_EMAIL")
CHECK_TIMEOUT_S = 10
ALERT_COOLDOWN_S = 3600  # site düşük kalırken tekrar hatırlatma sıklığı (spam önleme)

_state = {
    "down_since": None,      # float epoch veya None (şu an ayakta)
    "last_alert_at": 0.0,
}


async def _check_once() -> tuple[bool, str]:
    """Siteyi tek seferlik kontrol eder. (ok, detay) döndürür."""
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_S, follow_redirects=True) as client:
            r = await client.get(SITE_URL)
        return (r.status_code < 500), f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def check_and_alert() -> None:
    """5 dk'da bir çağrılır: kontrol eder, durum değiştiyse admin'e mail atar."""
    if not ADMIN_EMAIL:
        log.warning("ADMIN_EMAIL tanımlı değil — uptime alarmı gönderilemez.")
        return

    ok, detay = await _check_once()
    now = time.time()

    if ok:
        if _state["down_since"] is not None:
            kesinti_sn = now - _state["down_since"]
            dk, sn = int(kesinti_sn // 60), int(kesinti_sn % 60)
            log.info("Site tekrar erişilebilir (kesinti ~%d dk %d sn).", dk, sn)
            await send_email(
                to=ADMIN_EMAIL,
                subject=f"[Hukuk Emsal] Site tekrar AYAKTA ({SITE_URL})",
                html=(
                    f"<p><strong>{SITE_URL}</strong> tekrar erişilebilir hale geldi.</p>"
                    f"<p>Kesinti süresi: ~{dk} dk {sn} sn.</p>"
                ),
                text=f"{SITE_URL} tekrar erişilebilir. Kesinti: ~{dk} dk {sn} sn.",
            )
        _state["down_since"] = None
        _state["last_alert_at"] = 0.0
        return

    # DOWN
    log.warning("Uptime kontrolü BAŞARISIZ: %s", detay)
    if _state["down_since"] is None:
        _state["down_since"] = now

    if now - _state["last_alert_at"] >= ALERT_COOLDOWN_S:
        _state["last_alert_at"] = now
        kesinti_sn = now - _state["down_since"]
        dk = int(kesinti_sn // 60)
        await send_email(
            to=ADMIN_EMAIL,
            subject=f"[Hukuk Emsal] Site ERİŞİLEMİYOR ({SITE_URL})",
            html=(
                f"<p><strong>{SITE_URL}</strong> erişilemiyor.</p>"
                f"<p>Hata: {detay}</p>"
                f"<p>Kesinti süresi: ~{dk} dakika.</p>"
                "<p style='color:#888;font-size:12px;'>Not: bu kontrol API süreci "
                "içinde çalışır; API instance'ının kendisi tamamen düşerse bu mail "
                "de gitmeyebilir. GCP Console → Monitoring → Uptime Checks kurulumu "
                "ayrıca tamamlanmalı.</p>"
            ),
            text=f"{SITE_URL} erişilemiyor. Hata: {detay}. Kesinti: ~{dk} dk.",
        )
