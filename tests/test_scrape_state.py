"""common/scrape_state.py — artımlı tazeleme imleci.

KAPATILAN BOŞLUK
----------------
Scraper'lar her koşuda aynı aramaları BAŞTAN yapıyordu. İndirilmiş kararlar
JobQueue ile atlanıyordu ama kaynak siteler sonuçları alaka düzeyine göre
sıraladığından YENİ kararlar listenin başında çıkmayabiliyor, düzenli koşuda
gözden kaçabiliyordu. Artık "en son görülen karar tarihi" kalıcı tutuluyor.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from common import scrape_state as S


@pytest.fixture
def kok():
    with tempfile.TemporaryDirectory() as t:
        yield Path(t)


# ---------------------------------------------------------------------------
# Tarih normalizasyonu — kaynaklar farklı biçimler döndürüyor
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("girdi,beklenen", [
    ("2024-03-15", "2024-03-15"),
    ("15.03.2024", "2024-03-15"),
    ("15/03/2024", "2024-03-15"),
    ("2024-03-15T10:22:00", "2024-03-15"),
    ("2024-03-15 10:22", "2024-03-15"),
    ("", None),
    (None, None),
    ("bozuk", None),
    ("32.13.2024", None),      # geçersiz gün/ay
])
def test_tarih_normalize(girdi, beklenen):
    assert S.tarih_normalize(girdi) == beklenen


def test_tarih_normalize_date_nesnesi():
    from datetime import date, datetime
    assert S.tarih_normalize(date(2024, 3, 15)) == "2024-03-15"
    assert S.tarih_normalize(datetime(2024, 3, 15, 10, 0)) == "2024-03-15"


# ---------------------------------------------------------------------------
# yeni_mi — süzme kararı
# ---------------------------------------------------------------------------

def test_since_yoksa_her_sey_yeni():
    assert S.yeni_mi("2001-01-01", None) is True


def test_since_sonrasi_yeni():
    assert S.yeni_mi("2024-06-01", "2024-01-01") is True
    assert S.yeni_mi("2024-01-01", "2024-01-01") is True   # sınır dahil


def test_since_oncesi_eski():
    assert S.yeni_mi("2023-12-31", "2024-01-01") is False


def test_tarih_cozulemezse_DAHIL_edilir():
    """Belirsizlikte karar ATLANMAZ — eksik metadata yüzünden gerçek bir
    kararı kaçırmak, fazladan işlemekten daha kötü."""
    assert S.yeni_mi(None, "2024-01-01") is True
    assert S.yeni_mi("bozuk-tarih", "2024-01-01") is True


# ---------------------------------------------------------------------------
# Durum kaydı
# ---------------------------------------------------------------------------

def test_bos_kokte_none_doner(kok):
    assert S.since_hesapla(kok, "yargitay") is None
    assert S.yukle(kok) == {}


def test_kaydet_ve_oku(kok):
    S.kaydet(kok, "yargitay", "2024-06-15", eklenen=120)
    d = S.yukle(kok)["yargitay"]
    assert d["son_karar_tarihi"] == "2024-06-15"
    assert d["toplam_kayit"] == 120
    assert d["son_kosu"]


def test_imlec_yalnizca_ILERI_gider(kok):
    """Yarım kalan bir koşu imleci geri çekip sonraki koşuları bozmamalı."""
    S.kaydet(kok, "yargitay", "2024-06-15")
    S.kaydet(kok, "yargitay", "2024-01-01")      # daha eski
    assert S.yukle(kok)["yargitay"]["son_karar_tarihi"] == "2024-06-15"


def test_imlec_none_ise_korunur(kok):
    """Hiç karar bulunamayan koşu imleci silmemeli."""
    S.kaydet(kok, "yargitay", "2024-06-15")
    S.kaydet(kok, "yargitay", None)
    assert S.yukle(kok)["yargitay"]["son_karar_tarihi"] == "2024-06-15"


def test_toplam_kayit_birikir(kok):
    S.kaydet(kok, "danistay", "2024-01-01", eklenen=50)
    S.kaydet(kok, "danistay", "2024-02-01", eklenen=30)
    assert S.yukle(kok)["danistay"]["toplam_kayit"] == 80


def test_kaynaklar_birbirini_etkilemez(kok):
    S.kaydet(kok, "yargitay", "2024-06-15")
    S.kaydet(kok, "danistay", "2023-01-01")
    d = S.yukle(kok)
    assert d["yargitay"]["son_karar_tarihi"] == "2024-06-15"
    assert d["danistay"]["son_karar_tarihi"] == "2023-01-01"


def test_since_guvenlik_payi_uygulanir(kok):
    """Kaynaklar geriye dönük yayın yapıyor: imleci olduğu gibi kullanmak
    aradan karar kaçırır."""
    S.kaydet(kok, "yargitay", "2024-06-15")
    since = S.since_hesapla(kok, "yargitay", guvenlik_payi_gun=30)
    assert since == "2024-05-16"
    assert since < "2024-06-15"


def test_bozuk_json_cokmez(kok):
    (kok / "scrape_state.json").write_text("{bozuk", encoding="utf-8")
    assert S.yukle(kok) == {}
    assert S.since_hesapla(kok, "yargitay") is None


def test_bozuk_tarih_imleci_none_yapar(kok):
    (kok / "scrape_state.json").write_text(
        json.dumps({"yargitay": {"son_karar_tarihi": "bozuk"}}), encoding="utf-8")
    assert S.since_hesapla(kok, "yargitay") is None


# ---------------------------------------------------------------------------
# Scraper entegrasyonu
# ---------------------------------------------------------------------------

def test_yargitay_payload_since_ile_tarih_gonderir():
    """Yargıtay filtreyi SUNUCU tarafında uygular — asıl kazanç bu."""
    from scrapers.yargitay import _build_search_payload

    p = _build_search_payload("icra", "12. Hukuk Dairesi", 50, 1, since="2024-05-16")
    assert p["data"]["baslangicTarihi"] == "16.05.2024"


def test_yargitay_payload_sincesiz_bos_birakir():
    from scrapers.yargitay import _build_search_payload

    p = _build_search_payload("icra", "12. Hukuk Dairesi", 50, 1)
    assert p["data"]["baslangicTarihi"] == ""


def test_yargitay_yeniden_eskiye_siralar():
    """Yeni kararların ilk sayfalarda çıkması buna bağlı."""
    from scrapers.yargitay import _build_search_payload

    p = _build_search_payload("icra", "12. HD", 50, 1)["data"]
    assert p["siralamaDirection"] == "desc"


def test_base_atlanmali_mi(tmp_path):
    from scrapers.base import BaseScraper

    class _S(BaseScraper):
        source_name = "test"

        async def discover(self):
            ...

        async def fetch_detail(self, item):
            ...

    s = _S(root=tmp_path, since="2024-01-01")
    assert s.atlanmali_mi("2023-06-01") is True
    assert s.atlanmali_mi("2024-06-01") is False
    assert s.atlanmali_mi(None) is False          # belirsizde atlama

    s2 = _S(root=tmp_path)                        # since yok
    assert s2.atlanmali_mi("1999-01-01") is False


def test_base_imlec_en_yeniyi_takip_eder(tmp_path):
    from scrapers.base import BaseScraper

    class _S(BaseScraper):
        source_name = "test"

        async def discover(self):
            ...

        async def fetch_detail(self, item):
            ...

    s = _S(root=tmp_path)
    for t in ("2024-01-05", "2024-06-20", "2024-03-01", None, "bozuk"):
        s.append_cleaned({"id": "x", "decision_date": t})

    assert s.en_yeni_tarih == "2024-06-20"
    assert s.eklenen_kayit == 5

    s.durumu_kaydet()
    assert S.yukle(tmp_path)["test"]["son_karar_tarihi"] == "2024-06-20"
