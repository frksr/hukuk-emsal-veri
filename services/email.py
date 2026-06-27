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
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@hukukcuyapayzekasi.com")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Hukuk Emsal")
# STARTTLS: açıkça set edilebilir; aksi halde port 587 ise True, (mailpit/yerel
# 1025/1026/25 gibi) diğer portlarda False (düz SMTP). Mailpit STARTTLS istemez.
SMTP_STARTTLS = os.environ.get("SMTP_STARTTLS", "").strip().lower()
SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukcuyapayzekasi.com")


def is_configured() -> bool:
    # Host yeterli — kimlik (USER/PASS) opsiyonel: mailpit gibi sunucular auth istemez.
    return bool(SMTP_HOST)


def _use_starttls() -> bool:
    if SMTP_STARTTLS in ("1", "true", "yes", "on"):
        return True
    if SMTP_STARTTLS in ("0", "false", "no", "off"):
        return False
    return SMTP_PORT == 587  # otomatik: 587 → STARTTLS, diğerleri (yerel/mailpit) düz


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

    gonderim: dict = {
        "hostname": SMTP_HOST,
        "port": SMTP_PORT,
        "use_tls": False,
        "start_tls": _use_starttls(),
        "timeout": 15,
    }
    # Kimlik yalnızca tanımlıysa gönderilir (mailpit gibi auth'suz sunucular için).
    if SMTP_USER and SMTP_PASS:
        gonderim["username"] = SMTP_USER
        gonderim["password"] = SMTP_PASS

    try:
        await aiosmtplib.send(msg, **gonderim)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] to={to} host={SMTP_HOST}:{SMTP_PORT} starttls={gonderim['start_tls']} -> {e}")
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
      İletişim: <a href="mailto:info@hukukcuyapayzekasi.com" style="color:#1e3a5f;">info@hukukcuyapayzekasi.com</a>
    </p>
  </div>
</body></html>"""


async def send_verification_email(
    to: str,
    name: Optional[str],
    code: str,
    token: Optional[str] = None,
    expires_minutes: int = 10,
) -> bool:
    """E-posta doğrulama — 6 haneli KOD (birincil) + tek-tık LİNK (yedek).

    Kod cihazdan bağımsız çalışır (masaüstünde kayıt olup telefonda mailı açan
    kullanıcı için sorunsuz) ve kurumsal e-posta tarayıcılarının linki önceden
    tıklayıp tüketmesinden etkilenmez. Link ise aynı cihazda tek tıkla doğrular.
    """
    greeting = f"Merhaba {name}," if name else "Merhaba,"
    kod_kutu = (
        "<div style='margin:24px 0;text-align:center;'>"
        "<div style='display:inline-block;font-size:34px;font-weight:700;"
        "letter-spacing:10px;padding:14px 26px;border-radius:12px;"
        "background:#f1f5f9;color:#0f172a;font-family:monospace;'>"
        f"{code}</div></div>"
    )
    body = (
        f"<p>{greeting}</p>"
        "<p>Hukuk Emsal hesabınızı doğrulamak için aşağıdaki <strong>6 haneli kodu</strong> "
        "siteye girin:</p>"
        f"{kod_kutu}"
        f"<p style='color:#666;font-size:13px;'>Kod <strong>{expires_minutes} dakika</strong> "
        "geçerlidir. Bu işlemi siz yapmadıysanız bu e-postayı yok sayabilirsiniz.</p>"
    )
    cta = None
    text = f"{greeting}\n\nDoğrulama kodunuz: {code}\n({expires_minutes} dakika geçerli)\n"
    if token:
        url = f"{SITE_URL}/giris/dogrulama?token={token}"
        body += (
            "<p style='color:#666;font-size:13px;'>Dilerseniz tek tıkla da "
            "doğrulayabilirsiniz:</p>"
        )
        cta = (url, "Tek Tıkla Doğrula")
        text += f"\nVeya tek tıkla: {url}\n"
    return await send_email(
        to=to,
        subject=f"Doğrulama kodunuz: {code} — Hukuk Emsal",
        html=_wrap("E-posta Doğrulama", body, cta),
        text=text,
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


_PLAN_ETIKET = {
    "pro_solo": "Pro Solo",
    "pro_solo_uyap": "Pro + UYAP",
    "team": "Team",
    "team_uyap": "Team + UYAP",
    "enterprise": "Enterprise",
}


async def send_payment_failed_email(
    to: str,
    name: Optional[str],
    plan_tier: str,
    amount_try: float = 0.0,
) -> bool:
    """Abonelik yenileme ödemesi alınamadığında gönderilir.

    Ödeme alınamadığı için ücretli özellikler askıya alınır; kullanıcı kartını
    güncelleyip yeniden deneyebilir.
    """
    greeting = f"Merhaba {name}," if name else "Merhaba,"
    plan_ad = _PLAN_ETIKET.get(plan_tier, plan_tier)
    tutar = f"{amount_try:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".") if amount_try else ""
    body = (
        f"<p>{greeting}</p>"
        f"<p><strong>{plan_ad}</strong> aboneliğinizin yenileme ödemesi "
        f"{('(' + tutar + ') ') if tutar else ''}alınamadı.</p>"
        "<p>Bu nedenle hesabınızdaki ücretli özellikler geçici olarak askıya alındı. "
        "Erişiminizi geri açmak için ödeme yönteminizi güncelleyip yenilemeyi "
        "tekrar deneyebilirsiniz.</p>"
        "<p style='color:#64748b;font-size:13px;'>Ödeme başarıyla alındığında "
        "paketiniz ve tüm hakları otomatik olarak geri yüklenir.</p>"
    )
    return await send_email(
        to=to,
        subject="Ödeme alınamadı — aboneliğiniz askıya alındı",
        html=_wrap(
            "Ödeme alınamadı",
            body,
            (f"{SITE_URL}/panel/ayarlar/abonelik", "Ödemeyi Güncelle"),
        ),
    )


async def send_emsal_alarm_email(
    to: str,
    name: Optional[str],
    query: str,
    yeni_kararlar: list[dict],
) -> bool:
    """Emsal alarmı — takip edilen sorguya yeni karar düştüğünde gönderilir."""
    site = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukcuyapayzekasi.com")
    satirlar = []
    for k in yeni_kararlar[:5]:
        baslik = k.get("baslik") or k.get("chunk_id") or "Yeni karar"
        ozet = (k.get("ozet") or "")[:200]
        satirlar.append(f"<li><strong>{baslik}</strong><br/><small>{ozet}…</small></li>")
    body = (
        f"<p>Merhaba {name or ''},</p>"
        f"<p>Takip ettiğiniz <strong>“{query}”</strong> sorgusuyla eşleşen "
        f"{len(yeni_kararlar)} yeni emsal karar bulundu:</p>"
        f"<ul>{''.join(satirlar)}</ul>"
    )
    html = _wrap(
        "Takip ettiğiniz konuda yeni emsal var",
        body,
        cta=(f"{site}/emsal-arama?q=" + query.replace(" ", "+"), "Kararları İncele"),
    )
    return await send_email(
        to=to,
        subject=f"Yeni emsal: {query[:60]}",
        html=html,
    )
