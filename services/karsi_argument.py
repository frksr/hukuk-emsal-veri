"""Karşı Argüman Öngörü Servisi — "Şeytanın Avukatı" modu.

Kullanıcı kendi tezini anlatır, sistem:
  1. LLM ile tezin "anti-tez" formülasyonunu üretir (RAG sorgusu için).
  2. RAG ile bu anti-tez için emsal kararları çeker (services.rag.search).
  3. LLM ile karşı tarafın muhtemel argümanları + rebuttal listesi üretir.
  4. JSON parse + sağlam fallback ile dict döndürür.

Kullanım:
  from services.karsi_argument import karsi_argument_uret

  sonuc = karsi_argument_uret(
      kendi_tezi="Müvekkilim alacaklı, çek bedelini tahsil etmelidir.",
      dava_turu="itirazin_iptali",
  )
  for arg in sonuc["muhtemel_karsi_argumanlar"]:
      print(arg["arguman"], arg["guc_skoru"], arg["rebuttal"])
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from services.rag import search
from llm.provider import generate, is_available

log = logging.getLogger(__name__)

# Kullanıcıya gösterilecek genel mesaj — API key/env gibi iç mimari detaylar
# son kullanıcıya ASLA sızdırılmaz; gerçek sebep yalnızca sunucu loguna yazılır.
_KULLANICI_DEMO_MESAJI = (
    "Yapay Zeka analizi şu anda geçici olarak kullanılamıyor; aşağıda yalnızca "
    "ilgili emsal kararlar listelendi. Lütfen birkaç dakika sonra tekrar deneyin."
)


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

DAVA_TURU_LABEL: dict[str, str] = {
    "genel": "Genel Hukuki Uyuşmazlık",
    "itirazin_iptali": "İtirazın İptali Davası",
    "ihalenin_feshi": "İhalenin Feshi",
    "menfi_tespit": "Menfi Tespit Davası",
    "tahsilat": "Alacak / Tahsilat Davası",
    "is_hukuku": "İş Hukuku Uyuşmazlığı",
    "tazminat": "Tazminat Davası",
    "idari": "İdari Dava",
    "ceza": "Ceza Davası",
}


YASAL_UYARI = (
    "Bu çıktı, bir yapay zekâ öngörüsüdür. Karşı tarafın gerçek mahkeme "
    "sürecindeki tutumu, somut delillerle ve yargıcın takdiriyle "
    "değişebilir. Profesyonel hukuki görüş yerine geçmez."
)


SISTEM_PROMPT = """Sen bir Türk hukukunda "şeytanın avukatı" rolünde uzmansın.
Kullanıcının tezine karşı tarafın yapabileceği en güçlü argümanları sırala.

GÖREVİN:
1. Her argüman için ne diyeceğini açıkla (mantığı, hukuki dayanağı, içtihat referansı).
2. Argümanın gücünü 1-10 arası tam sayı ile değerlendir (10 = öldürücü argüman).
3. Kullanıcının bu argümanı nasıl çürütebileceğini (rebuttal) somut olarak öner.
4. Sağlanan emsallere atıfla bağ kur; uydurma esas/karar no ÜRETME.

KURALLAR:
- Resmî, ölçülü, hukuki Türkçe.
- Gerçekten karşı tarafın işine yarayacak en güçlü 3-6 argümana odaklan; doldurma yapma.
- Her argüman bağımsız ve uygulanabilir olmalı (sadece "iyi bir avukat olun" gibi değil).
- Çıktıyı SADECE aşağıdaki JSON formatında ver, başka açıklama EKLEME.

ÇIKTI FORMATI (kesinlikle uy):
{
  "muhtemel_karsi_argumanlar": [
    {
      "arguman": "Karşı tarafın iddia edeceği argümanın 2-4 cümlelik açıklaması.",
      "dayanak_emsal": ["EMSAL_1", "EMSAL_3"],
      "rebuttal": "Bu argümanı nasıl çürütebileceğinin 2-4 cümlelik önerisi.",
      "guc_skoru": 8
    }
  ],
  "ozet_uyari": "Kullanıcının en çok dikkat etmesi gereken zayıf noktanın 1-2 cümlelik özeti."
}

