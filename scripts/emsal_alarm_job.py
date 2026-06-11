#!/usr/bin/env python3
"""Emsal alarmı eşleştirme job'ı — retention motoru.

Akış:
  1. Aktif tüm `saved_search_alerts` kayıtlarını çek.
  2. Her sorgu için RAG araması yap (top-k).
  3. Daha önce bildirilmemiş chunk_id'leri bul (son_sonuclar diff'i).
  4. Yeni sonuç varsa kullanıcıya e-posta gönder, son_sonuclar'ı güncelle.

Çalıştırma (scrape + embed pipeline'ı bittikten sonra):
  python3 scripts/emsal_alarm_job.py            # gerçek gönderim
  python3 scripts/emsal_alarm_job.py --dry-run  # e-posta atmadan dene

Cron önerisi (gece scraper'larından sonra, örn. 06:00):
  0 6 * * * cd /app && python3 scripts/emsal_alarm_job.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOP_K = 10  # her alarm için bakılacak sonuç sayısı


async def main(dry_run: bool) -> None:
    from api.db import init_pool, close_pool, service_session
    from services.rag import search
    from services.email import send_emsal_alarm_email

    await init_pool()
    try:
        async with service_session() as conn:
            alarmlar = await conn.fetch(
                """SELECT a.id, a.user_id, a.query, a.filters, a.son_sonuclar,
                          u.email, u.name
                   FROM saved_search_alerts a
                   JOIN users u ON u.id = a.user_id
                   WHERE a.aktif = TRUE AND u.is_active = TRUE"""
            )
        print(f"{len(alarmlar)} aktif alarm bulundu.")

        gonderilen = 0
        for alarm in alarmlar:
            query = alarm["query"]
            filters = alarm["filters"] or {}
            if isinstance(filters, str):
                filters = json.loads(filters or "{}")

            where = None
            f = {k: v for k, v in filters.items()
                 if k in ("source", "court_chamber") and v}
            if len(f) == 1:
                where = f
            elif len(f) > 1:
                where = {"$and": [{k: v} for k, v in f.items()]}

            try:
                # Senkron RAG çağrısı — job'da event loop kaygısı yok ama yine
                # de thread'e alalım ki email I/O'su paralel akabilsin.
                sonuclar = await asyncio.to_thread(search, query, TOP_K, where)
            except Exception as e:
                print(f"  ! {query!r} araması başarısız: {e}")
                continue

            yeni_ids = [s["chunk_id"] for s in sonuclar]
            onceki = set(alarm["son_sonuclar"] or [])
            if isinstance(alarm["son_sonuclar"], str):
                onceki = set(json.loads(alarm["son_sonuclar"] or "[]"))

            yeniler = [s for s in sonuclar if s["chunk_id"] not in onceki]
            now = datetime.now(timezone.utc)

            if not onceki:
                # İlk çalıştırma: baseline kur, bildirim gönderme (spam olmasın)
                async with service_session() as conn:
                    await conn.execute(
                        """UPDATE saved_search_alerts
                           SET son_kontrol = $1, son_sonuclar = $2::jsonb
                           WHERE id = $3""",
                        now, json.dumps(yeni_ids), alarm["id"],
                    )
                print(f"  • {query!r}: baseline kuruldu ({len(yeni_ids)} sonuç)")
                continue

            if not yeniler:
                async with service_session() as conn:
                    await conn.execute(
                        "UPDATE saved_search_alerts SET son_kontrol = $1 WHERE id = $2",
                        now, alarm["id"],
                    )
                continue

            kararlar = [
                {
                    "baslik": (s.get("meta") or {}).get("court_chamber", "")
                    + " · " + str((s.get("meta") or {}).get("case_no", "")),
                    "ozet": (s.get("text") or "")[:300],
                    "chunk_id": s["chunk_id"],
                }
                for s in yeniler
            ]

            if dry_run:
                print(f"  → [DRY] {alarm['email']}: {query!r} için {len(yeniler)} yeni karar")
            else:
                ok = await send_emsal_alarm_email(
                    to=alarm["email"], name=alarm["name"],
                    query=query, yeni_kararlar=kararlar,
                )
                if ok:
                    gonderilen += 1
                async with service_session() as conn:
                    await conn.execute(
                        """UPDATE saved_search_alerts
                           SET son_kontrol = $1, son_bildirim = $1,
                               son_sonuclar = $2::jsonb
                           WHERE id = $3""",
                        now, json.dumps(yeni_ids), alarm["id"],
                    )
                print(f"  ✓ {alarm['email']}: {query!r} → {len(yeniler)} yeni karar bildirildi")

        print(f"Bitti — {gonderilen} e-posta gönderildi.")
    finally:
        await close_pool()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.dry_run))
