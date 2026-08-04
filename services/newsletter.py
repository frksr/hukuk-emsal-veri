"""Haftalık bülten — blog yayın bildirimi.

Yeni bir makale yayınlandığında (api/routers/icerik.py admin_yayinla) aktif
abonelere ("status='active'") kısa bir "yeni yazı yayınlandı" bildirimi
gönderir. Makalenin tam metni BİLEREK e-postaya gömülmez — yalnızca özet +
siteye yönlendiren bir bağlantı gönderilir (site trafiği/dönüşüm ve SEO
açısından, iç link'lerin ve sayfa görüntülenmesinin değeri tam-metin
e-postadan daha yüksektir).
"""
from __future__ import annotations

import asyncio
import logging
import os

from api.db import service_session
from services.email import send_new_post_email

log = logging.getLogger("services.newsletter")

SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukcuyapayzekasi.com")

# Ardışık gönderimler arası küçük gecikme — abone sayısı büyüdükçe SMTP
# sağlayıcısını tek seferde yüzlerce istekle boğmamak için (mevcut toplu
# gönderim örneklerinde, ör. waitlist.send_invites, bu yok; oradaki liste
# ≤100 ile sınırlı, bülten abone sayısı sınırsız büyüyebileceği için eklendi).
_GONDERIM_ARASI_BEKLEME_SN = 0.2


async def notify_subscribers_of_new_post(*, slug: str, title: str, excerpt: str) -> dict:
    """status='active' olan tüm abonelere yeni yazı bildirimi gönderir.

    Tek bir abonenin gönderim hatası diğerlerini etkilemez (loglanır, atlanır).
    Başarılı gönderimlerde `last_sent_at` güncellenir. Sonuç özeti döner.
    """
    url = f"{SITE_URL}/blog/{slug}"
    gonderilen = 0
    basarisiz = 0

    async with service_session() as conn:
        rows = await conn.fetch(
            "SELECT id, email, unsubscribe_token FROM newsletter_subscribers "
            "WHERE status = 'active'"
        )
        for row in rows:
            cikis_url = f"{SITE_URL}/bulten/cikis?token={row['unsubscribe_token']}"
            try:
                ok = await send_new_post_email(
                    to=row["email"],
                    title=title,
                    excerpt=excerpt,
                    url=url,
                    unsubscribe_url=cikis_url,
                )
            except Exception:
                log.exception("Bülten e-postası gönderim hatası: %s", row["email"])
                ok = False

            if ok:
                gonderilen += 1
                await conn.execute(
                    "UPDATE newsletter_subscribers SET last_sent_at = NOW() WHERE id = $1",
                    row["id"],
                )
            else:
                basarisiz += 1
                log.warning("Bülten e-postası gönderilemedi: %s", row["email"])

            await asyncio.sleep(_GONDERIM_ARASI_BEKLEME_SN)

    log.info(
        "Bülten bildirimi tamamlandı: slug=%s gonderilen=%d basarisiz=%d",
        slug, gonderilen, basarisiz,
    )
    return {"gonderilen": gonderilen, "basarisiz": basarisiz}