dayanak_emsal listesinde, sana verilen "EMSAL N" etiketlerini kullan
(N = 1..K). İlgisiz emsalleri eklemek YERİNE boş liste ver.
"""


ANTI_TEZ_SISTEM_PROMPT = """Sen, hukuki argümanları "anti-tez" formuna çeviren
bir Türk hukuk uzmanısın. Kullanıcının savunduğu teze KARŞI olan bakışı,
emsal kararlarda aranabilecek kısa bir arama sorgusu olarak yaz.

KURALLAR:
- Maksimum 20 kelime.
- Türkçe.
- "...kabul edilmemiştir", "...reddi", "...karşıt görüş", "...aksi yönde" gibi
  karşıt kalıplar kullan.
- Sadece sorgu metnini ver, başka açıklama yazma, tırnak ekleme.

ÖRNEK:
Tez: "Emekli maaşı haczedilemez."
Anti-tez sorgu: "emekli maaşı haczedilebilir nafaka borcu istisna kabul edilen"

Tez: "Çek bedeli tahsil edilmelidir."
Anti-tez sorgu: "çek bedeli tahsil edilemez karşılıksız çek itiraz kabul"
"""


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _emsal_etiket(meta: dict | None, chunk_id: str) -> dict[str, str]:
    """Bir emsal için karar_id / atif / kısa özet üret.

    services.rag.search() 'court_chamber'/'case_no'/'decision_no' döner
    (pgvector şeması); eski Türkçe anahtarlar (mahkeme/daire/esas_no/karar_no)
    yalnızca geriye dönük uyumluluk için fallback'te tutulur — bkz.
    api/routers/arama.py'deki aynı desen.
    """
    meta = meta or {}
    mahkeme_bilinmiyor = not (
        meta.get("court_chamber") or meta.get("mahkeme")
        or meta.get("daire") or meta.get("source") or meta.get("kaynak")
    )
    mahkeme = (
        meta.get("court_chamber")
        or meta.get("mahkeme")
        or meta.get("daire")
        or meta.get("source")
        or meta.get("kaynak")
        or "Mahkeme bilgisi yok"
    )
    esas = meta.get("case_no") or meta.get("esas_no") or meta.get("esas") or ""
    karar = meta.get("decision_no") or meta.get("karar_no") or meta.get("karar") or ""
    karar_id = (
        meta.get("decision_id")
        or meta.get("id")
        or chunk_id
        or ""
    )
    if mahkeme_bilinmiyor:
        # İyelik ekiyle bozuk bir cümle ("Mahkeme bilgisi yok'nin...") kurmak
        # yerine dilbilgisel olarak doğru, ayrı bir ifade kullanılır.
        atif = "İlgili yerleşik içtihat (mahkeme bilgisi mevcut değil)"
    elif esas and karar:
        atif = f"{mahkeme}'nin {esas} E., {karar} K. sayılı kararı"
    elif esas:
        atif = f"{mahkeme}'nin {esas} E. sayılı kararı"
    else:
        atif = f"{mahkeme}'nin yerleşik içtihadı"
    return {
        "karar_id": str(karar_id),
        "mahkeme": str(mahkeme),
        "atif": atif,
    }


def _emsal_blogu_hazirla(emsaller: list[dict]) -> str:
    """LLM prompt'una verilecek emsal kararların özet bloğu."""
    if not emsaller:
        return "(Sağlanan emsal karar yok — genel hukuki bilgiyle değerlendir.)"

    satirlar: list[str] = []
    for i, e in enumerate(emsaller, start=1):
        et = _emsal_etiket(e.get("meta"), e.get("chunk_id", ""))
        ozet = (e.get("text") or "").strip().replace("\n", " ")
        if len(ozet) > 700:
            ozet = ozet[:700] + "..."
        satirlar.append(
            f"[EMSAL {i}] (karar_id: {et['karar_id']})\n"
            f"  Atıf: {et['atif']}\n"
            f"  İlgili Bölüm:\n  \"\"\"{ozet}\"\"\""
        )
    return "\n\n".join(satirlar)


def _dayanak_emsaller_format(emsaller: list[dict]) -> list[dict]:
    """Dönüş yapısı için emsalleri sadeleştir."""
    out: list[dict] = []
    for e in emsaller:
        et = _emsal_etiket(e.get("meta"), e.get("chunk_id", ""))
        ozet = (e.get("text") or "").strip().replace("\n", " ")
        if len(ozet) > 500:
            ozet = ozet[:500] + "..."
        out.append({
            "karar_id": et["karar_id"],
            "ozet": ozet,
            "atif": et["atif"],
        })
    return out


