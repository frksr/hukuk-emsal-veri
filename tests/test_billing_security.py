"""Billing güvenlik testleri — webhook imza doğrulama, durum eşleme, fatura doğrulama."""
import asyncio
import hashlib
import hmac

from services import billing


def test_signature_none_when_not_configured(monkeypatch):
    monkeypatch.setattr(billing, "IYZICO_WEBHOOK_SECRET", "")
    assert billing.verify_webhook_signature(b"{}", {}) is None


def test_signature_valid(monkeypatch):
    secret = "super-secret"
    monkeypatch.setattr(billing, "IYZICO_WEBHOOK_SECRET", secret)
    body = b'{"event":"x"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert billing.verify_webhook_signature(body, {"X-IYZ-SIGNATURE-V3": sig}) is True


def test_signature_invalid(monkeypatch):
    monkeypatch.setattr(billing, "IYZICO_WEBHOOK_SECRET", "secret")
    body = b'{"event":"x"}'
    assert billing.verify_webhook_signature(body, {"X-IYZ-SIGNATURE-V3": "deadbeef"}) is False


def test_signature_missing_header_rejected(monkeypatch):
    monkeypatch.setattr(billing, "IYZICO_WEBHOOK_SECRET", "secret")
    assert billing.verify_webhook_signature(b"{}", {}) is False


def test_status_map_covers_iyzico_states():
    m = billing._IYZICO_STATUS_MAP
    assert m["ACTIVE"] == "active"
    assert m["CANCELED"] == "canceled"
    assert m["UNPAID"] == "failed"
    assert m["EXPIRED"] == "expired"


def test_authoritative_dev_mode_active():
    """iyzico yapılandırılmamışken (dev) re-query 'active' döndürür."""
    res = asyncio.run(billing.get_authoritative_subscription("any-ref"))
    assert res["found"] is True
    assert res["status"] == "active"
    assert res.get("dev_mode") is True


def test_tckn_validator():
    from api.routers.billing import _valid_tckn
    assert _valid_tckn("10000000146") is True   # geçerli checksum
    assert _valid_tckn("11111111111") is False  # sahte default — reddedilmeli
    assert _valid_tckn("123") is False
    assert _valid_tckn(None) is False
    assert _valid_tckn("01234567890") is False  # ilk hane 0


def test_phone_normalizer():
    from api.routers.billing import _normalize_phone
    assert _normalize_phone("0555 123 45 67") == "+905551234567"
    assert _normalize_phone("+90 555 123 45 67") == "+905551234567"
    assert _normalize_phone("5551234567") == "+905551234567"
    assert _normalize_phone("12345") is None
    assert _normalize_phone(None) is None
