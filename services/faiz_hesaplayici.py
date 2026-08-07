"""Türk hukuku icra/tahsilat süreci için faiz, harç ve vekalet ücreti hesaplayıcı.

LLM kullanmaz — saf, deterministik Decimal aritmetiği.

Kapsam:
- Temerrüt faizi (3095 sayılı Kanun m.1 yasal faiz, TCMB ticari avans,
  TCMB reeskont, TTK 1530 mal/hizmet tedarikinde geç ödeme faizi)
- İİK harçları (cezaevi harcı %2, tahsil harcı %4.55)
- Vekalet ücreti (Avukatlık Asgari Ücret Tarifesi 2024 — yaklaşık kademeli)

Oranlar gün hassasiyetinde, kaynak atıflı FAIZ_DONEMLERI tablosundan gelir
(bkz. aşağıdaki tablo başındaki not). Yasal faiz artık sabit bir yüzde değil;
7589 sayılı Kanun (RG 31.07.2026/33326) ile TCMB reeskont oranına endekslendi
ve yılda bir (gerekirse iki) kez otomatik değişir — bu modül tek bir "güncel
oran" sabiti YAZMAZ, dönem tarihine göre hesaplar.

UYARI: Bu modül tahmini hesap yapar. Kesin değer mahkeme/icra müdürlüğü
takdirindedir. Avukat/muhasebeci kontrolü zorunludur.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any

# Para hesabı için yeterli hassasiyet
getcontext().prec = 28

# -----------------------------------------------------------------------------
# Faiz oranları — yıl bazlı sabit sözlük (yalnızca FAIZ_DONEMLERI'nin
# kapsamadığı eski tarihler için fallback; bkz. aşağıdaki dönem tablosu).
# Yıllık % olarak (örn 8.25 = %8.25)
# -----------------------------------------------------------------------------

TCMB_AVANS_YILLIK: dict[int, float] = {
    2020: 8.25,
    2021: 14.0,
    2022: 13.75,
    2023: 22.5,
    2024: 45.0,
    2025: 44.25,  # 2025 başı — yıl içi kırılımlar için bkz. FAIZ_DONEMLERI
    2026: 39.75,
}

YASAL_FAIZ_YILLIK: dict[int, float] = {  # TBK 88 / 3095 sayılı Kanun m.1
    2020: 9.0,
    2021: 9.0,
    2022: 9.0,
    2023: 9.0,
    2024: 24.0,  # 1 Haziran 2024'ten itibaren (8485 sayılı CB Kararı)
    2025: 24.0,
    2026: 31.0,  # 31 Temmuz 2026'dan itibaren (7589 sayılı Kanun) — bkz. FAIZ_DONEMLERI
}

# TCMB reeskont oranı (yıllık %)
TCMB_REESKONT_YILLIK: dict[int, float] = {
    2020: 9.0,
    2021: 14.75,
    2022: 14.75,
    2023: 23.5,
    2024: 48.0,
    2025: 43.25,
    2026: 38.75,
}

# Mal/hizmet tedarikinde geç ödeme faizi — TTK 1530 (yalnızca ticari işlerde,
# tacirler arası mal/hizmet borçlarında; genel ticari temerrütle karıştırılmamalı)
TTK_1530_YILLIK: dict[int, float] = {
    2026: 43.0,
}

FAIZ_TABLOLARI: dict[str, dict[int, float]] = {
    "yasal": YASAL_FAIZ_YILLIK,
    "ticari_avans": TCMB_AVANS_YILLIK,
    "tcmb_reeskont": TCMB_REESKONT_YILLIK,
    "ttk_1530": TTK_1530_YILLIK,
}

# Varsayılan oran (tabloda yoksa kullanılır)
VARSAYILAN_ORAN: dict[str, float] = {
    "yasal": 31.0,
    "ticari_avans": 39.75,
    "tcmb_reeskont": 38.75,
    "ttk_1530": 43.0,
}

# -----------------------------------------------------------------------------
# Dönem bazlı oranlar (gün hassasiyetinde) — bir tarihe uygulanacak oran, o
# tarihe eşit veya ondan önce başlayan EN SON dönemin oranıdır. Yıl içinde
# birden fazla oran değişikliği olduğunda (örn. 2024 ve 2026'da yasal faiz)
# yukarıdaki yıllık tablolar tek bir yıla tek oran sığdıramadığından bu tablo
# esas alınır; yıllık tablolar yalnızca bu tablonun başlamadığı (daha eski)
# tarihler için fallback'tir.
#
# Kaynak (çapraz doğrulanmış — bkz. SEO_ANALIZ_VE_PLAN.md "Faiz doğruluğu"):
#  - Yasal faiz: 7589 sayılı Kanun ("12. Yargı Paketi") m.10, RG 31.07.2026/33326
#    — 3095 sayılı Kanun m.1'i değiştirdi; oran artık TCMB'nin bir önceki yılın
#    31 Aralık günkü kısa vadeli reeskont oranının %80'i (yıl ortasında reeskont
#    30 Haziran'da >5 puan sapmışsa ikinci yarı için yeniden hesaplanır).
#    1 Haziran 2024 – 30 Temmuz 2026 arası: %24 (8485 sayılı CB Kararı,
#    RG 21.05.2024/32552).
#  - Ticari avans / TCMB reeskont: TCMB'nin 8 Mart, 17 Eylül ve 20 Aralık 2025
#    tarihli reeskont-avans ilanları.
#  - TTK 1530 (mal/hizmet tedarikinde geç ödeme): TCMB'nin 2 Ocak 2026 tarihli,
#    33125 sayılı RG tebliği — %43, asgari giderim 2.020 TL.
#
# Son doğrulama: 2026-08-03. Değişiklikte scripts/update_faiz_oranlari.py
# --set ile data/faiz_oranlari.json üzerinden de override edilebilir.
FAIZ_DONEMLERI: dict[str, list[tuple[date, float]]] = {
    "yasal": [
        (date(2006, 1, 1), 9.0),
        (date(2024, 6, 1), 24.0),
        (date(2026, 7, 31), 31.0),
    ],
    "ticari_avans": [
        (date(2025, 3, 8), 44.25),
        (date(2025, 9, 17), 42.25),
        (date(2025, 12, 20), 39.75),
    ],
    "tcmb_reeskont": [
        (date(2025, 3, 8), 43.25),
        (date(2025, 9, 17), 41.25),
        (date(2025, 12, 20), 38.75),
    ],
    "ttk_1530": [
        (date(2026, 1, 2), 43.0),
    ],
}

FAIZ_DONEM_KAYNAK = (
    "7589 sayılı Kanun / 12. Yargı Paketi m.10 (RG 31.07.2026/33326); "
    "8485 sayılı Cumhurbaşkanı Kararı (RG 21.05.2024/32552); "
    "TCMB reeskont-avans ilanları; TTK 1530 tebliği (RG 02.01.2026/33125)"
)
FAIZ_DONEM_SON_KONTROL = "2026-08-03"

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


def _period_max_yil(faiz_turu: str) -> int | None:
    donemler = FAIZ_DONEMLERI.get(faiz_turu)
    if not donemler:
        return None
    return max(basl.year for basl, _ in donemler)


def _oran_getir_tarih(faiz_turu: str, gun: date) -> float:
    """Belirli bir güne uygulanacak yıllık faiz oranını (%) döndürür.

    Öncelik sırası:
    1. Dönem tablosunun kapsamadığı (gelecek) yıllar için önce JSON manuel
       override'a bakılır — operasyonel güncelleme (scripts/update_faiz_oranlari.py
       --set / --evds) kod deploy'u beklemeden devreye girsin diye.
    2. Gün hassasiyetli dönem tablosu (FAIZ_DONEMLERI) — kaynak atıflı,
       2026-08-03 itibarıyla çapraz doğrulanmış.
    3. Statik yıllık tablo / en yakın yıl / varsayılan (_oran_getir).
    """
    if faiz_turu not in FAIZ_TABLOLARI:
        raise ValueError(
            f"Bilinmeyen faiz_turu: {faiz_turu!r}. "
            f"Geçerli: {list(FAIZ_TABLOLARI.keys())}"
        )
    max_yil = _period_max_yil(faiz_turu)
    if max_yil is not None and gun.year > max_yil:
        try:
            from services.faiz_oranlari import oran_overrides
            overrides = oran_overrides(faiz_turu)
            if gun.year in overrides:
                return overrides[gun.year]
        except Exception:
            pass
    donemler = FAIZ_DONEMLERI.get(faiz_turu, [])
    uygun = [(basl, oran) for basl, oran in donemler if basl <= gun]
    if uygun:
        _, oran = max(uygun, key=lambda t: t[0])
        return oran
    return _oran_getir(faiz_turu, gun.year)


def _donemlere_bol(
    baslangic: date, bitis: date, faiz_turu: str
) -> list[tuple[date, date, int, float]]:
    """Tarih aralığını hem takvim yılına hem oran değişikliği tarihlerine göre böler.

    Aynı takvim yılı içinde oran değiştiyse (örn. 2024'te 1 Haziran, 2026'da
    31 Temmuz) tek bir yıllık oranla hesap yapmak yanlış sonuç verir; bu yüzden
    yıl sonu VE her dönem başlangıcı birer kesim noktasıdır.

    Returns:
      [(seg_baslangic, seg_bitis, gun_sayisi, oran_yillik), ...] — baslangic ve
      bitis dahil, kronolojik sırayla.
    """
    if bitis < baslangic:
        return []
    kesimler: set[date] = set()
    yil = baslangic.year
    while yil <= bitis.year:
        kesimler.add(date(yil, 12, 31))
        yil += 1
    for basl, _oran in FAIZ_DONEMLERI.get(faiz_turu, []):
        onceki_gun = basl - timedelta(days=1)
        if baslangic <= onceki_gun < bitis:
            kesimler.add(onceki_gun)
    kesim_noktalari = sorted(k for k in kesimler if baslangic <= k < bitis)

    sonuc: list[tuple[date, date, int, float]] = []
    cur = baslangic
    for k in kesim_noktalari:
        if k < cur:
            continue
        seg_son = k
        gun = (seg_son - cur).days + 1
        oran = _oran_getir_tarih(faiz_turu, cur)
        sonuc.append((cur, seg_son, gun, oran))
        cur = seg_son + timedelta(days=1)
    if cur <= bitis:
        gun = (bitis - cur).days + 1
        oran = _oran_getir_tarih(faiz_turu, cur)
        sonuc.append((cur, bitis, gun, oran))
    return sonuc


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
      faiz_turu: "yasal" | "ticari_avans" | "tcmb_reeskont" | "ttk_1530"
        ("ttk_1530" yalnızca ticari mal/hizmet tedarikinde geç ödeme faizi
        için; genel ticari temerrütle karıştırılmamalı — bkz. FAIZ_DONEMLERI
        üstündeki kaynak notu)
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
        "yillik_breakdown": [
          {"yil": int, "baslangic": date, "bitis": date, "gun": int,
           "oran": float, "faiz": Decimal}
        ],  # aynı yıl içinde oran değiştiyse (2024, 2026 gibi) birden fazla satır olabilir
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

    # Hem yıl hem de oran değişikliği tarihlerine göre böl (bkz. _donemlere_bol
    # docstring — aynı yıl içinde oran değişmişse tek oranla hesap yanlış olur)
    segmentler = _donemlere_bol(faiz_baslangic, faiz_bitis, faiz_turu)
    toplam_faiz = Decimal("0")
    breakdown: list[dict[str, Any]] = []
    toplam_gun = 0

    for seg_baslangic, seg_bitis, gun, oran_yillik in segmentler:
        gun_baz = _yilin_gun_sayisi(seg_baslangic.year)
        # Basit (yıllık) faiz: anapara * oran * (gun/gun_baz)
        oran_dec = Decimal(str(oran_yillik)) / Decimal("100")
        faiz_seg = anapara * oran_dec * Decimal(gun) / Decimal(gun_baz)
        faiz_seg_y = _kurus_yuvarla(faiz_seg)
        toplam_faiz += faiz_seg_y
        toplam_gun += gun
        breakdown.append({
            "yil": seg_baslangic.year,
            "baslangic": seg_baslangic,
            "bitis": seg_bitis,
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
    "TTK_1530_YILLIK",
    "FAIZ_TABLOLARI",
    "FAIZ_DONEMLERI",
    "FAIZ_DONEM_KAYNAK",
    "FAIZ_DONEM_SON_KONTROL",
    "UYARI_METNI",
]