def _emsal_etiket_to_karar_id(
    etiket_listesi: list[str],
    emsaller: list[dict],
) -> list[str]:
    """LLM'in döndürdüğü 'EMSAL 1', 'EMSAL 3' gibi etiketleri karar_id'ye çevir.

    Tanınmayan etiket varsa atla. Etiket yerine doğrudan karar_id geldiyse onu da
    kabul et.
    """
    karar_id_listesi: list[str] = []
    karar_id_set = {
        _emsal_etiket(e.get("meta"), e.get("chunk_id", ""))["karar_id"]
        for e in emsaller
    }
    for etiket in etiket_listesi:
        if not isinstance(etiket, str):
            continue
        s = etiket.strip()
        if not s:
            continue
        m = re.match(r"^EMSAL\s*(\d+)$", s, re.IGNORECASE)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(emsaller):
                et = _emsal_etiket(
                    emsaller[idx].get("meta"),
                    emsaller[idx].get("chunk_id", ""),
                )
                karar_id_listesi.append(et["karar_id"])
            continue
        # Doğrudan karar_id verdiyse kabul et.
        if s in karar_id_set:
            karar_id_listesi.append(s)
    return karar_id_listesi


def _json_extract(metin: str) -> dict | None:
    """LLM çıktısından JSON'u çıkar (kod bloğu fence'leri vs. tolere et)."""
    if not metin:
        return None
    metin = metin.strip()
    # ```json ... ``` veya ``` ... ``` bloğu varsa içeriği al.
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", metin, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # İlk { ile son } arası dene.
    ilk = metin.find("{")
    son = metin.rfind("}")
    if ilk != -1 and son != -1 and son > ilk:
        try:
            return json.loads(metin[ilk:son + 1])
        except Exception:
            pass
    try:
        return json.loads(metin)
    except Exception:
        return None


def _coerce_int(value: Any, default: int = 5) -> int:
    """guc_skoru için: int'e zorla, 1-10 aralığına kıs."""
    try:
        v = int(value)
    except Exception:
        try:
            v = int(float(value))
        except Exception:
            return default
    return max(1, min(10, v))


def _normalize_argumanlar(
    veri: dict,
    emsaller: list[dict],
) -> list[dict]:
    """LLM JSON'undaki argüman listesini şema'ya uyumla."""
    ham_liste = veri.get("muhtemel_karsi_argumanlar")
    if not isinstance(ham_liste, list):
        return []

    sonuc: list[dict] = []
    for item in ham_liste:
        if not isinstance(item, dict):
            continue
        arguman = (item.get("arguman") or "").strip()
        rebuttal = (item.get("rebuttal") or "").strip()
        if not arguman:
            continue
        dayanak_raw = item.get("dayanak_emsal") or []
        if not isinstance(dayanak_raw, list):
            dayanak_raw = [str(dayanak_raw)]
        dayanak_ids = _emsal_etiket_to_karar_id(dayanak_raw, emsaller)
        guc = _coerce_int(item.get("guc_skoru"), default=5)
        sonuc.append({
            "arguman": arguman,
            "dayanak_emsal": dayanak_ids,
            "rebuttal": rebuttal or "(Rebuttal önerilmedi.)",
            "guc_skoru": guc,
        })
    return sonuc


# ---------------------------------------------------------------------------
# 1) Anti-tez sorgusu üret
# ---------------------------------------------------------------------------

def _basit_anti_tez(kendi_tezi: str) -> str:
    """LLM yokken kullanılacak heuristic anti-tez sorgusu."""
    # Çok basit: tezdeki ana isimleri al, başına "reddi karşıt" ekle.
    temiz = re.sub(r"[^\w\sğüşıöçĞÜŞİÖÇ]+", " ", kendi_tezi or "", flags=re.UNICODE)
    kelimeler = [k for k in temiz.split() if len(k) > 3]
    ana = " ".join(kelimeler[:10]) if kelimeler else kendi_tezi
    return f"{ana} reddi kabul edilmemiştir karşıt görüş"


