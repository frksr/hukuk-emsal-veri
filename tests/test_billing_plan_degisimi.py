"""api/routers/billing.py — çift abonelik / plan değişimi koruması.

KİLİTLENEN AÇIK: `checkout()` mevcut aktif aboneliği hiç sorgulamıyordu.
Pro Solo'dayken Team'e geçen kullanıcı için iyzico'da İKİNCİ bir abonelik
açılıyor, birincisi iptal edilmediği için ertesi ay İKİ KEZ tahsilat
yapılabiliyordu.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BILLING = (ROOT / "api" / "routers" / "billing.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# checkout() mevcut aboneliği kontrol ediyor mu?
# ---------------------------------------------------------------------------

def _checkout_govdesi() -> str:
    m = re.search(r"async def checkout\(.*?(?=\n@router)", BILLING, re.DOTALL)
    assert m, "checkout() bulunamadı"
    return m.group(0)


def test_checkout_mevcut_aktif_abonelik_sorguluyor():
    govde = _checkout_govdesi()
    assert "status = 'active'" in govde and "FROM subscriptions" in govde, \
        "checkout() mevcut aboneliği sorgulamıyor — çift abonelik açılabilir."


def test_ayni_plana_ikinci_kez_abone_olunamaz():
    govde = _checkout_govdesi()
    assert "zaten_abone" in govde, \
        "Aynı plana ikinci checkout engellenmiyor."


def test_plan_degisimi_yeni_abonelige_isaretleniyor():
    """Aktivasyon anında eskisini kapatabilmek için iz bırakılmalı."""
    govde = _checkout_govdesi()
    assert "supersedes" in govde, \
        "Plan değişiminde önceki abonelik id'si metadata'ya yazılmıyor."


# ---------------------------------------------------------------------------
# Aktivasyon eskiyi kapatıyor mu?
# ---------------------------------------------------------------------------

def test_devir_fonksiyonu_var_ve_iyzicoda_iptal_ediyor():
    m = re.search(r"async def _onceki_abonelikleri_devret\(.*?(?=\nasync def |\ndef )",
                  BILLING, re.DOTALL)
    assert m, "_onceki_abonelikleri_devret() yok"
    govde = m.group(0)
    assert "cancel_subscription(" in govde, "iyzico'da iptal çağrısı yok"
    assert "status = 'canceled'" in govde, "lokal kayıt kapatılmıyor"
    assert "superseded_by" in govde, "hangi abonelikle değiştiği izlenmiyor"


def test_callback_aktivasyonda_devir_cagriliyor():
    m = re.search(r"async def callback\(.*?(?=\n@router)", BILLING, re.DOTALL)
    assert m, "callback() bulunamadı"
    assert "_onceki_abonelikleri_devret" in m.group(0), \
        "Yeni abonelik aktifleşirken eskisi kapatılmıyor — çift tahsilat riski."


def test_devir_yeni_abonelik_aktiflestikten_SONRA_calisiyor():
    """Sıralama kritik: önce iptal edilseydi, yeni ödeme başarısız olduğunda
    kullanıcı hiç plansız kalırdı."""
    m = re.search(r"async def callback\(.*?(?=\n@router)", BILLING, re.DOTALL)
    govde = m.group(0)
    aktif_idx = govde.find("status = 'active'")
    devir_idx = govde.find("_onceki_abonelikleri_devret")
    assert aktif_idx != -1 and devir_idx != -1
    assert aktif_idx < devir_idx, "Eski abonelik, yenisi aktifleşmeden kapatılıyor."


def test_iyzico_iptali_basarisizsa_yuksek_seviyede_loglanir():
    """Sessizce yutulursa çift tahsilat fark edilmez."""
    m = re.search(r"async def _onceki_abonelikleri_devret\(.*?(?=\nasync def |\ndef )",
                  BILLING, re.DOTALL)
    assert "log.error" in m.group(0), \
        "iyzico iptal hatası log.error ile bildirilmiyor."


# ---------------------------------------------------------------------------
# Webhook idempotency
# ---------------------------------------------------------------------------

def test_webhook_token_yoksa_govde_hashine_dusuyor():
    """`iyzico_token` NULL geldiğinde SQL'de NULL = NULL asla TRUE olmadığından
    tekilleştirme sessizce devre dışı kalıyor, aynı olay tekrar işlenebiliyordu."""
    m = re.search(r"async def webhook\(.*?(?=\n@router|\Z)", BILLING, re.DOTALL)
    assert m, "webhook() bulunamadı"
    govde = m.group(0)
    assert "sha256" in govde and "if not iyzico_token" in govde, \
        "Token yokken alternatif idempotency anahtarı üretilmiyor."


def test_webhook_istemci_ip_guvenilir_proxy_ile_cozuluyor():
    m = re.search(r"async def webhook\(.*?(?=\n@router|\Z)", BILLING, re.DOTALL)
    assert "client_ip(request)" in m.group(0), \
        "webhook source_ip'i request.client.host'tan alıyor (proxy arkasında yanlış)."


# ---------------------------------------------------------------------------
# TCKN doğrulaması
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tckn,gecerli", [
    ("10000000146", True),    # geçerli checksum
    ("11111111111", False),   # sahte varsayılan — 2. kural geçer, 3. geçmez
    ("12345678901", False),
    ("00000000000", False),   # ilk hane 0
    ("1234567890", False),    # 10 hane
    ("123456789012", False),  # 12 hane
    ("1234567890a", False),   # rakam değil
    ("", False),
    (None, False),
])
def test_tckn_checksum(monkeypatch, tckn, gecerli):
    monkeypatch.setenv("IYZICO_BASE_URL", "https://api.iyzipay.com")  # prod modu
    from api.routers.billing import _valid_tckn

    assert _valid_tckn(tckn) is gecerli


def test_iyzico_ornek_tckni_yalnizca_sandboxta_kabul(monkeypatch):
    from api.routers.billing import _valid_tckn

    monkeypatch.setenv("IYZICO_BASE_URL", "https://sandbox-api.iyzipay.com")
    assert _valid_tckn("74300864791") is True

    monkeypatch.setenv("IYZICO_BASE_URL", "https://api.iyzipay.com")
    assert _valid_tckn("74300864791") is False
