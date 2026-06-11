"""Türk hukuku icra/tahsilat süreci için faiz, harç ve vekalet ücreti hesaplayıcı.

LLM kullanmaz — saf, deterministik Decimal aritmetiği.

Kapsam:
- Temerrüt faizi (TBK 88 yasal faiz, TCMB ticari avans, TCMB reeskont)
- İİK harçları (cezaevi harcı %2, tahsil harcı %4.55)
- Vekalet ücreti (Avukatlık Asgari Ücret Tarifesi 2024 — yaklaşık kademeli)

UYARI: Bu modül tahmini hesap yapar. Kesin değer mahkeme/icra müdürlüğü
takdirindedir. Avukat/muhasebeci kontrolü zorunludur.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any

# Para hesabı için yeterli hassasiyet
getcontext().prec = 28

# -----------------------------------------------------------------------------
# Faiz oranları — yaklaşık, yıl bazlı sabit sözlük (gerçek TCMB verisi)
# Yıllık % olarak (örn 8.25 = %8.25)
# -----------------------------------------------------------------------------

TCMB_AVANS_YILLIK: dict[int, float] = {
    2020: 8.25,
    2021: 14.0,
    2022: 13.75,
    2023: 22.5,
    2024: 45.0,
    2025: 47.5,
    2026: 47.5,
}

YASAL_FAIZ_YILLIK: dict[int, float] = {  # TBK 88 — değişken
    2020: 9.0,
    2021: 9.0,
    2022: 9.0,
    2023: 9.0,
    2024: 9.0,
    2025: 9.0,
    2026: 9.0,
}

# TCMB reeskont oranı (yaklaşık, yıllık %)
TCMB_REESKONT_YILLIK: dict[int, float] = {
    2020: 9.0,
    2021: 14.75,
    2022: 14.75,
    2023: 23.5,
    2024: 48.0,
    2025: 50.5,
    2026: 50.5,
}

FAIZ_TABLOLARI: dict[str, dict[int, float]] = {
    "yasal": YASAL_FAIZ_YILLIK,
    "ticari_avans": TCMB_AVANS_YILLIK,
    "tcmb_reeskont": TCMB_REESKONT_YILLIK,
}

# Varsayılan oran (tabloda yoksa kullanılır)
VARSAYILAN_ORAN: dict[str, float] = {
    "yasal": 9.0,
    "ticari_avans": 47.5,
    "tcmb_reeskont": 50.5,
}

# İİK harçları
CEZAEVI_HARCI_ORAN = Decimal("0.02")        # %2
TAHSIL_HARCI_ORAN = Decimal("0.0455")       # %4.55

UYARI_METNI = (
    "Hesaplama tahmini, kesin değer için tahsilat aşamasında "
    "mahkeme/icra müdürlüğü değerlendirir. Avukat/muhasebeci kontrolü zorunludur."
)


# -----------------------------------------------------------------------------
# Yardımcılar
# -----------------------------------------------------------------------------

def _kurus_yuvarla(x: Decimal) -> Decimal:
    """Türk lirası — iki ondalık (kuruş) yuvarlama."""
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _yilin_gun_sayisi(yil: int) -> int:
    """Artık yıl mı?"""
    if (yil % 4 == 0 and yil % 100 != 0) or (yil % 400 == 0):
        return 366
    return 365


def _yillara_bol(baslangic: date, bitis: date) -> list[tuple[int, int]]:
    """Tarih aralığını yıllara böl.

    Returns:
      [(yil, gun_sayisi), ...]  — baslangic dahil, bitis dahil
    """
    if bitis < baslangic:
        return []
    sonuc: list[tuple[int, int]] = []
    cur = baslangic
    while cur <= bitis:
        yil_sonu = date(cur.year, 12, 31)
        segment_son = min(yil_sonu, bitis)
        gun = (segment_son - cur).days + 1
        sonuc.append((cur.year, gun))
        cur = segment_son + timedelta(days=1)
    return sonuc


def _oran_getir(faiz_turu: str, yil: int) -> float:
    if faiz_turu not in FAIZ_TABLOLARI:
        raise ValueError(
            f"Bilinmeyen faiz_turu: {faiz_turu!r}. "
            f"Geçerli: {list(FAIZ_TABLOLARI.keys())}"
        )
    # Önce güncellenebilir JSON kaynağına bak (TCMB EVDS güncellemeleri),
    # yoksa statik fallback tabloya düş. Bkz: services/faiz_oranlari.py
    try:
        from services.faiz_oranlari import oran_overrides
        overrides = oran_overrides(faiz_turu)
        if yil in overrides:
            return overrides[yil]
    except Exception:
        pass
    tablo = FAIZ_TABLOLARI[faiz_turu]
    if yil in tablo:
        return tablo[yil]
    # Yoksa en yakın yılı veya varsayılan
    if tablo:
        en_yakin = max(tablo.keys()) if yil > max(tablo.keys()) else min(tablo.keys())
        return tablo[en_yakin]
    return VARSAYILAN_ORAN[faiz_turu]


# -----------------------------------------------------------------------------
# Vekalet ücreti — AAÜT 2024 yaklaşık kademeli
# (Resmi tarifenin basitleştirilmiş yansıması — gerçek hesap için baroya bakın)
# -----------------------------------------------------------------------------

# (üst_sinir_TRY, oran, sabit_eklenti) — alacağa göre kademeli
AAUT_2024_KADEMELER: list[tuple[Decimal, Decimal, Decimal]] = [
    (Decimal("80000"),    Decimal("0.16"), Decimal("0")),
    (Decimal("320000"),   Decimal("0.15"), Decimal("12800")),
    (Decimal("800000"),   Decimal("0.12"), Decimal("48800")),
    (Decimal("1600000"),  Decimal("0.10"), Decimal("106400")),
    (Decimal("3200000"),  Decimal("0.08"), Decimal("186400")),
]
# Üstü için son satır + %6
AAUT_2024_USTU_ORAN = Decimal("0.06")
AAUT_MINIMUM = Decimal("17900")  # 2024 maktu asgari ücret yaklaşık


def _vekalet_ucreti_hesapla(alacak: Decimal) -> Decimal:
    """Kademeli vekalet ücreti — AAÜT 2024 yaklaşık."""
    if alacak <= Decimal("0"):
        return _kurus_yuvarla(AAUT_MINIMUM)

    onceki_sinir = Decimal("0")
    for ust_sinir, oran, sabit in AAUT_2024_KADEMELER:
        if alacak <= ust_sinir:
            ek = (alacak - onceki_sinir) * oran
            ucret = sabit + ek
            return _kurus_yuvarla(max(ucret, AAUT_MINIMUM))
        onceki_sinir = ust_sinir

    # En üst kademe üstü — son satırın üst sınırından itibaren %6
    son_sinir, son_kademe_oran, son_sabit = AAUT_2024_KADEMELER[-1]
    son_kademe_alt = (
        AAUT_2024_KADEMELER[-2][0] if len(AAUT_2024_KADEMELER) >= 2 else Decimal("0")
    )
    son_kademe_tam = (son_sinir - son_kademe_alt) * son_kademe_oran
    ust = (alacak - son_sinir) * AAUT_2024_USTU_ORAN
    ucret = son_sabit + son_kademe_tam + ust
    return _kurus_yuvarla(max(ucret, AAUT_MINIMUM))


# -----------------------------------------------------------------------------
# Ana hesap fonksiyonu
# -----------------------------------------------------------------------------

def hesapla(
    anapara: Decimal,
    temerrut_tarihi: date,
    vade_tarihi: date | None,
    faiz_turu: str,
    ana_para_para_birimi: str = "TRY",
) -> dict[str, Any]:
    """Temerrüt faizi + İİK harçları + vekalet ücreti hesabı.

    Args:
      anapara: Borç anaparası (TRY varsayılan)
      temerrut_tarihi: Borçlunun temerrüde düştüğü tarih
      vade_tarihi: Hesaplama bitiş tarihi (None → bugün)
      faiz_turu: "yasal" | "ticari_avans" | "tcmb_reeskont"
      ana_para_para_birimi: Bilgi amaçlı (hesap TRY üzerinden)

    Returns:
      {
        "anapara": Decimal,
        "faiz_baslangic": date,
        "faiz_bitis": date,
        "gun_sayisi": int,
        "faiz_tutari": Decimal,
        "cezaevi_harci": Decimal,
        "tahsil_harci": Decimal,
        "vekalet_ucreti": Decimal,
        "toplam_alacak": Decimal,
        "yillik_breakdown": [{"yil": int, "gun": int, "oran": float, "faiz": Decimal}],
        "uyari": str,
      }
    """
    if not isinstance(anapara, Decimal):
        anapara = Decimal(str(anapara))
    if anapara < 0:
        raise ValueError("Anapara negatif olamaz")

    if vade_tarihi is None:
        vade_tarihi = date.today()

    # Gün hesabı: temerrüt_tarihi + 1 → vade_tarihi (kararlaştırılmış formül)
    faiz_baslangic = temerrut_tarihi + timedelta(days=1)
    faiz_bitis = vade_tarihi

    if faiz_bitis < faiz_baslangic:
        # Vade temerrütten önce/aynı — faiz yok
        anapara_y = _kurus_yuvarla(anapara)
        cezaevi = _kurus_yuvarla(anapara_y * CEZAEVI_HARCI_ORAN)
        tahsil = _kurus_yuvarla(anapara_y * TAHSIL_HARCI_ORAN)
        vekalet = _vekalet_ucreti_hesapla(anapara_y)
        return {
            "anapara": anapara_y,
            "faiz_baslangic": faiz_baslangic,
            "faiz_bitis": faiz_bitis,
            "gun_sayisi": 0,
            "faiz_tutari": Decimal("0.00"),
            "cezaevi_harci": cezaevi,
            "tahsil_harci": tahsil,
            "vekalet_ucreti": vekalet,
            "toplam_alacak": _kurus_yuvarla(anapara_y + cezaevi + tahsil + vekalet),
            "yillik_breakdown": [],
            "uyari": UYARI_METNI,
        }

    # Yıllara böl, her yıl için faiz hesapla
    segmentler = _yillara_bol(faiz_baslangic, faiz_bitis)
    toplam_faiz = Decimal("0")
    breakdown: list[dict[str, Any]] = []
    toplam_gun = 0

    for yil, gun in segmentler:
        oran_yillik = _oran_getir(faiz_turu, yil)
        gun_baz = _yilin_gun_sayisi(yil)
        # Basit (yıllık) faiz: anapara * oran * (gun/gun_baz)
        oran_dec = Decimal(str(oran_yillik)) / Decimal("100")
        faiz_seg = anapara * oran_dec * Decimal(gun) / Decimal(gun_baz)
        faiz_seg_y = _kurus_yuvarla(faiz_seg)
        toplam_faiz += faiz_seg_y
        toplam_gun += gun
        breakdown.append({
            "yil": yil,
            "gun": gun,
            "oran": float(oran_yillik),
            "faiz": faiz_seg_y,
        })

    anapara_y = _kurus_yuvarla(anapara)
    toplam_faiz_y = _kurus_yuvarla(toplam_faiz)

    # Harçlar — alacak üzerinden (anapara + faiz)
    alacak_brut = anapara_y + toplam_faiz_y
    cezaevi = _kurus_yuvarla(alacak_brut * CEZAEVI_HARCI_ORAN)
    tahsil = _kurus_yuvarla(alacak_brut * TAHSIL_HARCI_ORAN)
    vekalet = _vekalet_ucreti_hesapla(alacak_brut)

    toplam = _kurus_yuvarla(anapara_y + toplam_faiz_y + cezaevi + tahsil + vekalet)

    return {
        "anapara": anapara_y,
        "faiz_baslangic": faiz_baslangic,
        "faiz_bitis": faiz_bitis,
        "gun_sayisi": toplam_gun,
        "faiz_tutari": toplam_faiz_y,
        "cezaevi_harci": cezaevi,
        "tahsil_harci": tahsil,
        "vekalet_ucreti": vekalet,
        "toplam_alacak": toplam,
        "yillik_breakdown": breakdown,
        "uyari": UYARI_METNI,
    }


__all__ = [
    "hesapla",
    "TCMB_AVANS_YILLIK",
    "YASAL_FAIZ_YILLIK",
    "TCMB_REESKONT_YILLIK",
    "UYARI_METNI",
]
