"""Transactional email — SMTP tabanlı, async.

Production'da: Resend / Postmark / SendGrid önerilir.
Development: Gmail SMTP veya Mailtrap.
"""
from __future__ import annotations
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

import aiosmtplib

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@hukukemsal.tr")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Hukuk Emsal")
SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukemsal.tr")


def is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


async def send_email(
    to: str,
    subject: str,
    html: str,
    text: Optional[str] = None,
) -> bool:
    if not is_configured():
        # Development: konsola yaz, gönderme
        print(f"\n[EMAIL DEV MODE]\nTo: {to}\nSubject: {subject}\n{text or html}\n")
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM))
    msg["To"] = to
    msg["Reply-To"] = SMTP_FROM

    if text:
        msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASS,
            use_tls=False,
            start_tls=True,
            timeout=15,
        )
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


# ----- Templates -----

def _wrap(title: str, body: str, cta: tuple[str, str] | None = None) -> str:
    cta_html = ""
    if cta:
        url, label = cta
        cta_html = (
            f'<p style="margin:32px 0;text-align:center;">'
            f'<a href="{url}" style="display:inline-block;padding:14px 28px;'
            f'background:#1e3a5f;color:#fff;text-decoration:none;border-radius:6px;'
            f'font-weight:600;">{label}</a></p>'
        )

    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,Segoe UI,Inter,Arial,sans-serif;background:#f5f5f7;margin:0;padding:24px;">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;padding:32px;">
    <div style="text-align:center;margin-bottom:24px;">
      <div style="font-size:24px;font-weight:700;color:#1e3a5f;">⚖️ Hukuk Emsal</div>
    </div>
    <h1 style="font-size:20px;color:#1e3a5f;margin:0 0 16px;">{title}</h1>
    <div style="color:#444;line-height:1.6;font-size:15px;">{body}</div>
    {cta_html}
    <hr style="border:none;border-top:1px solid #eee;margin:32px 0 16px;">
    <p style="color:#888;font-size:12px;text-align:center;margin:0;">
      Bu e-posta {SITE_URL} sistemi tarafından otomatik gönderildi.<br>
      İletişim: <a href="mailto:info@hukukemsal.tr" style="color:#1e3a5f;">info@hukukemsal.tr</a>
    </p>
  </div>
</body></html>"""


async def send_verification_email(to: str, name: Optional[str], token: str) -> bool:
    url = f"{SITE_URL}/giris/dogrulama?token={token}"
    greeting = f"Merhaba {name}," if name else "Merhaba,"
    body = (
        f"<p>{greeting}</p>"
        "<p>Hukuk Emsal'e kayıt olduğunuz için teşekkürler. "
        "Hesabınızı doğrulamak için aşağıdaki butona tıklayın:</p>"
        "<p style='color:#666;font-size:13px;'>"
        "Bu bağlantı 24 saat geçerlidir. Eğer kayıt işlemini siz yapmadıysanız "
        "bu e-postayı yok sayabilirsiniz.</p>"
    )
    return await send_email(
        to=to,
        subject="Hesabınızı doğrulayın — Hukuk Emsal",
        html=_wrap("E-posta Doğrulama", body, (url, "Hesabımı Doğrula")),
        text=f"{greeting}\n\nHesabınızı doğrulamak için: {url}\n\n24 saat içinde yapın.",
    )


async def send_password_reset_email(to: str, name: Optional[str], token: str) -> bool:
    url = f"{SITE_URL}/sifre-sifirla?token={token}"
    greeting = f"Merhaba {name}," if name else "Merhaba,"
    body = (
        f"<p>{greeting}</p>"
        "<p>Hesabınız için şifre sıfırlama talebinde bulunuldu. "
        "Yeni şifre belirlemek için aşağıdaki butona tıklayın:</p>"
        "<p style='color:#666;font-size:13px;'>"
        "Bu bağlantı <strong>1 saat</strong> geçerlidir. Şifre sıfırlama talebini "
        "siz yapmadıysanız, bu e-postayı yok sayın — şifreniz değişmedi.</p>"
    )
    return await send_email(
        to=to,
        subject="Şifre Sıfırlama — Hukuk Emsal",
        html=_wrap("Şifre Sıfırlama", body, (url, "Yeni Şifre Belirle")),
        text=f"{greeting}\n\nŞifre sıfırlama bağlantısı: {url}\n\n1 saat içinde geçerli.",
    )


async def send_welcome_email(to: str, name: Optional[str]) -> bool:
    greeting = f"Merhaba {name}," if name else "Merhaba,"
    body = (
        f"<p>{greeting}</p>"
        "<p>Hukuk Emsal ailesine hoş geldiniz! Hesabınız aktif. Artık şu özellikleri kullanabilirsiniz:</p>"
        "<ul style='padding-left:20px;line-height:1.8;'>"
        "<li><strong>40 emsal arama/gün</strong> — 10.000+ Yargıtay, Danıştay, AİHM kararı</li>"
        "<li><strong>6 AI dilekçe/gün</strong> — emsallere atıflı taslak</li>"
        "<li><strong>Sınırsız hesaplayıcı</strong> — faiz, zamanaşımı, ihtarname</li>"
        "<li><strong>Geçmiş kayıt</strong> — aramalarınızı tekrar görebilirsiniz</li>"
        "</ul>"
        "<p>UYAP entegrasyonu, kendi dosyalarınızda AI sorgu gibi daha fazlası için "
        "Pro plana yükselebilirsiniz.</p>"
    )
    return await send_email(
        to=to,
        subject="Hoş geldin — Hukuk Emsal hesabınız aktif",
        html=_wrap("Hoş geldiniz! 🎉", body, (f"{SITE_URL}/app", "Dashboard'a Git")),
    )
