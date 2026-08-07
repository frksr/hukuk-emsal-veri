"""İstemci IP çözümü — güvenilir proxy (X-Forwarded-For) doğrulamasıyla.

NEDEN BU MODÜL VAR
------------------
`X-Forwarded-For` header'ı istemci tarafından serbestçe uydurulabilir. Header'ın
İLK değerine güvenmek (eski davranış) iki açığa yol açıyordu:

  1. Kota atlatma — anonim kullanıcı her istekte farklı bir XFF göndererek
     IP başına günlük limiti (api/kota.py) sınırsız kez aşabiliyordu.
  2. Audit log sahteciliği — `audit_log.ip_address` KVKK/adli inceleme için
     tutulur; sahte doldurulabildiğinde delil değeri kalmıyordu.

DOĞRU YAKLAŞIM (rightmost-N)
----------------------------
XFF zincirinde her proxy, isteği ALDIĞI peer'ın adresini sona ekler. Yani
zincirin SAĞ tarafı bizim kontrolümüzdeki altyapı tarafından yazılır, SOL
tarafı istemci tarafından uydurulabilir.

    İstemci "1.2.3.4"  →  LB (client=203.0.113.9 ekler)  →  uygulama
    Uygulamanın gördüğü XFF: "1.2.3.4, 203.0.113.9"  ← soldaki sahte!

Bu yüzden soldan değil, SAĞDAN `TRUSTED_PROXY_HOPS` kadar sayarak okuruz.

  TRUSTED_PROXY_HOPS = 0  →  XFF'e hiç güvenme, TCP peer adresini kullan
                             (uygulama doğrudan internete açıksa bunu seç)
  TRUSTED_PROXY_HOPS = 1  →  önümüzde tek bir güvenilir proxy var
                             (Cloud Run / Railway / tek LB — VARSAYILAN)
  TRUSTED_PROXY_HOPS = 2  →  CDN + LB gibi iki katman var
                             (ör. Cloudflare → GCLB → Cloud Run)

Yanlış yapılandırma sessizce güvensiz hale gelmesin diye, zincir beklenenden
kısaysa en soldaki değere DEĞİL, TCP peer adresine düşeriz.
"""
from __future__ import annotations

import ipaddress
import logging
import os

from fastapi import Request

log = logging.getLogger("api.net")

#: Uygulamanın önündeki güvenilir proxy sayısı. Deploy topolojisine göre ayarlanır.
TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "1"))

#: IP çözülemediğinde kullanılan sabit. Kota/audit tarafında "bilinmiyor" demek.
UNKNOWN_IP = "0.0.0.0"


def _valid_ip(value: str) -> str | None:
    """Geçerli bir IPv4/IPv6 adresiyse normalize edip döndür, değilse None."""
    value = value.strip()
    if not value:
        return None
    # "203.0.113.9:51234" gibi port ekli formlar (bazı proxy'ler yazar)
    if value.count(":") == 1 and "." in value:
        value = value.split(":", 1)[0]
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def _peer_ip(request: Request) -> str:
    """TCP peer adresi — uydurulamaz, ama proxy arkasındaysak LB'nin adresidir."""
    if request.client and request.client.host:
        return _valid_ip(request.client.host) or UNKNOWN_IP
    return UNKNOWN_IP


def client_ip(request: Request) -> str:
    """İstemcinin gerçek IP'si.

    `TRUSTED_PROXY_HOPS` kadar sağdan sayarak XFF zincirinden okur; zincir
    beklenenden kısaysa veya değer geçerli bir IP değilse TCP peer adresine
    düşer (asla istemcinin uydurabileceği sol tarafa güvenmez).
    """
    if TRUSTED_PROXY_HOPS <= 0:
        return _peer_ip(request)

    fwd = request.headers.get("x-forwarded-for")
    if not fwd:
        # Proxy bekliyorduk ama XFF yok — doğrudan erişim veya health probe.
        return _peer_ip(request)

    parts = [p for p in (s.strip() for s in fwd.split(",")) if p]
    if len(parts) < TRUSTED_PROXY_HOPS:
        # Zincir beklenenden kısa: ya yapılandırma yanlış ya da birisi header'ı
        # kırpmaya çalışıyor. Güvenli tarafta kal.
        log.debug(
            "XFF zinciri beklenenden kısa (%d < %d) — peer adresine düşülüyor",
            len(parts), TRUSTED_PROXY_HOPS,
        )
        return _peer_ip(request)

    candidate = _valid_ip(parts[-TRUSTED_PROXY_HOPS])
    return candidate or _peer_ip(request)


def user_agent(request: Request, max_len: int = 500) -> str:
    """User-Agent header'ı — log/audit için kırpılmış hali."""
    return (request.headers.get("user-agent") or "")[:max_len]
