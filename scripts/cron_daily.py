"""Günlük bakım işleri — TEK giriş noktası.

NEDEN
-----
Bazı kritik arka plan işleri yazılmış ama hiçbir zamanlayıcıya bağlanmamıştı:

  * `scripts/purge_deleted.py` — KVKK m.7 kalıcı silme. Kullanıcıya "verileriniz
    30 gün içinde tamamen silinir" deniyor ama betik elle çalıştırılmadıkça
    hiçbir şey silinmiyordu. Uyum açısından en riskli boşluk buydu.
  * `scripts/update_faiz_oranlari.py` — faiz oranları güncellemesi. Bayat oran,
    hesaplayıcının yanlış sonuç vermesi demek.
  * `scripts/emsal_alarm_job.py` — kullanıcıların emsal alarmları.

Her biri ayrı ayrı zamanlanmak yerine buradan çağrılır: tek Cloud Scheduler
job'u, tek log akışı, tek hata bildirimi.

KURULUM (GCP)
-------------
    bash infra/gcp/setup_cron.sh

Bu script, Cloud Run Job'u oluşturup Cloud Scheduler ile her gece 03:15'te
(Europe/Istanbul) tetikler. Ayrıntı: DR_RUNBOOK.md.

ELLE ÇALIŞTIRMA
---------------
    python -m scripts.cron_daily              # hepsi
    python -m scripts.cron_daily --dry-run    # hiçbir şey silmez/yazmaz
    python -m scripts.cron_daily --only purge_deleted

ÇIKIŞ KODU
----------
0 = tüm işler başarılı, 1 = en az bir iş hata verdi (Scheduler yeniden dener).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
import traceback

log = logging.getLogger("cron_daily")


async def _purge_deleted(dry_run: bool) -> dict:
    from scripts.purge_deleted import purge
    return await purge(dry_run=dry_run)


async def _faiz_oranlari(dry_run: bool) -> dict:
    if dry_run:
        return {"skipped": "dry-run"}
    from scripts.update_faiz_oranlari import main as faiz_main
    # Senkron + ağ çağrısı yapıyor → event loop'u bloklamasın.
    await asyncio.to_thread(faiz_main)
    return {"ok": True}


async def _emsal_alarmlari(dry_run: bool) -> dict:
    from scripts.emsal_alarm_job import main as alarm_main
    await alarm_main(dry_run=dry_run)
    return {"ok": True}


#: (ad, fonksiyon, kritik_mi). Kritik işler başarısız olursa admin'e mail gider.
ISLER = [
    ("purge_deleted", _purge_deleted, True),   # KVKK — kaçırılamaz
    ("faiz_oranlari", _faiz_oranlari, False),
    ("emsal_alarmlari", _emsal_alarmlari, False),
]


async def _admin_uyar(basliklar: list[str], detay: str) -> None:
    """Kritik iş başarısız olduğunda admin'e e-posta. Sessiz kalmasın."""
    admin = os.environ.get("ADMIN_EMAIL")
    if not admin:
        log.error("ADMIN_EMAIL yok — kritik cron hatası bildirilemedi.")
        return
    try:
        from services.email import send_email

        await send_email(
            to=admin,
            subject=f"[hukuk-api] Günlük bakım işi başarısız: {', '.join(basliklar)}",
            html=(
                "<p>Aşağıdaki günlük bakım işleri hata verdi:</p>"
                f"<p><b>{', '.join(basliklar)}</b></p><pre>{detay[:4000]}</pre>"
                "<p>KVKK kalıcı silme (purge_deleted) bu listede ise "
                "sebebi giderilene kadar silme taahhüdü yerine getirilmiyor demektir.</p>"
            ),
        )
    except Exception as e:
        log.error("Uyarı e-postası gönderilemedi: %s", e)


async def calistir(dry_run: bool, only: str | None) -> int:
    sonuclar: dict[str, dict] = {}
    hatalar: list[str] = []
    izler: list[str] = []

    for ad, fn, kritik in ISLER:
        if only and ad != only:
            continue
        t0 = time.perf_counter()
        try:
            sonuclar[ad] = await fn(dry_run)
            log.info("✓ %s (%.1fs) → %s", ad, time.perf_counter() - t0, sonuclar[ad])
        except Exception as e:
            sonuclar[ad] = {"error": str(e)}
            log.exception("✗ %s başarısız", ad)
            if kritik:
                hatalar.append(ad)
                izler.append(f"--- {ad} ---\n{traceback.format_exc()}")

    if hatalar:
        await _admin_uyar(hatalar, "\n".join(izler))

    from api.db import close_pool
    await close_pool()

    print(sonuclar)
    return 1 if hatalar else 0


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    ap = argparse.ArgumentParser(description="Günlük bakım işleri")
    ap.add_argument("--dry-run", action="store_true", help="hiçbir şey değiştirme")
    ap.add_argument("--only", help="tek bir işi çalıştır", default=None,
                    choices=[ad for ad, _, _ in ISLER])
    args = ap.parse_args()
    return asyncio.run(calistir(args.dry_run, args.only))


if __name__ == "__main__":
    sys.exit(main())