def _anti_tez_query_uret(kendi_tezi: str) -> tuple[str, str]:
    """LLM ile anti-tez sorgusu üret. (query, hata) döner."""
    if not is_available():
        return _basit_anti_tez(kendi_tezi), ""

    try:
        sorgu = generate(
            system=ANTI_TEZ_SISTEM_PROMPT,
            user=f"Tez:\n\"\"\"\n{kendi_tezi.strip()}\n\"\"\"\n\nAnti-tez sorgu:",
            max_tokens=120,
            temperature=0.4,
        )
    except Exception as e:
        log.warning(f"Anti-tez LLM hatası, basit fallback kullanılıyor: {e}")
        return _basit_anti_tez(kendi_tezi), ""

    sorgu = (sorgu or "").strip().strip('"').strip("'")
    # Tek satırlık olduğundan emin ol.
    sorgu = sorgu.splitlines()[0].strip() if sorgu else ""
    if not sorgu:
        return _basit_anti_tez(kendi_tezi), ""
    return sorgu, ""


# ---------------------------------------------------------------------------
# 2) LLM ile karşı argümanlar
# ---------------------------------------------------------------------------

def _stub_argumanlar(
    kendi_tezi: str,
    emsaller: list[dict],
) -> dict:
    """LLM yokken kullanılacak basit iskelet sonuç.

    NOT: Bu içerik doğrudan kullanıcıya gösterilir — iç mimari/altyapı
    detayı (API key, .env vb.) İÇERMEMELİDİR; kullanıcıyı ilgilendirmez.
    """
    karar_ids = [
        _emsal_etiket(e.get("meta"), e.get("chunk_id", ""))["karar_id"]
        for e in emsaller[:2]
    ]
    return {
        "muhtemel_karsi_argumanlar": [
            {
                "arguman": (
                    "Karşı argüman analizi şu anda geçici olarak kullanılamıyor. "
                    "Yine de ilgili emsaller aşağıda listelendi — bunları "
                    "inceleyerek karşı tarafın muhtemel argümanlarını manuel "
                    "değerlendirebilirsiniz."
                ),
                "dayanak_emsal": karar_ids,
                "rebuttal": "Lütfen birkaç dakika sonra tekrar deneyin.",
                "guc_skoru": 5,
            }
        ],
        "ozet_uyari": _KULLANICI_DEMO_MESAJI,
    }


def _llm_argumanlar_uret(
    kendi_tezi: str,
    dava_turu_label: str,
    anti_tez_query: str,
    emsaller: list[dict],
) -> tuple[dict, str]:
    """LLM çağrısı + JSON parse. (parsed_dict, hata) döner."""
    emsal_blogu = _emsal_blogu_hazirla(emsaller)
    user_prompt = f"""DAVA TÜRÜ: {dava_turu_label}

KULLANICININ TEZİ:
\"\"\"
{kendi_tezi.strip()}
\"\"\"

ANTİ-TEZ ARAMA SORGUSU (karşı tarafın penceresi):
\"\"\"
{anti_tez_query}
\"\"\"

İLGİLİ EMSAL KARARLAR (RAG ile karşıt sorguya göre çekildi):
{emsal_blogu}

GÖREV:
Yukarıdaki tez için karşı tarafın yapabileceği en güçlü 3-6 argümanı sırala.
Her argüman için açıklama, dayanak emsal etiketleri (EMSAL 1..N), güç skoru
(1-10) ve kullanıcının nasıl çürütebileceğine dair rebuttal öner.
SADECE belirtilen JSON formatında çıktı ver.
"""

    try:
        ham = generate(
            system=SISTEM_PROMPT,
            user=user_prompt,
            max_tokens=2500,
            temperature=0.35,
        )
    except Exception as e:
        return {}, f"LLM çağrısı başarısız: {e}"

    parsed = _json_extract(ham)
    if not parsed or not isinstance(parsed, dict):
        return {}, "LLM çıktısı JSON olarak parse edilemedi."
    return parsed, ""


# ---------------------------------------------------------------------------
# Ana giriş noktası
# ---------------------------------------------------------------------------

