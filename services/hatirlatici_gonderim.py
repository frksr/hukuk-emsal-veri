"""Hatırlatıcı gönderimi — vadesi gelen 'pending' hatırlatıcıları e-posta ile
gönderir. service_session (RLS bypass) ile cross-user okuma yapar; her satırı
gönderdikten sonra status='sent'/'failed' olarak işaretler.

Periyodik çalıştırılır:
  - FastAPI startup'ında başlatılan hafif asyncio döngüsü (api/main.py), veya
  - Cron:  python -m services.hatirlatici_gonderim
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from services.email import send_email, _wrap

log = logging.getLogger("services.hatirlatici_gonderim")


def _govde(r) -> str:
    """Hatırlatıcı e-postası HTML gövdesi (başlık + not + kaynak özeti)."""
    parcalar = []
    if r["not_metni"]:
        parcalar.append(
            f"<p style='white-space:pre-wrap;'>{r['not_metni']}</p>"
        )
    if r["kaynak_ozet"]:
        etiket = {
            "not": "Not",
            "dosya": "Dosya",
            "uretim": "Üretim",
            "arama": "Arama",
            "serbest": "Hatırlatıcı",
        }.get(r["kaynak_tip"] or "serbest", "Kaynak")
        parcalar.append(
            f"<p style='color:#666;font-size:13px;border-left:3px solid #e5e7eb;"
            f"padding-left:12px;margin-top:16px;'>"
            f"<strong>{etiket}:</strong> {r['kaynak_ozet']}</p>"
        )
    if not parcalar:
        parcalar.append("<p>Planladığınız hatırlatıcının zamanı geldi.</p>")
    return "".join(parcalar)


async def bekleyen_hatirlaticilari_gonder(limit: int = 100) -> int:
    """Vadesi gelmiş (status='pending' AND remind_at <= now()) hatırlatıcıları
    gönderir. Gönderilen adedi döndürür."""
    from api.db import service_session

    now = datetime.now(timezone.utc)
    gonderilen = 0
    async with service_session() as conn:
        rows = await conn.fetch(
            """SELECT r.id, r.baslik, r.not_metni, r.kaynak_tip, r.kaynak_ozet,
                      r.channel, u.email, u.name
               FROM reminders r
               JOIN users u ON u.id = r.user_id
               WHERE r.status = 'pending'
                 AND r.remind_at <= $1
                 AND u.is_active = TRUE
               ORDER BY r.remind_at
               LIMIT $2""",
            now, limit,
        )

        for r in rows:
            # Şimdilik yalnızca e-posta kanalı destekleniyor.
            if (r["channel"] or "email") != "email":
                continue
            try:
                ok = await send_email(
                    to=r["email"],
                    subject=f"Hatırlatıcı: {(r['baslik'] or '')[:80]}",
                    html=_wrap(r["baslik"] or "Hatırlatıcı", _govde(r)),
                )
                if ok:
                    await conn.execute(
                        "UPDATE reminders SET status='sent', sent_at=NOW(), "
                        "updated_at=NOW() WHERE id=$1",
                        r["id"],
                    )
                    gonderilen += 1
                else:
                    await conn.execute(
                        "UPDATE reminders SET status='failed', updated_at=NOW() "
                        "WHERE id=$1",
                        r["id"],
                    )
                    log.warning("Hatırlatıcı gönderilemedi (send=false): %s", r["id"])
            except Exception as e:
                log.exception("Hatırlatıcı gönderim hatası: %s", r["id"])
                try:
                    await conn.execute(
                        "UPDATE reminders SET status='failed', updated_at=NOW() "
                        "WHERE id=$1",
                        r["id"],
                    )
                except Exception:
                    pass
    return gonderilen


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = asyncio.run(bekleyen_hatirlaticilari_gonder())
    print(f"Gönderilen hatırlatıcı: {n}")
