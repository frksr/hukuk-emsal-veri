"""api/net.py — X-Forwarded-For güvenilir proxy çözümü.

Bu testler bir güvenlik regresyonunu kilitler: eskiden XFF'in İLK değeri
okunuyordu, yani istemci header'ı uydurarak IP bazlı anonim kotayı (api/kota.py)
sınırsız kez sıfırlayabiliyor ve audit_log.ip_address'i sahteleyebiliyordu.
"""
from __future__ import annotations

import importlib

import pytest


def _request(xff: str | None = None, peer: str | None = "10.0.0.5"):
    """Minimal sahte Request — api.net yalnızca headers ve client okuyor."""
    from starlette.requests import Request

    headers = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (peer, 12345) if peer else None,
    }
    return Request(scope)


def _net(monkeypatch, hops: int):
    """api.net'i verilen TRUSTED_PROXY_HOPS ile yeniden yükle."""
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", str(hops))
    import api.net

    return importlib.reload(api.net)


def test_tek_proxy_zincirin_sagindan_okur(monkeypatch):
    """Saldırgan XFF'e sahte IP eklese bile LB'nin yazdığı gerçek IP alınır."""
    net = _net(monkeypatch, 1)
    # Saldırgan "1.2.3.4" gönderdi; LB gerçek istemciyi (203.0.113.9) sona ekledi.
    req = _request("1.2.3.4, 203.0.113.9")
    assert net.client_ip(req) == "203.0.113.9"


def test_iki_proxy_katmani(monkeypatch):
    """CDN + LB varsa gerçek istemci sağdan ikinci sıradadır."""
    net = _net(monkeypatch, 2)
    req = _request("198.51.100.7, 203.0.113.9")
    assert net.client_ip(req) == "198.51.100.7"


def test_hops_sifirsa_xff_tamamen_yoksayilir(monkeypatch):
    """Uygulama doğrudan internete açıksa XFF'e hiç güvenilmez."""
    net = _net(monkeypatch, 0)
    req = _request("1.2.3.4, 5.6.7.8", peer="203.0.113.9")
    assert net.client_ip(req) == "203.0.113.9"


def test_zincir_beklenenden_kisaysa_peer_adresine_duser(monkeypatch):
    """Header kırpılmışsa istemcinin uydurduğu sol tarafa DÜŞÜLMEZ."""
    net = _net(monkeypatch, 2)
    req = _request("1.2.3.4", peer="203.0.113.9")  # zincirde 1 var, 2 bekleniyor
    assert net.client_ip(req) == "203.0.113.9"


def test_gecersiz_ip_degeri_peer_adresine_duser(monkeypatch):
    net = _net(monkeypatch, 1)
    req = _request("not-an-ip", peer="203.0.113.9")
    assert net.client_ip(req) == "203.0.113.9"


def test_xff_yoksa_peer_adresi(monkeypatch):
    net = _net(monkeypatch, 1)
    assert net.client_ip(_request(None, peer="203.0.113.9")) == "203.0.113.9"


def test_client_yoksa_unknown(monkeypatch):
    net = _net(monkeypatch, 1)
    assert net.client_ip(_request(None, peer=None)) == net.UNKNOWN_IP


def test_ipv6_desteklenir(monkeypatch):
    net = _net(monkeypatch, 1)
    req = _request("1.2.3.4, 2001:db8::1")
    assert net.client_ip(req) == "2001:db8::1"


def test_port_ekli_deger_temizlenir(monkeypatch):
    net = _net(monkeypatch, 1)
    req = _request("203.0.113.9:51234")
    assert net.client_ip(req) == "203.0.113.9"


@pytest.mark.parametrize("ua,beklenen_uzunluk", [("x" * 900, 500), ("Mozilla", 7)])
def test_user_agent_kirpilir(monkeypatch, ua, beklenen_uzunluk):
    net = _net(monkeypatch, 1)
    from starlette.requests import Request

    req = Request({
        "type": "http", "method": "GET", "path": "/",
        "headers": [(b"user-agent", ua.encode())], "client": ("10.0.0.1", 1),
    })
    assert len(net.user_agent(req)) == beklenen_uzunluk
