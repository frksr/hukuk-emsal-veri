"""
Karar Özetleme Servisi

Türk hukuk emsal kararlarını sade Türkçe'ye çevirir.
Genç avukatlar ve hukuk bilgisi olmayan vatandaşlar için anlaşılır özetler üretir.
"""

from __future__ import annotations

import re
from typing import Dict, List

try:
    from llm.provider import generate
except Exception:  # pragma: no cover
    generate = None  # type: ignore


# Uzunluk profili: (paragraf_sayisi_aciklamasi, max_tokens, anahtar_nokta_sayisi)
UZUNLUK_PROFILLERI: Dict[str, Dict] = {
    "kisa": {
        "paragraf": "3 paragraf",
        "max_tokens": 800,
        "anahtar_sayisi": "3-5",
        "aciklama": "kısa ve öz",
    },
    "orta": {
        "paragraf": "5 paragraf",
        "max_tokens": 1300,
        "anahtar_sayisi": "5-7",
        "aciklama": "dengeli detay",
    },
    "detayli": {
        "paragraf": "7-10 paragraf",
        "max_tokens": 2000,
        "anahtar_sayisi": "8-12",
        "aciklama": "kapsamlı ve detaylı",
    },
}

# Çok uzun kararlar için truncate eşiği (karakter)
MAX_KAYNAK_CHAR = 30000
TRUNCATE_LIMITI = 28000

YASAL_NOT = "AI özeti, orijinal metnin yerine geçmez. Hukuki işlem için orijinal karar metnini ve uzman görüşünü esas alın."


SISTEM_PROMPT_TEMPLATE = """Sen bir Türk hukuk uzmanısın. Karar metnini sade dile çevir, hukuki terimler için parantez içinde açıklama ekle.

Hedef kitle: Genç avukatlar ve hukuk bilgisi olmayan vatandaşlar.

Kurallar:
- Sade, anlaşılır Türkçe kullan.
- Hukuki terimleri (örn. "müddei", "feshi", "tazminat") parantez içinde açıkla.
- Tarafsız ve doğru ol; metinde olmayan bilgi uydurma.
- {paragraf} halinde, {aciklama} bir özet hazırla.

Çıktı formatı (KESİNLİKLE bu sırayla, başka başlık ekleme):

## ÖZET
Paragraf 1: Davacı kim, ne istiyor (sade dilde).
Paragraf 2: Mahkeme ne dedi, hangi gerekçeyle (sade dilde).
Paragraf 3 ve sonrası (varsa): Sonuç + emsal değeri (genç avukat ve vatandaş için ne anlama geliyor).

## ANAHTAR NOKTALAR
- {anahtar_sayisi} adet madde olarak en önemli noktaları yaz.
- Her madde tek cümle olsun.

## İLGİLİ KANUNLAR
- Kararda atıf yapılan kanun, madde ve içtihatları liste halinde yaz (örn. "TBK m. 49", "HMK m. 27", "Yargıtay 4. HD 2019/1234 E.").
- Yoksa "Belirtilmemiş" yaz.
"""


