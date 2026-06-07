"""
İhtarname Üretim Servisi

Türk hukukunda noter ihtarnamesi üretir. TBK 117 (temerrüt),
İİK 51 (icra ihtarı), TBK 89 (ifa yeri), TBK 315 (kira),
TTK 808 (çek) gibi referansları kullanır.

Bu modül LLM ile gerçekçi taslak üretir; nihai kullanım için
mutlaka avukat ve noter onayı gerekir.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

try:
    from llm.provider import generate
except Exception:  # pragma: no cover
    generate = None  # type: ignore


# Tür → (varsayılan tahsilat süresi gün, yasal referanslar, açıklama)
TUR_PROFILLERI: Dict[str, Dict] = {
    "alacak_temerrut": {
        "ad": "Alacak Temerrüt İhtarnamesi",
        "sure_gun": 7,
        "referanslar": ["TBK m. 117", "TBK m. 88", "TBK m. 120"],
        "aciklama": (
            "Vadesi gelmiş bir alacağın ödenmesi için borçluyu "
            "temerrüde düşürmek amacıyla çekilen ihtar."
        ),
    },
    "kira_tahliye": {
        "ad": "Kira Borcundan Dolayı Tahliye İhtarnamesi",
        "sure_gun": 30,
        "referanslar": ["TBK m. 315", "TBK m. 352", "İİK m. 269"],
        "aciklama": (
            "Kira bedelinin ödenmemesi nedeniyle kiracıya verilen "
            "ödeme ve tahliye ihtarı."
        ),
    },
    "cek_ihtari": {
        "ad": "Karşılıksız Çek İhtarnamesi",
        "sure_gun": 10,
        "referanslar": ["TTK m. 808", "TTK m. 780", "Çek K. m. 5"],
        "aciklama": (
            "Karşılıksız çıkan çekin bedelinin tahsili için "
            "keşideciye veya cirantaya çekilen ihtar."
        ),
    },
    "fesih_ihtari": {
        "ad": "Sözleşme Fesih İhtarnamesi",
        "sure_gun": 15,
        "referanslar": ["TBK m. 117", "TBK m. 125", "TBK m. 126"],
        "aciklama": (
            "Borcun ifa edilmemesi nedeniyle sözleşmenin "
            "feshedileceğine dair ihtar."
        ),
    },
    "tahliye_30gun": {
        "ad": "30 Günlük Tahliye İhtarnamesi",
        "sure_gun": 30,
        "referanslar": ["TBK m. 315", "TBK m. 352/2", "İİK m. 269"],
        "aciklama": (
            "Bir kira yılı içinde iki haklı ihtara sebebiyet veren "
            "kiracıya çekilen 30 günlük tahliye ihtarı."
        ),
    },
    "genel": {
        "ad": "Genel İhtarname",
        "sure_gun": 7,
        "referanslar": ["TBK m. 117", "İİK m. 51"],
        "aciklama": (
            "Hak ve taleplerin karşı tarafa resmi olarak bildirilmesi "
            "için çekilen genel ihtarname."
        ),
    },
}

YASAL_UYARI = (
    "AI taslağı, noter onayından önce avukat incelemesi gerekir. "
    "Bu metin sadece taslak amaçlıdır; somut olayın özelliklerine göre "
    "değiştirilmesi zorunludur."
)


SISTEM_PROMPT = """Sen Türk hukukunda noter ihtarnamesi yazan deneyimli bir avukatsın.
TBK 117 (temerrüt), İİK 51 (icra ihtarı), TBK 89 (ifa yeri),
TBK 315 (kira), TBK 352 (tahliye), TTK 808 (çek) referanslarını
yerinde ve doğru kullan.

Kurallar:
- Tarih, miktar (rakam ve yazı ile), taraf bilgileri eksiksiz olsun.
- Resmi, ağır ve hukuki dil kullan. Argo veya tehditkar ifade KULLANMA.
- "Aksi takdirde aleyhinize yasal yollara müracaat edileceği" gibi
  standart kalıpları kullan.
