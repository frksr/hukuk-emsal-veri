"""Hukuki Belge Denetleyici — dilekçe/ihtarname/sözleşme/genel belge için AI denetim.

Yapılan kontroller:
- Yasal dayanak (kanun madde referansları doğru mu, eksik mi)
- Emsal uyumluluk (Yargıtay/Danıştay içtihatlarına aykırı argüman var mı, RAG ile)
- Yapı kontrolü (zorunlu bölümler eksik mi: davacı, davalı, konu, açıklamalar, sonuç-istem)
- Tutarlılık (esas no / tarih / taraf bilgileri self-consistent mi)
- Üslup ve hukuki dil
- Risk skoru ve madde madde öneri
"""
from __future__ import annotations
import json
import re
from typing import Literal

from services.rag import search as rag_search

try:
    from llm.provider import generate, is_available
    _LLM = True
except Exception:
    _LLM = False
    def is_available(*a, **k): return False  # type: ignore

BelgeTuru = Literal["dilekce", "ihtarname", "sozlesme", "dava_dilekce", "cevap_dilekce", "genel"]

SISTEM_PROMPT = """Sen Türk hukukunda 25 yıl deneyimli kıdemli bir avukatsın.
Görevin: Kullanıcının yüklediği/yapıştırdığı hukuki belgeyi titizlikle DENETLEMEK.

DENETİM KRİTERLERİ:
1. **Yasal Dayanak**: Kanun maddesi referansları doğru mu? (TBK, TTK, İİK, HMK, VUK, AATUHK, KVKK)
   - "İİK 67" mi yoksa "İİK 67/1" mı belirsiz mi?
   - Yanlış kanun numarası var mı?
   - Eksik kritik referans var mı?
2. **Emsal Uyumluluk**: Kullanıcıya verilen emsal kararlara aykırı argüman var mı?
3. **Yapı Kontrolü**: Belge tipine göre zorunlu bölümler eksik mi?
   - Dilekçe: davacı, davalı, konu, açıklamalar, hukuki nedenler, deliller, sonuç-istem
   - İhtarname: alacaklı, borçlu, konu, ihtar süresi, ödeme talebi
   - Sözleşme: taraflar, konu, süre, fesih, cezai şart, uyuşmazlık çözümü
4. **Tutarlılık**: Esas no, karar no, tarih, taraf isimleri belge boyunca tutarlı mı?
5. **Üslup**: Mahkeme diline uygun mu? Argo, belirsizlik, yazım hatası var mı?
6. **Risk**: Karşı tarafın bu belgede yakalayabileceği zayıflık var mı?

Cevabını KESİNLİKLE şu JSON şemasına göre ver:

```json
{
  "genel_risk_skoru": 0-100,
  "ozet": "2-3 cümle genel değerlendirme",
  "kritik_sorunlar": ["..."],
  "uyarilar": [
    {
      "kategori": "yasal_dayanak|yapi|tutarlilik|emsal|uslup|risk",
      "ciddiyet": "yuksek|orta|dusuk",
      "ilgili_bolum": "metinden alıntı (max 200 char)",
      "sorun": "ne sorunlu",
      "oneri": "nasıl düzeltilmeli"
    }
  ],
  "eksik_bolumler": ["zorunlu ama eksik bölüm/madde"],
  "emsal_uyumsuzluk": [
    {"karar_id": "EMSAL_1", "neden": "açıklama"}
  ],
  "guclu_yonler": ["belgenin iyi yönleri"]
}
```

Sadece JSON döndür, başka açıklama yapma."""


def _belge_tipine_gore_kontroller(tur: BelgeTuru) -> list[str]:
    base = {
        "dilekce": ["mahkeme başlığı", "davacı/davalı bilgisi", "konu", "açıklamalar", "hukuki nedenler", "sonuç ve istem", "tarih/imza"],
        "dava_dilekce": ["mahkeme", "davacı vekili", "davalı", "konu", "harç", "açıklamalar", "hukuki nedenler", "deliller", "sonuç ve istem"],
        "cevap_dilekce": ["mahkeme", "esas no", "davalı/cevap veren", "süresi içinde itirazlar", "esas hakkında cevap", "sonuç ve istem"],
        "ihtarname": ["alacaklı", "borçlu", "konu", "açıklamalar", "ihtar süresi (3/7/15/30 gün)", "ödeme talebi", "tarih"],
        "sozlesme": ["taraflar", "konu", "süre", "ücret/bedel", "fesih", "cezai şart", "uyuşmazlık çözümü", "tebligat", "imza"],
        "genel": ["başlık", "taraflar", "konu", "tarih"],
    }
    return base.get(tur, base["genel"])


