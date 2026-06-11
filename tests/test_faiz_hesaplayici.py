"""services/faiz_hesaplayici.py birim testleri.

Saf deterministik Decimal aritmetiği — dış bağımlılık yok.
"""
from datetime import date
from decimal import Decimal

import pytest

from services.faiz_hesaplayici import (
    CEZAEVI_HARCI_ORAN,
    TAHSIL_HARCI_ORAN,
    UYARI_METNI,
    _vekalet_ucreti_hesapla,
    _yilin_gun_sayisi,
    _yillara_bol,
    hesapla,
)


# ---------------------------------------------------------------- yardımcılar

def test_artik_yil():
    assert _yilin_gun_sayisi(2024) == 366
    assert _yilin_gun_sayisi(2023) == 365
    assert _yilin_gun_sayisi(2000) == 366  # 400'e bölünür
    assert _yilin_gun_sayisi(1900) == 365  # 100'e bölünür ama 400'e bölünmez


def test_yillara_bol_tek_yil():
    seg = _yillara_bol(date(2024, 1, 1), date(2024, 12, 31))
    assert seg == [(2024, 366)]


def test_yillara_bol_yil_asan():
    seg = _yillara_bol(date(2023, 12, 30), date(2024, 1, 2))
    assert seg == [(2023, 2), (2024, 2)]


def test_yillara_bol_ters_aralik_bos():
    assert _yillara_bol(date(2024, 5, 1), date(2024, 4, 30)) == []


# ------------------------------------------------------------ vekalet ücreti

def test_vekalet_minimum_uygulanir():
    # Çok küçük alacakta maktu asgari ücret döner
    assert _vekalet_ucreti_hesapla(Decimal("1000")) == Decimal("17900.00")


def test_vekalet_ilk_kademe():
    # 80.000 TL → %16 = 12.800
    assert _vekalet_ucreti_hesapla(Decimal("80000")) == Decimal("17900.00")  # min altında
    # 200.000 TL → 12.800 + (200.000-80.000)*0.15 = 30.800
    assert _vekalet_ucreti_hesapla(Decimal("200000")) == Decimal("30800.00")


def test_vekalet_kademeler_monoton_artar():
    onceki = Decimal("0")
    for tutar in (10_000, 100_000, 500_000, 1_000_000, 2_000_000, 5_000_000):
        ucret = _vekalet_ucreti_hesapla(Decimal(tutar))
        assert ucret >= onceki, f"{tutar} TL'de vekalet ücreti düştü"
        onceki = ucret


# -------------------------------------------------------------------- hesapla

def test_hesapla_temel_yasal_faiz():
    """365 günlük tam yıl, %9 yasal faiz → anapara * 0.09."""
    r = hesapla(
        anapara=Decimal("100000"),
        temerrut_tarihi=date(2022, 12, 31),
        vade_tarihi=date(2023, 12, 31),
        faiz_turu="yasal",
    )
    assert r["gun_sayisi"] == 365
    assert r["faiz_tutari"] == Decimal("9000.00")
    assert r["uyari"] == UYARI_METNI


def test_hesapla_harclar_alacak_uzerinden():
    r = hesapla(
        anapara=Decimal("100000"),
        temerrut_tarihi=date(2022, 12, 31),
        vade_tarihi=date(2023, 12, 31),
        faiz_turu="yasal",
    )
    brut = r["anapara"] + r["faiz_tutari"]
    assert r["cezaevi_harci"] == (brut * CEZAEVI_HARCI_ORAN).quantize(Decimal("0.01"))
    assert r["tahsil_harci"] == (brut * TAHSIL_HARCI_ORAN).quantize(Decimal("0.01"))


def test_hesapla_toplam_tutarli():
    r = hesapla(
        anapara=Decimal("250000"),
        temerrut_tarihi=date(2023, 6, 1),
        vade_tarihi=date(2024, 6, 1),
        faiz_turu="ticari_avans",
    )
    beklenen = (
        r["anapara"] + r["faiz_tutari"] + r["cezaevi_harci"]
        + r["tahsil_harci"] + r["vekalet_ucreti"]
    )
    assert r["toplam_alacak"] == beklenen.quantize(Decimal("0.01"))


def test_hesapla_vade_temerrutten_once_faiz_sifir():
    r = hesapla(
        anapara=Decimal("50000"),
        temerrut_tarihi=date(2024, 6, 1),
        vade_tarihi=date(2024, 5, 1),
        faiz_turu="yasal",
    )
    assert r["gun_sayisi"] == 0
    assert r["faiz_tutari"] == Decimal("0.00")
    assert r["yillik_breakdown"] == []


def test_hesapla_yil_asan_breakdown():
    r = hesapla(
        anapara=Decimal("100000"),
        temerrut_tarihi=date(2023, 11, 30),
        vade_tarihi=date(2024, 2, 29),
        faiz_turu="yasal",
    )
    yillar = [seg["yil"] for seg in r["yillik_breakdown"]]
    assert yillar == [2023, 2024]
    assert r["gun_sayisi"] == sum(seg["gun"] for seg in r["yillik_breakdown"])


def test_hesapla_negatif_anapara_hata():
    with pytest.raises(ValueError):
        hesapla(
            anapara=Decimal("-1"),
            temerrut_tarihi=date(2024, 1, 1),
            vade_tarihi=date(2024, 2, 1),
            faiz_turu="yasal",
        )


def test_hesapla_bilinmeyen_faiz_turu_hata():
    with pytest.raises(ValueError):
        hesapla(
            anapara=Decimal("1000"),
            temerrut_tarihi=date(2024, 1, 1),
            vade_tarihi=date(2024, 2, 1),
            faiz_turu="bilinmeyen",
        )


def test_hesapla_float_anapara_kabul():
    r = hesapla(
        anapara=12345.67,  # type: ignore[arg-type]
        temerrut_tarihi=date(2024, 1, 1),
        vade_tarihi=date(2024, 6, 1),
        faiz_turu="yasal",
    )
    assert r["anapara"] == Decimal("12345.67")
