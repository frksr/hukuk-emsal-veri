"""Welcome e-mail serisi — kayıt sonrası 7 gün boyunca otomatik gönderim.

Cron veya scheduled task ile çalıştırılır:
  python -m services.welcome_series

Veya FastAPI background task olarak.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta, timezone
import os

from services.email import send_email, _wrap

log = logging.getLogger("services.welcome_series")
SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukcuyapayzekasi.com")


TEMPLATES = {
    "welcome_day_0": {
        "subject": "🎉 Hukuk Emsal'e hoş geldiniz",
        "delay_hours": 0,
        "body": lambda name: (
            f"<p>Merhaba {name or ''},</p>"
            "<p>Hukuk Emsal ailesine hoş geldiniz! Hesabınız aktif, hemen başlayabilirsiniz.</p>"
            "<p><strong>İlk 3 adım:</strong></p>"
            "<ol style='padding-left:20px;line-height:1.8;'>"
            "<li>İlk emsal aramanızı yapın (icra, tahsilat, ihtar konularında)</li>"
            "<li>Faiz hesaplayıcı ile bir alacak hesabı çıkarın</li>"
            "<li>Pro+UYAP planını inceleyin — kendi dosyalarınızda AI sorgu</li>"
            "</ol>"
        ),
        "cta": ("/emsal-arama", "İlk Aramayı Yap"),
    },
    "welcome_day_1": {
        "subject": "💡 Bilmediğiniz 5 özellik",
        "delay_hours": 24,
        "body": lambda name: (
            f"<p>Merhaba {name or ''},</p>"
            "<p>Bugün size ünlü özellikleri tanıtalım:</p>"
            "<ul style='padding-left:20px;line-height:1.8;'>"
            "<li><strong>Karşı Argüman Öngörüsü</strong> — davadan önce karşı tarafın diyebileceklerini gör</li>"
            "<li><strong>Belge Denetleyici</strong> — yazdığın dilekçenin hukuki risklerini AI kontrol etsin</li>"
            "<li><strong>Karar Trend Paneli</strong> — Yargıtay'ın konu bazlı tutumu nasıl değişti?</li>"
            "<li><strong>İhtarname Üretici</strong> — TBK 117, İİK 51 noter onayına hazır taslak</li>"
            "<li><strong>KVKK Uyum Listesi</strong> — sektörünüze özel 30+ maddelik checklist</li>"
            "</ul>"
        ),
        "cta": (f"{SITE_URL}", "Tüm Özellikleri Gör"),
    },
    "welcome_day_3": {
        "subject": "🚀 UYAP dosyalarınızla AI — Pro deneme",
        "delay_hours": 72,
        "body": lambda name: (
            f"<p>Merhaba {name or ''},</p>"
            "<p>Eğer UYAP'tan gelen dosyalarınızla AI sorgu yapmak istersen, "
            "<strong>Pro + UYAP</strong> planı senin için.</p>"
            "<p>Bu özellik ile:</p>"
            "<ul style='padding-left:20px;line-height:1.8;'>"
            "<li>UYAP dosyalarınızı şifreli yükleyin</li>"
            "<li>Kendi davalarınızda AI sorgu (Yargıtay emsalleri ile birlikte)</li>"
            "<li>Müvekkil bilgileri otomatik maskelenir (KVKK uyum)</li>"
            "<li>Tüm veriler Türkiye lokasyonunda, sadece size özel</li>"
            "</ul>"
            "<p>Aylık ₺799. İstediğiniz an iptal edebilirsiniz; iptalde hizmet dönem "
            "sonuna kadar açık kalır. Para iadesi yapılmaz.</p>"
        ),
        "cta": ("/panel/ayarlar/abonelik", "Pro + UYAP'ı İncele"),
    },
    "welcome_day_7": {
        "subject": "📊 Bir haftadır bizimle — geri bildiriminizi alalım?",
        "delay_hours": 168,
        "body": lambda name: (
            f"<p>Merhaba {name or ''},</p>"
            "<p>Bir haftadır Hukuk Emsal'i deneyimliyorsunuz. Sizden öğrenmek istiyoruz:</p>"
            "<ul style='padding-left:20px;line-height:1.8;'>"
            "<li>Hangi özellik en çok işinize yaradı?</li>"
            "<li>Hangi özelliği yetersiz buldunuz?</li>"
            "<li>Eklenmesini istediğiniz özellik var mı?</li>"
            "</ul>"
            "<p>Her sayfanın sağ alt köşesindeki 💬 widget'ten anında bildirebilirsiniz.</p>"
            "<p>Geri bildiriminiz ürünün şekillenmesinde gerçek etki yapar.</p>"
        ),
        "cta": (f"{SITE_URL}/app", "Dashboard'a Dön"),
    },
}


async def schedule_welcome_emails(user_id: str, email: str, name: str | None):
    """Yeni kayıt için welcome serisini DB'ye scheduled olarak yaz."""
    from api.db import service_session
    now = datetime.now(timezone.utc)
    async with service_session() as conn:
        for key, tpl in TEMPLATES.items():
            scheduled_for = now + timedelta(hours=tpl["delay_hours"])
            try:
                await conn.execute(
                    """INSERT INTO scheduled_emails
                       (user_id, email_type, scheduled_for)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (user_id, email_type) DO NOTHING""",
                    user_id, key, scheduled_for,
                )
            except Exception as e:
                log.warning(f"Welcome schedule hatası: {e}")