def _kanun_referans_check(text: str) -> list[dict]:
    """Belirgin kanun referans hatalarını regex ile tespit et."""
    issues = []
    # Belirsiz madde no (örn "İİK 67" — fıkra belirsiz olabilir)
    matches = re.findall(r"\b(TBK|TTK|İİK|HMK|VUK|AATUHK|KVKK|TMK)\s+(\d+)(?:/(\d+))?", text)
    for kanun, madde, fikra in matches:
        # En sık fıkra gerektiren maddeler
        if kanun == "İİK" and madde in ("67", "68", "89", "134") and not fikra:
            issues.append({
                "kategori": "yasal_dayanak",
                "ciddiyet": "dusuk",
                "ilgili_bolum": f"{kanun} {madde}",
                "sorun": f"{kanun} {madde} maddesinin alt fıkrası belirtilmemiş",
                "oneri": f"Atfı somutlaştırın: {kanun} {madde}/1 veya {madde}/2",
            })
    return issues


def _yapi_check(text: str, tur: BelgeTuru) -> list[str]:
    """Belirli anahtar kelimelerin varlığını kontrol et."""
    text_lower = text.lower()
    eksikler = []
    kontroller = _belge_tipine_gore_kontroller(tur)
    # Kabaca: kontrol başlığı/varyantı belgede geçiyor mu?
    keywords_map = {
        "davacı": ["davacı", "davaci"],
        "davalı": ["davalı", "davali"],
        "konu": ["konu:", "konu :"],
        "sonuç": ["sonuç", "sonuc", "talep", "istem"],
        "açıklamalar": ["açıklama", "aciklama"],
        "hukuki nedenler": ["hukuki neden", "hukuki sebep", "yasal dayanak"],
        "deliller": ["delil"],
        "alacaklı": ["alacaklı", "alacakli", "ihtar eden"],
        "borçlu": ["borçlu", "borclu", "muhatap"],
        "ihtar süresi": [" gün içinde", " gün içerisinde"],
        "ödeme": ["ödeme", "odeme", "tediye"],
        "taraflar": ["taraf"],
        "süre": ["süre", "sure"],
        "fesih": ["fesih"],
        "cezai şart": ["cezai şart", "cezai sart"],
        "uyuşmazlık": ["uyuşmazlık", "uyusmazlik", "yetkili mahkeme"],
        "imza": ["imza", "imzala"],
    }
    for k in kontroller:
        kwords = keywords_map.get(k.split(" ")[0].lower(), [k.lower()])
        if not any(kw in text_lower for kw in kwords):
            eksikler.append(k)
    return eksikler


def _llm_denetim(metin: str, tur: BelgeTuru, emsaller: list[dict]) -> dict:
    """LLM ile derinlemesine denetim."""
    if not is_available():
        return _stub_denetim(metin, tur, emsaller)

    emsal_block = ""
    for i, e in enumerate(emsaller[:5], 1):
        m = e.get("meta", {}) or {}
        emsal_block += (
            f"EMSAL_{i}: {m.get('court_chamber','?')} · "
            f"E.{m.get('case_no','?')}/K.{m.get('decision_no','?')} · "
            f"{m.get('decision_date','?')}\n"
            f"  {e.get('text','')[:300]}\n\n"
        )

    user_prompt = f"""DENETLENECEK BELGE TÜRÜ: {tur}

BELGE METNİ:
{metin[:8000]}

İLGİLİ EMSAL KARARLAR (RAG ile bulundu):
{emsal_block or '(emsal yok)'}

Yukarıdaki belgeyi sistem talimatındaki kriterlere göre denetle ve JSON formatında sonuç ver."""

    try:
        out = generate(
            system=SISTEM_PROMPT,
            user=user_prompt,
            max_tokens=2500,
            temperature=0.2,
        )
        # JSON parse — code block toleranslı
        m = re.search(r"```json\s*(\{.*?\})\s*```", out, re.DOTALL)
        if m:
            out = m.group(1)
        else:
            m = re.search(r"(\{.*\})", out, re.DOTALL)
            if m:
                out = m.group(1)
        return json.loads(out)
    except Exception as e:
        return {
            "genel_risk_skoru": 50,
            "ozet": "LLM analizi başarısız oldu, statik kontroller döndürülüyor.",
            "kritik_sorunlar": [],
            "uyarilar": [],
            "eksik_bolumler": [],
            "emsal_uyumsuzluk": [],
            "guclu_yonler": [],
            "hata": str(e)[:200],
        }