- Para tutarlarını "X TL (yazı ile: X Türk Lirası)" formatında yaz.
- Faiz, gecikme zammı, icra masrafları talep hakkını saklı tut.
- Tebliğden itibaren süreyi açıkça belirt.
- KARAR METNİ İÇİNE YORUM, AÇIKLAMA VEYA NOT EKLEME.
- Sadece ihtarname metnini üret, başka hiçbir şey ekleme.

ÇIKTI FORMATI (KESİNLİKLE bu yapıya uy):

İHTARNAME

İHTAR EDEN (ALACAKLI)
Ad-Soyad/Unvan : ...
Adres          : ...
Vekili         : ... (varsa)

MUHATAP (BORÇLU)
Ad-Soyad/Unvan : ...
Adres          : ...

KONU: [kısa konu özeti]

AÇIKLAMALAR:
1. [Borcun doğumu, dayanak belge, vade]
2. [Borcun miktarı, faiz, ferileri]
3. [Temerrüt / TBK m. 117 atfı veya ilgili madde]
4. [Talep edilen eylem]

SONUÇ VE TALEP:
İşbu ihtarın tebliğinden itibaren ... (...) gün içinde toplam
... TL (yazı ile: ...) tutarındaki borcun ... hesabına/elden
ödenmesi, aksi takdirde aleyhinize icra takibi başlatılacağı,
yargılama gideri, vekalet ücreti ve faizin tarafınızca
ödetileceği hususu, fazlaya ilişkin haklarımız saklı kalmak
kaydıyla ihtar olunur.

[Tarih: GG.AA.YYYY]
İHTAR EDEN / VEKİLİ
[Ad-Soyad / İmza]
"""


def _format_para(tutar: Decimal) -> str:
    """Decimal tutarı '12.345,67 TL' formatında string'e çevirir."""
    try:
        # Türk formatı: binlik nokta, ondalık virgül
        s = f"{tutar:,.2f}"
        # 1,234.56 → 1.234,56
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s} TL"
    except Exception:
        return f"{tutar} TL"


def _format_tarih(d: date | str | None) -> str:
    if d is None:
        return "—"
    if isinstance(d, str):
        return d
    try:
        return d.strftime("%d.%m.%Y")
    except Exception:
        return str(d)


def _build_user_prompt(
    tur: str,
    profil: dict,
    taraflar: dict,
    alacak_detay: dict,
    ek_talepler: Optional[List[str]],
) -> str:
    """LLM'e gönderilecek detaylı kullanıcı promptunu oluşturur."""
    anapara = alacak_detay.get("anapara", Decimal("0"))
    if not isinstance(anapara, Decimal):
        try:
            anapara = Decimal(str(anapara))
        except Exception:
            anapara = Decimal("0")

    faiz = alacak_detay.get("faiz_orani", 0.0)
    vade = _format_tarih(alacak_detay.get("vade_tarihi"))
    neden = alacak_detay.get("neden", "—")
    dayanak = alacak_detay.get("dayanak_belge", "—")

    vekil_satiri = ""
    if taraflar.get("alacakli_vekil"):
        vekil_satiri = f"\n- Alacaklı Vekili: {taraflar['alacakli_vekil']}"

    ek_talepler_satiri = ""
    if ek_talepler:
        ek_talepler_satiri = "\n\nEK TALEPLER:\n" + "\n".join(
            f"- {t}" for t in ek_talepler if t and t.strip()
        )

    bugun = datetime.now().strftime("%d.%m.%Y")

    prompt = f"""Aşağıdaki bilgilerle bir {profil['ad']} hazırla.

İHTARNAME TÜRÜ: {tur} ({profil['ad']})
AÇIKLAMA: {profil['aciklama']}
KULLANILACAK YASAL REFERANSLAR: {", ".join(profil['referanslar'])}
TAHSİLAT SÜRESİ: {profil['sure_gun']} gün
BUGÜNÜN TARİHİ: {bugun}

TARAFLAR:
- Alacaklı (İhtar Eden): {taraflar.get('alacakli_ad', '—')}
- Alacaklı Adresi: {taraflar.get('alacakli_adres', '—')}{vekil_satiri}
- Borçlu (Muhatap): {taraflar.get('borclu_ad', '—')}
- Borçlu Adresi: {taraflar.get('borclu_adres', '—')}

ALACAK DETAYI:
- Anapara: {_format_para(anapara)}
- Faiz Oranı: %{faiz} (yıllık)
- Vade Tarihi: {vade}
- Borcun Sebebi: {neden}
- Dayanak Belge: {dayanak}{ek_talepler_satiri}

GÖREVİN: Yukarıdaki sistem promptundaki formata BİREBİR uygun, hukuken
geçerli, eksiksiz bir ihtarname metni üret. Sadece metni üret, başka
açıklama yapma. Tarihi {bugun} olarak yaz."""
    return prompt