def _truncate_karar(metin: str) -> str:
    """Çok uzun kararları akıllıca kısaltır: başını ve sonunu korur."""
    if len(metin) <= MAX_KAYNAK_CHAR:
        return metin
    bas = metin[: TRUNCATE_LIMITI // 2]
    son = metin[-(TRUNCATE_LIMITI // 2):]
    return f"{bas}\n\n[... metin uzunluğu nedeniyle orta kısım atlandı ...]\n\n{son}"


def _parse_bolumler(cikti: str) -> Dict:
    """LLM çıktısını ÖZET / ANAHTAR NOKTALAR / İLGİLİ KANUNLAR bölümlerine ayırır."""
    ozet_text = ""
    anahtar: List[str] = []
    kanunlar: List[str] = []

    # Bölümleri başlıklara göre ayır
    parts = re.split(r"##\s*", cikti)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lower = part.lower()
        if lower.startswith("özet") or lower.startswith("ozet"):
            ozet_text = re.sub(r"^(özet|ozet)\s*\n?", "", part, flags=re.IGNORECASE).strip()
        elif lower.startswith("anahtar"):
            body = re.sub(r"^anahtar\s*noktalar\s*\n?", "", part, flags=re.IGNORECASE).strip()
            for line in body.splitlines():
                line = line.strip()
                if not line:
                    continue
                # "- madde" veya "* madde" veya "1. madde" formatlarını yakala
                m = re.match(r"^[-*•]\s*(.+)$", line)
                if not m:
                    m = re.match(r"^\d+[\.\)]\s*(.+)$", line)
                if m:
                    anahtar.append(m.group(1).strip())
                elif line and not line.startswith("#"):
                    anahtar.append(line)
        elif lower.startswith("ilgili") or lower.startswith("i̇lgili"):
            body = re.sub(r"^i̇?lgili\s*kanunlar\s*\n?", "", part, flags=re.IGNORECASE).strip()
            for line in body.splitlines():
                line = line.strip()
                if not line:
                    continue
                m = re.match(r"^[-*•]\s*(.+)$", line)
                if not m:
                    m = re.match(r"^\d+[\.\)]\s*(.+)$", line)
                if m:
                    kanunlar.append(m.group(1).strip())
                elif line and not line.startswith("#"):
                    kanunlar.append(line)

    # Hiçbir bölüm yakalanamadıysa, ham çıktıyı özet olarak kullan
    if not ozet_text and not anahtar and not kanunlar:
        ozet_text = cikti.strip()

    return {
        "ozet": ozet_text,
        "anahtar_noktalar": anahtar,
        "ilgili_kanunlar": kanunlar,
    }


def ozet_uret(karar_metni: str, uzunluk: str = "orta") -> dict:
    """
    Bir karar metninden sade Türkçe özet üretir.

    Args:
        karar_metni: Tam karar metni (ham metin)
        uzunluk: "kisa" (3 paragraf), "orta" (5 paragraf), "detayli" (7-10 paragraf)

    Returns:
        {
            "ozet": str,                     # markdown formatında özet
            "anahtar_noktalar": [str],       # madde madde anahtar noktalar
            "ilgili_kanunlar": [str],        # atıf yapılan kanun/madde/içtihat
            "model": str,                    # kullanılan LLM modeli/sağlayıcısı
            "kaynak_char_count": int,        # orijinal metin karakter sayısı
        }
    """
    if not karar_metni or not karar_metni.strip():
        return {
            "ozet": "",
            "anahtar_noktalar": [],
            "ilgili_kanunlar": [],
            "model": "yok",
            "kaynak_char_count": 0,
            "hata": "Karar metni boş.",
        }

    if generate is None:
        return {
            "ozet": "",
            "anahtar_noktalar": [],
            "ilgili_kanunlar": [],
            "model": "yok",
            "kaynak_char_count": len(karar_metni),
            "hata": "LLM provider yüklenemedi. llm/provider.py kontrol edin.",
        }

    profil = UZUNLUK_PROFILLERI.get(uzunluk, UZUNLUK_PROFILLERI["orta"])
    kaynak_char_count = len(karar_metni)
    kullanilan_metin = _truncate_karar(karar_metni)

    sistem_prompt = SISTEM_PROMPT_TEMPLATE.format(
        paragraf=profil["paragraf"],
        aciklama=profil["aciklama"],
        anahtar_sayisi=profil["anahtar_sayisi"],
    )

    kullanici_prompt = (
        "Aşağıdaki Türk mahkeme kararını sade Türkçe ile özetle. "
        "Çıktı formatına KESİNLİKLE uy (## ÖZET, ## ANAHTAR NOKTALAR, ## İLGİLİ KANUNLAR).\n\n"
        f"--- KARAR METNİ BAŞLANGIÇ ---\n{kullanilan_metin}\n--- KARAR METNİ SON ---"
    )

    try:
        sonuc = generate(
            system=sistem_prompt,
            user=kullanici_prompt,
            max_tokens=profil["max_tokens"],
            provider=None,
            temperature=0.2,
        )
    except TypeError:
        # Bazı provider'lar farklı imzaya sahip olabilir
        try:
            sonuc = generate(
                system=sistem_prompt,
                user=kullanici_prompt,
                max_tokens=profil["max_tokens"],
            )
        except Exception as e:
            return {
                "ozet": "",
                "anahtar_noktalar": [],
                "ilgili_kanunlar": [],
                "model": "hata",
                "kaynak_char_count": kaynak_char_count,
                "hata": f"LLM çağrısı başarısız: {e}",
            }
    except Exception as e:
        return {
            "ozet": "",
            "anahtar_noktalar": [],
            "ilgili_kanunlar": [],
            "model": "hata",
            "kaynak_char_count": kaynak_char_count,
            "hata": f"LLM çağrısı başarısız: {e}",
        }

    # generate() string veya dict döndürebilir
    if isinstance(sonuc, dict):
        ham_cikti = sonuc.get("text") or sonuc.get("content") or sonuc.get("output") or ""
        model_adi = sonuc.get("model", "bilinmiyor")
    else:
        ham_cikti = str(sonuc)
        model_adi = "llm.provider"

    bolumler = _parse_bolumler(ham_cikti)

    return {
        "ozet": bolumler["ozet"],
        "anahtar_noktalar": bolumler["anahtar_noktalar"],
        "ilgili_kanunlar": bolumler["ilgili_kanunlar"],
        "model": model_adi,
        "kaynak_char_count": kaynak_char_count,
        "uzunluk": uzunluk,
        "yasal_not": YASAL_NOT,
    }