def _stub_denetim(metin: str, tur: BelgeTuru, emsaller: list[dict]) -> dict:
    return {
        "genel_risk_skoru": 50,
        "ozet": "LLM erişimi yok. Sadece statik kontroller yapıldı.",
        "kritik_sorunlar": [],
        "uyarilar": [],
        "eksik_bolumler": [],
        "emsal_uyumsuzluk": [],
        "guclu_yonler": [],
        "demo_modu": True,
    }


def denetle(metin: str, tur: BelgeTuru = "dilekce", k: int = 5) -> dict:
    """Ana giriş: belgeyi denetle ve kapsamlı rapor döndür."""
    if not metin or len(metin) < 50:
        return {
            "hata": "Belge çok kısa (en az 50 karakter gerekli)",
            "uyarilar": [],
            "eksik_bolumler": [],
            "genel_risk_skoru": 0,
        }

    # 1) Statik kontroller
    kanun_uyarilari = _kanun_referans_check(metin)
    yapi_eksikler = _yapi_check(metin, tur)

    # 2) RAG ile emsal bul
    try:
        # Belgeden anahtar cümle çıkar — ilk 500 char arama için
        query = metin[:500]
        emsaller = rag_search(query, k=k)
    except Exception:
        emsaller = []

    # 3) LLM ile derinlemesine analiz
    llm_sonuc = _llm_denetim(metin, tur, emsaller)

    # Birleştir
    uyarilar = list(llm_sonuc.get("uyarilar") or [])
    uyarilar = kanun_uyarilari + uyarilar

    eksik_bolumler = list(llm_sonuc.get("eksik_bolumler") or [])
    # Statik tespit edilenleri ekle (deduplicate)
    for ek in yapi_eksikler:
        if ek not in eksik_bolumler:
            eksik_bolumler.append(ek)

    # Kullanılan emsallerin özetlerini ekle
    dayanak_emsaller = []
    for e in emsaller[:5]:
        m = e.get("meta", {}) or {}
        dayanak_emsaller.append({
            "karar_id": m.get("decision_id", ""),
            "atif": f"{m.get('court_chamber','?')} - E.{m.get('case_no','?')}/K.{m.get('decision_no','?')}",
            "ozet": (e.get("text", "") or "")[:300],
            "tarih": m.get("decision_date", ""),
        })

    return {
        "belge_turu": tur,
        "metin_uzunluk": len(metin),
        "genel_risk_skoru": int(llm_sonuc.get("genel_risk_skoru", 50)),
        "ozet": llm_sonuc.get("ozet", ""),
        "kritik_sorunlar": llm_sonuc.get("kritik_sorunlar") or [],
        "uyarilar": uyarilar,
        "eksik_bolumler": eksik_bolumler,
        "emsal_uyumsuzluk": llm_sonuc.get("emsal_uyumsuzluk") or [],
        "guclu_yonler": llm_sonuc.get("guclu_yonler") or [],
        "dayanak_emsaller": dayanak_emsaller,
        "demo_modu": llm_sonuc.get("demo_modu", False),
        "yasal_uyari": "Bu AI denetimi, bir avukatın profesyonel incelemesinin yerine geçmez.",
    }