def _bos_sonuc(tur: str, profil: dict, hata: str) -> dict:
    return {
        "ihtarname_metni": "",
        "tur": tur,
        "yasa_referanslari": profil["referanslar"],
        "tahsilat_suresi_gun": profil["sure_gun"],
        "uyari": YASAL_UYARI,
        "hata": hata,
    }


def ihtarname_olustur(
    tur: str,
    taraflar: dict,
    alacak_detay: dict,
    ek_talepler: list[str] | None = None,
) -> dict:
    """
    Türk hukukuna uygun bir noter ihtarnamesi taslağı üretir.

    Args:
        tur: "alacak_temerrut" | "kira_tahliye" | "cek_ihtari" |
             "fesih_ihtari" | "tahliye_30gun" | "genel"
        taraflar: {
            "alacakli_ad": str,
            "alacakli_adres": str,
            "borclu_ad": str,
            "borclu_adres": str,
            "alacakli_vekil": str (opsiyonel),
        }
        alacak_detay: {
            "anapara": Decimal,
            "faiz_orani": float,
            "vade_tarihi": date,
            "neden": str,
            "dayanak_belge": str,
        }
        ek_talepler: opsiyonel ek talep listesi (örn. faiz, masraf)

    Returns:
        {
            "ihtarname_metni": str,
            "tur": str,
            "yasa_referanslari": [str],
            "tahsilat_suresi_gun": int,
            "uyari": str,
        }
    """
    profil = TUR_PROFILLERI.get(tur, TUR_PROFILLERI["genel"])

    # Girdi doğrulama
    if not taraflar or not isinstance(taraflar, dict):
        return _bos_sonuc(tur, profil, "Taraflar bilgisi eksik.")

    gerekli = ["alacakli_ad", "alacakli_adres", "borclu_ad", "borclu_adres"]
    eksikler = [k for k in gerekli if not taraflar.get(k)]
    if eksikler:
        return _bos_sonuc(
            tur, profil, f"Zorunlu taraf alanları eksik: {', '.join(eksikler)}"
        )

    if not alacak_detay or not isinstance(alacak_detay, dict):
        return _bos_sonuc(tur, profil, "Alacak detayı eksik.")

    if generate is None:
        return _bos_sonuc(
            tur, profil, "LLM provider yüklenemedi. llm/provider.py kontrol edin."
        )

    user_prompt = _build_user_prompt(tur, profil, taraflar, alacak_detay, ek_talepler)

    try:
        metin = generate(
            system=SISTEM_PROMPT,
            user=user_prompt,
            max_tokens=2000,
            provider=None,
            temperature=0.25,
        )
    except TypeError:
        try:
            metin = generate(
                system=SISTEM_PROMPT,
                user=user_prompt,
                max_tokens=2000,
            )
        except Exception as e:
            return _bos_sonuc(tur, profil, f"LLM çağrısı başarısız: {e}")
    except Exception as e:
        return _bos_sonuc(tur, profil, f"LLM çağrısı başarısız: {e}")

    if isinstance(metin, dict):
        metin = metin.get("text") or metin.get("content") or metin.get("output") or ""
    metin = str(metin).strip()

    if not metin:
        return _bos_sonuc(tur, profil, "LLM boş yanıt döndü.")

    return {
        "ihtarname_metni": metin,
        "tur": tur,
        "yasa_referanslari": profil["referanslar"],
        "tahsilat_suresi_gun": profil["sure_gun"],
        "uyari": YASAL_UYARI,
    }


__all__ = [
    "ihtarname_olustur",
    "TUR_PROFILLERI",
    "YASAL_UYARI",
]