async def process_pending_emails(limit: int = 50):
    """Vade gelen pending email'leri gönder. Cron ile çağırılır."""
    from api.db import service_session
    now = datetime.now(timezone.utc)
    async with service_session() as conn:
        rows = await conn.fetch(
            """SELECT se.id, se.user_id, se.email_type, u.email, u.name,
                      u.marketing_consent
               FROM scheduled_emails se
               JOIN users u ON u.id = se.user_id
               WHERE se.status = 'pending'
                 AND se.scheduled_for <= $1
                 AND u.is_active = TRUE
               LIMIT $2""",
            now, limit,
        )

        for r in rows:
            tpl = TEMPLATES.get(r["email_type"])
            if not tpl:
                await conn.execute(
                    "UPDATE scheduled_emails SET status = 'skipped' WHERE id = $1",
                    r["id"],
                )
                continue

            # marketing_consent false ise sadece welcome_day_0'ı gönder
            if not r["marketing_consent"] and r["email_type"] != "welcome_day_0":
                await conn.execute(
                    "UPDATE scheduled_emails SET status = 'skipped' WHERE id = $1",
                    r["id"],
                )
                continue

            try:
                ok = await send_email(
                    to=r["email"],
                    subject=tpl["subject"],
                    html=_wrap(
                        tpl["subject"].split(" ", 1)[1] if " " in tpl["subject"] else tpl["subject"],
                        tpl["body"](r["name"]),
                        (f"{SITE_URL}{tpl['cta'][0]}" if not tpl['cta'][0].startswith('http') else tpl['cta'][0],
                         tpl["cta"][1]),
                    ),
                )
                if ok:
                    await conn.execute(
                        """UPDATE scheduled_emails SET status = 'sent', sent_at = NOW()
                           WHERE id = $1""",
                        r["id"],
                    )
                else:
                    await conn.execute(
                        """UPDATE scheduled_emails SET status = 'failed',
                           error_message = 'send returned false' WHERE id = $1""",
                        r["id"],
                    )
            except Exception as e:
                log.exception(f"Email gönderme hatası: {r['email_type']}")
                await conn.execute(
                    """UPDATE scheduled_emails SET status = 'failed',
                       error_message = $2 WHERE id = $1""",
                    r["id"], str(e)[:500],
                )


if __name__ == "__main__":
    asyncio.run(process_pending_emails())
