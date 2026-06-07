"""
Zamanaşımı Hesaplama Servisi

Türk hukukunda farklı dava ve alacak türlerinin zamanaşımı sürelerini hesaplar.
LLM kullanmaz; deterministik tarih aritmetiği yapar.

UYARI: Bu modül yaklaşık bilgi sağlar. Zamanaşımı süreleri her somut olayda farklı
işleyebilir (kesilme, durma, def'i ileri sürme zorunluluğu vb.). Kesin sonuç için
mutlaka bir avukata danışın.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple


# (kategori, alt_tip) -> (yil_sayisi, kanun_referans, aciklama)
ZAMANASIMI_SURELERI: Dict[Tuple[str, str], Tuple[int, str, str]] = {
    # Alacaklar
    ("alacak", "genel"): (10, "TBK 146", "Genel alacak"),
    ("alacak", "kira"): (5, "TBK 147/1", "Kira alacağı"),
    ("alacak", "ucret"): (5, "TBK 147/3", "Ücret alacağı"),
    ("alacak", "isci_ucreti"): (5, "İş K 32", "İşçi ücreti"),
    ("alacak", "kambiyo_senedi"): (3, "TTK 778", "Kambiyo senetlerinde poliçeden doğan"),
    ("alacak", "cek"): (3, "TTK 814", "Çekin keşidecisine karşı"),

    # Ticari
    ("ticari", "sirket_borc"): (10, "TBK 146", "Ticari şirketten doğan borç"),

    # Vergi / Amme
    ("vergi", "amme_alacagi"): (5, "AATUHK 102", "Amme alacağı tahsil zamanaşımı"),
    ("vergi", "vergi_alacagi"): (5, "VUK 114", "Vergi alacağı"),

    # Haksız fiil
    ("haksiz_fiil", "maddi"): (2, "TBK 72", "Haksız fiil — fiili öğrenmeden 2 yıl, her halükarda 10 yıl"),
    ("haksiz_fiil", "manevi"): (2, "TBK 72", "Haksız fiil — maddi ile aynı"),

    # İş kazası
    ("is_kazasi", "tazminat"): (10, "TBK 146", "İş kazası tazminatı"),

    # Sebepsiz zenginleşme
    ("haksiz_iktisap", "genel"): (2, "TBK 82", "Sebepsiz zenginleşmeden — bilmeden 2 yıl, her halükarda 10"),

    # Kira
    ("kira", "tahliye"): (1, "TBK 339", "Tahliye davası"),

    # İcra
    ("icra", "ilamsiz_takip"): (10, "İİK 39 - ilamsız", "İlamsız icra takibi"),
    ("icra", "ilamli_takip"): (10, "İİK 39 - ilamlı", "İlamlı icra takibi"),

    # Nafaka
    ("nafaka", "yardim"): (5, "TBK 147/4", "Yardım nafakası"),

    # Aile
    ("aile", "bosanma"): (10, "TMK 178", "Boşanmadan doğan maddi/manevi tazminat"),
}


# Kategori başlıkları (UI için okunabilir Türkçe etiketler)
KATEGORI_ETIKETLERI: Dict[str, str] = {
    "alacak": "Alacak",
    "ticari": "Ticari",
    "vergi": "Vergi / Amme Alacağı",
    "haksiz_fiil": "Haksız Fiil",
    "is_kazasi": "İş Kazası",
    "haksiz_iktisap": "Sebepsiz Zenginleşme",
    "kira": "Kira",
    "icra": "İcra",
    "nafaka": "Nafaka",
    "aile": "Aile Hukuku",
}

# Alt tip başlıkları
ALT_TIP_ETIKETLERI: Dict[Tuple[str, str], str] = {
    ("alacak", "genel"): "Genel alacak (10 yıl)",
    ("alacak", "kira"): "Kira alacağı (5 yıl)",
    ("alacak", "ucret"): "Ücret alacağı (5 yıl)",
    ("alacak", "isci_ucreti"): "İşçi ücreti (5 yıl)",
    ("alacak", "kambiyo_senedi"): "Kambiyo senedi (3 yıl)",
    ("alacak", "cek"): "Çek (3 yıl)",
    ("ticari", "sirket_borc"): "Şirket borcu (10 yıl)",
    ("vergi", "amme_alacagi"): "Amme alacağı (5 yıl)",
    ("vergi", "vergi_alacagi"): "Vergi alacağı (5 yıl)",
    ("haksiz_fiil", "maddi"): "Maddi tazminat (2/10 yıl)",
    ("haksiz_fiil", "manevi"): "Manevi tazminat (2/10 yıl)",
    ("is_kazasi", "tazminat"): "İş kazası tazminatı (10 yıl)",
    ("haksiz_iktisap", "genel"): "Sebepsiz zenginleşme (2/10 yıl)",
    ("kira", "tahliye"): "Tahliye davası (1 yıl)",
    ("icra", "ilamsiz_takip"): "İlamsız icra takibi (10 yıl)",
    ("icra", "ilamli_takip"): "İlamlı icra takibi (10 yıl)",
    ("nafaka", "yardim"): "Yardım nafakası (5 yıl)",
    ("aile", "bosanma"): "Boşanmadan doğan tazminat (10 yıl)",
}


YASAL_UYARI = (
    "Bu hesap YAKLAŞIK bilgi içindir. Zamanaşımı süreleri somut olayda kesilme, "
    "durma, def'i ileri sürme zorunluluğu ve özel mevzuat nedeniyle farklı işleyebilir. "
    "Hak kaybına uğramamak için mutlaka bir avukata danışın."
)


def _yil_ekle(d: date, yil: int) -> date:
    """Bir tarihe yıl ekler. 29 Şubat gibi kenar durumları güvenli işler."""
    try:
        return d.replace(year=d.year + yil)
    except ValueError:
        # 29 Şubat -> artık olmayan yılda 28 Şubat
        return d.replace(year=d.year + yil, day=28)


def list_kategoriler() -> Dict[str, List[str]]:
    """
    Mevcut kategori ve alt tipleri döndürür.

    Returns:
        {kategori: [alt_tip, ...], ...}
    """
    sonuc: Dict[str, List[str]] = {}
    for (kategori, alt_tip) in ZAMANASIMI_SURELERI.keys():
        sonuc.setdefault(kategori, []).append(alt_tip)
    # Stabil sıra için
    for k in sonuc:
        sonuc[k].sort()
    return sonuc


def kategori_etiketi(kategori: str) -> str:
    """UI için okunabilir kategori etiketi."""
    return KATEGORI_ETIKETLERI.get(kategori, kategori)


def alt_tip_etiketi(kategori: str, alt_tip: str) -> str:
    """UI için okunabilir alt tip etiketi."""
    return ALT_TIP_ETIKETLERI.get((kategori, alt_tip), alt_tip)


def _durum_belirle(kalan_gun: int) -> str:
    """
    Kalan gün sayısına göre durum kategorisi:
      - "asıldı"   : negatif (zamanaşımı geçmiş)
      - "kritik"   : 0 - 29 gün
      - "yaklasan" : 30 - 180 gün
      - "guncel"   : 180 günden fazla
    """
    if kalan_gun < 0:
        return "asıldı"
    if kalan_gun < 30:
        return "kritik"
    if kalan_gun <= 180:
        return "yaklasan"
    return "guncel"


def _uyari_ekle(
    uyarilar: List[str],
    kategori: str,
    alt_tip: str,
    durum: str,
    kesilme_sayisi: int,
) -> None:
    """Kategori-spesifik ve durum-spesifik uyarıları listeye ekler."""

    # Her zaman gösterilen genel uyarı
    uyarilar.append(YASAL_UYARI)

    # Durum uyarıları
    if durum == "asıldı":
        uyarilar.append(
            "Görünüşe göre zamanaşımı süresi geçmiş. Yine de bazı hallerde "
            "(kesilme, durma, borçlunun ikrarı) süre korunmuş olabilir; bir avukata danışın."
        )
    elif durum == "kritik":
        uyarilar.append(
            "30 günden az süre kaldı. Hak kaybı riski yüksek — ivedi olarak dava/icra "
            "açma veya ihtarname ile zamanaşımını kesme yoluna gidilmesi düşünülmeli."
        )
    elif durum == "yaklasan":
        uyarilar.append(
            "6 ay içinde zamanaşımı dolacak. Belge toplama ve hukuki strateji için "
            "şimdiden avukatla görüşmek faydalı olur."
        )

    # Kategori-spesifik uyarılar
    if kategori == "haksiz_fiil":
        uyarilar.append(
            "Haksız fiilde iki süre vardır: fiili ve faili öğrenmeden itibaren 2 yıl, "
            "her halükarda fiilin işlendiği tarihten itibaren 10 yıl (TBK 72). "
            "Bu hesap kısa süreyi esas alır; somut olayınızda hangi sürenin geçerli "
            "olduğunu mutlaka kontrol edin."
        )
        uyarilar.append(
            "Eylem aynı zamanda suç oluşturuyorsa, ceza zamanaşımı daha uzunsa o süre uygulanır."
        )
    elif kategori == "haksiz_iktisap":
        uyarilar.append(
            "Sebepsiz zenginleşmede de iki süre vardır: öğrenmeden 2 yıl, her halükarda 10 yıl (TBK 82)."
        )
    elif kategori == "vergi":
        uyarilar.append(
            "Vergi/amme alacaklarında zamanaşımı, alacağın doğduğu takvim yılını izleyen "
            "yılın başından başlar. Bu hesap basit yıl-ekleme yaklaşımı kullanır; "
            "vergi dairesinin işlem tarihleri esas alınmalıdır."
        )
    elif kategori == "icra":
        uyarilar.append(
            "İcra takibinde her takip işlemi zamanaşımını keser (İİK 39). "
            "Dosyanızdaki son işlem tarihini esas almak daha doğru olur."
        )
    elif (kategori, alt_tip) == ("alacak", "cek"):
        uyarilar.append(
            "Çekte zamanaşımı 6102 sayılı TTK ile düzenlenir; ibraz süresinin bitiminden başlar. "
            "Bu hesap olay tarihini ibraz süresi bitimi kabul eder."
        )
    elif (kategori, alt_tip) == ("kira", "tahliye"):
        uyarilar.append(
            "Tahliye davasında süre, tahliye sebebinin öğrenildiği tarihten itibaren işler. "
            "Sebebe göre süre farklılık gösterebilir."
        )

    # Kesilme uyarısı
    if kesilme_sayisi > 0:
        uyarilar.append(
            f"{kesilme_sayisi} adet kesilme tarihi dikkate alındı; en son kesilme "
            f"tarihinden itibaren süre yeniden başlatıldı (TBK 154). "
            f"Kesilme sebebinin geçerliliği (ihtar, dava, ikrar vb.) ayrıca incelenmelidir."
        )


def hesapla(
    kategori: str,
    alt_tip: str,
    olay_tarihi: date,
    kesilme_tarihleri: Optional[List[date]] = None,
) -> dict:
    """
    Bir hukuki olay için zamanaşımı durumunu hesaplar.

    Args:
        kategori: ZAMANASIMI_SURELERI sözlüğündeki kategori (örn. "alacak").
        alt_tip:  Alt tip (örn. "isci_ucreti").
        olay_tarihi: Zamanaşımı süresinin başladığı olay tarihi.
        kesilme_tarihleri: Varsa, zamanaşımını kesen tarihler (ihtar, dava, ikrar vb.).
                           Süre, en son kesilme tarihinden itibaren yeniden başlatılır.

    Returns:
        {
            "zamanasimi_yil": int,
            "kanun": str,
            "aciklama": str,
            "olay_tarihi": date,
            "baslangic_tarihi": date,   # kesilme varsa son kesilme, yoksa olay tarihi
            "bitis_tarihi": date,
            "kalan_gun": int,
            "durum": str,                # "guncel" | "yaklasan" | "kritik" | "asıldı"
            "uyarilar": [str],
            "kesilme_sayisi": int,
            "hata": str | None,
        }
    """
    anahtar = (kategori, alt_tip)
    if anahtar not in ZAMANASIMI_SURELERI:
        return {
            "zamanasimi_yil": 0,
            "kanun": "",
            "aciklama": "",
            "olay_tarihi": olay_tarihi,
            "baslangic_tarihi": olay_tarihi,
            "bitis_tarihi": olay_tarihi,
            "kalan_gun": 0,
            "durum": "asıldı",
            "uyarilar": [
                f"Bilinmeyen kategori/alt_tip: ({kategori}, {alt_tip}).",
                YASAL_UYARI,
            ],
            "kesilme_sayisi": 0,
            "hata": f"Bilinmeyen ({kategori}, {alt_tip}). "
                    f"list_kategoriler() ile geçerli değerleri görebilirsiniz.",
        }

    yil_sayisi, kanun, aciklama = ZAMANASIMI_SURELERI[anahtar]

    # Kesilme tarihlerini temizle ve sırala
    kesilmeler: List[date] = []
    if kesilme_tarihleri:
        for kd in kesilme_tarihleri:
            if isinstance(kd, date) and kd >= olay_tarihi:
                kesilmeler.append(kd)
        kesilmeler.sort()

    # Süre, en son kesilme tarihinden (varsa) yeniden başlar
    baslangic_tarihi = kesilmeler[-1] if kesilmeler else olay_tarihi

    bitis_tarihi = _yil_ekle(baslangic_tarihi, yil_sayisi)

    bugun = date.today()
    kalan_gun = (bitis_tarihi - bugun).days

    durum = _durum_belirle(kalan_gun)

    uyarilar: List[str] = []
    _uyari_ekle(uyarilar, kategori, alt_tip, durum, len(kesilmeler))

    return {
        "zamanasimi_yil": yil_sayisi,
        "kanun": kanun,
        "aciklama": aciklama,
        "olay_tarihi": olay_tarihi,
        "baslangic_tarihi": baslangic_tarihi,
        "bitis_tarihi": bitis_tarihi,
        "kalan_gun": kalan_gun,
        "durum": durum,
        "uyarilar": uyarilar,
        "kesilme_sayisi": len(kesilmeler),
        "hata": None,
    }
