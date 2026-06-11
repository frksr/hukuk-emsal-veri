"""services/zamanasimi.py birim testleri.

Deterministik tarih aritmetiği — date.today() bağımlı alanlar göreli doğrulanır.
"""
from datetime import date, timedelta

from services.zamanasimi import (
    YASAL_UYARI,
    ZAMANASIMI_SURELERI,
    _durum_belirle,
    _yil_ekle,
    alt_tip_etiketi,
    hesapla,
    kategori_etiketi,
    list_kategoriler,
)


# ---------------------------------------------------------------- yardımcılar

def test_yil_ekle_normal():
    assert _yil_ekle(date(2020, 5, 15), 5) == date(2025, 5, 15)


def test_yil_ekle_29_subat():
    # 29 Şubat → artık olmayan yılda 28 Şubat
    assert _yil_ekle(date(2024, 2, 29), 1) == date(2025, 2, 28)
    # Artık yıla denk gelirse 29 Şubat korunur
    assert _yil_ekle(date(2024, 2, 29), 4) == date(2028, 2, 29)


def test_durum_belirle_sinirlar():
    assert _durum_belirle(-1) == "asıldı"
    assert _durum_belirle(0) == "kritik"
    assert _durum_belirle(29) == "kritik"
    assert _durum_belirle(30) == "yaklasan"
    assert _durum_belirle(180) == "yaklasan"
    assert _durum_belirle(181) == "guncel"


def test_list_kategoriler_tam():
    kategoriler = list_kategoriler()
    # Sözlükteki her anahtar listede olmalı
    for (kat, alt) in ZAMANASIMI_SURELERI:
        assert alt in kategoriler[kat]


def test_etiketler():
    assert kategori_etiketi("alacak") == "Alacak"
    assert kategori_etiketi("yok_boyle_kategori") == "yok_boyle_kategori"
    assert alt_tip_etiketi("alacak", "cek") == "Çek (3 yıl)"
    assert alt_tip_etiketi("x", "y") == "y"


# -------------------------------------------------------------------- hesapla

def test_hesapla_genel_alacak_10_yil():
    olay = date(2020, 3, 1)
    r = hesapla("alacak", "genel", olay)
    assert r["hata"] is None
    assert r["zamanasimi_yil"] == 10
    assert r["kanun"] == "TBK 146"
    assert r["bitis_tarihi"] == date(2030, 3, 1)
    assert r["kalan_gun"] == (r["bitis_tarihi"] - date.today()).days


def test_hesapla_gecmis_sure_asildi():
    olay = date.today() - timedelta(days=15 * 365)
    r = hesapla("alacak", "cek", olay)  # 3 yıl
    assert r["durum"] == "asıldı"
    assert r["kalan_gun"] < 0
    assert any("zamanaşımı süresi geçmiş" in u for u in r["uyarilar"])


def test_hesapla_kesilme_sureyi_yeniler():
    olay = date.today() - timedelta(days=9 * 365)
    kesilme = date.today() - timedelta(days=30)
    r = hesapla("alacak", "genel", olay, kesilme_tarihleri=[kesilme])
    assert r["kesilme_sayisi"] == 1
    assert r["baslangic_tarihi"] == kesilme
    assert r["durum"] == "guncel"
    assert any("TBK 154" in u for u in r["uyarilar"])


def test_hesapla_olay_oncesi_kesilme_yok_sayilir():
    olay = date(2023, 1, 1)
    r = hesapla(
        "alacak", "genel", olay,
        kesilme_tarihleri=[date(2022, 1, 1)],  # olaydan önce — geçersiz
    )
    assert r["kesilme_sayisi"] == 0
    assert r["baslangic_tarihi"] == olay


def test_hesapla_kesilmeler_siralanir_en_son_esas():
    olay = date(2022, 1, 1)
    k1, k2 = date(2023, 5, 1), date(2024, 8, 1)
    r = hesapla("alacak", "genel", olay, kesilme_tarihleri=[k2, k1])
    assert r["baslangic_tarihi"] == k2
    assert r["kesilme_sayisi"] == 2


def test_hesapla_bilinmeyen_tip_hata_doner():
    r = hesapla("yok", "boyle", date(2024, 1, 1))
    assert r["hata"] is not None
    assert r["durum"] == "asıldı"
    assert YASAL_UYARI in r["uyarilar"]


def test_hesapla_yasal_uyari_her_zaman_var():
    r = hesapla("alacak", "genel", date.today())
    assert YASAL_UYARI in r["uyarilar"]


def test_hesapla_kategori_spesifik_uyarilar():
    r = hesapla("haksiz_fiil", "maddi", date.today())
    assert any("TBK 72" in u for u in r["uyarilar"])

    r = hesapla("icra", "ilamsiz_takip", date.today())
    assert any("İİK 39" in u for u in r["uyarilar"])

    r = hesapla("vergi", "amme_alacagi", date.today())
    assert any("takvim yılını izleyen" in u for u in r["uyarilar"])