def karsi_argument_uret(
    kendi_tezi: str,
    dava_turu: str | None = None,
    *,
    k: int = 5,
) -> dict:
    """Kullanıcının tezine karşı argümanları + rebuttal listesi üret.

    Args:
        kendi_tezi: Kullanıcının savunduğu tez (serbest metin).
        dava_turu: DAVA_TURU_LABEL anahtarlarından biri (None ise "genel").
        k: RAG için top-k emsal sayısı.

    Returns:
        {
            "kendi_tezi": str,
            "anti_tez_query": str,
            "muhtemel_karsi_argumanlar": [
                {"arguman": str, "dayanak_emsal": [karar_id],
                 "rebuttal": str, "guc_skoru": int},
                ...
            ],
            "ozet_uyari": str,
            "dayanak_emsaller": [
                {"karar_id": str, "ozet": str, "atif": str}, ...
            ],
            "uyari": str,   # işlem sırasında oluşan ek uyarı/hata (opsiyonel)
            "yasal_uyari": str,
            "demo_modu": bool,
        }
    """
    kendi_tezi = (kendi_tezi or "").strip()
    if not kendi_tezi:
        return {
            "kendi_tezi": "",
            "anti_tez_query": "",
            "muhtemel_karsi_argumanlar": [],
            "ozet_uyari": "Tez metni boş — karşı argüman üretilemedi.",
            "dayanak_emsaller": [],
            "uyari": "Tez metni boş.",
            "yasal_uyari": YASAL_UYARI,
            "demo_modu": not is_available(),
        }

    if dava_turu not in DAVA_TURU_LABEL:
        dava_turu = "genel"
    dava_turu_label = DAVA_TURU_LABEL[dava_turu]

    uyari_parcalari: list[str] = []

    # 1) Anti-tez sorgusu üret.
    anti_tez_query, at_hata = _anti_tez_query_uret(kendi_tezi)
    if at_hata:
        uyari_parcalari.append(at_hata)

    # 2) RAG araması (anti-tez sorgusuyla).
    try:
        emsaller = search(anti_tez_query, k=k)
    except Exception as e:
        emsaller = []
        log.warning(f"Karşı argüman için RAG araması başarısız: {e}")

    dayanak_emsaller = _dayanak_emsaller_format(emsaller)

    # 3) LLM ile argümanları üret.
    demo_modu = not is_available()
    if demo_modu:
        # Prod'da bu, ANTHROPIC_API_KEY/GOOGLE_API_KEY yapılandırma hatası
        # anlamına gelir — ops/Sentry görsün diye logla; kullanıcıya iç
        # mimari detay (env değişkeni adı) asla gösterilmez, onu ilgilendirmez.
        log.error(
            "Karşı argüman üretimi DEMO MODUNA düştü: LLM API key yok "
            "(ANTHROPIC_API_KEY / GOOGLE_API_KEY)."
        )
        parsed = _stub_argumanlar(kendi_tezi, emsaller)
        uyari_parcalari.append(_KULLANICI_DEMO_MESAJI)
    else:
        parsed, llm_hata = _llm_argumanlar_uret(
            kendi_tezi, dava_turu_label, anti_tez_query, emsaller,
        )
        if llm_hata:
            # LLM çağrısı patladı / parse edilemedi → stub'a dön. Teknik
            # detay yalnızca loglanır, kullanıcıya genel mesaj gösterilir.
            log.error(f"Karşı argüman LLM çağrısı başarısız: {llm_hata}")
            uyari_parcalari.append(_KULLANICI_DEMO_MESAJI)
            parsed = _stub_argumanlar(kendi_tezi, emsaller)
            demo_modu = True  # kullanıcı UI'da görsün

    argumanlar = _normalize_argumanlar(parsed, emsaller)
    if not argumanlar:
        # Fallback: en azından bir placeholder ver, UI boş kalmasın.
        argumanlar = [{
            "arguman": (
                "Karşı argüman üretilemedi. LLM çıktısı geçersiz veya boş "
                "geldi. Lütfen tezi daha somut yeniden ifade edip tekrar "
                "deneyin."
            ),
            "dayanak_emsal": [d["karar_id"] for d in dayanak_emsaller[:2]],
            "rebuttal": "—",
            "guc_skoru": 1,
        }]

    ozet_uyari = (parsed.get("ozet_uyari") or "").strip() or (
        "Tezin en zayıf noktası için ayrıca somut delil ve tanık planlaması "
        "yapılması önerilir."
    )

    uyari_str = " | ".join([u for u in uyari_parcalari if u])

    return {
        "kendi_tezi": kendi_tezi,
        "anti_tez_query": anti_tez_query,
        "muhtemel_karsi_argumanlar": argumanlar,
        "ozet_uyari": ozet_uyari,
        "dayanak_emsaller": dayanak_emsaller,
        "uyari": uyari_str,
        "yasal_uyari": YASAL_UYARI,
        "demo_modu": demo_modu,
    }
