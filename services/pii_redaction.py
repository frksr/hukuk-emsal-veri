"""PII (Kişisel Veri) maskeleme + geri yükleme.

LLM'e gönderilen metinde kişisel veriler placeholder ile değiştirilir; yanıt
geldiğinde geri konur.

ÜÇ KATMANLI MASKELEME:
    1. Regex (her zaman): TCKN, IBAN, telefon, kredi kartı, e-posta, plaka gibi
       YAPISAL/FORMATLI veriler.
    2. Heuristik (her zaman): kural tabanlı Türkçe kişi adı + adres maskeleme.
       "Davacı/Davalı/Vekili/Av./Sayın <Ad Soyad>" gibi YÜKSEK GÜVENİLİRLİKLİ
       bağlamlar ve "<...> Mahallesi/Caddesi/Sokak", "No:12" gibi adres kalıpları.
       Model indirmeden çalışır → isim maskeleme varsayılan olarak AKTİFTİR.
    3. NER (opsiyonel, en geniş kapsam): PII_NER_MODEL ayarlıysa Türkçe bir NER
       modeli (ör. savasy/bert-base-turkish-ner-cased) ile PERSON/LOCATION/ORG
       varlıkları serbest metinde de yakalanır.

KVKK DÜRÜST SINIR:
    Heuristik katman yüksek precision'lı ama eksiksiz DEĞİLDİR (her ismi
    yakalamaz). En güçlü koruma için NER önerilir. `name_layer()` aktif en güçlü
    katmanı ("ner" | "heuristic") döndürür; `RedactionMap.names_redacted` ise o
    belge için gerçekten isim/adres maskelenip maskelenmediğini bildirir. Strict
    KVKK modunda (PII_BLOCK_FOREIGN_LLM_WITHOUT_NER=1) NER yoksa yurt dışı LLM
    çağrısı engellenir.
"""
from __future__ import annotations
import os
import re
import uuid
import logging
from typing import Pattern, Optional

log = logging.getLogger("services.pii_redaction")

# PII pattern'leri — sırası önemli (en spesifik önce)
PATTERNS: list[tuple[str, Pattern]] = [
    ("TCKN", re.compile(r"\b[1-9]\d{10}\b")),
    ("IBAN", re.compile(r"\bTR\d{2}\s?(?:\d{4}\s?){5}\d{2}\b")),
    ("PHONE", re.compile(
        r"\b(?:\+90[\s-]?|0)?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b"
    )),
    ("CREDIT_CARD", re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b")),
    # Adres parçaları (yaklaşık)
    ("PLATE", re.compile(r"\b\d{1,2}\s?[A-ZÇĞIİÖŞÜ]{1,3}\s?\d{1,4}\b")),
]

# NER ile maskelenecek varlık tipleri → placeholder etiketi
_NER_LABEL_MAP = {
    "PER": "PERSON", "PERSON": "PERSON",
    "LOC": "LOCATION", "LOCATION": "LOCATION", "GPE": "LOCATION",
    "ORG": "ORG", "ORGANIZATION": "ORG",
}

_NER_MODEL_NAME = os.environ.get("PII_NER_MODEL", "")  # ör. "savasy/bert-base-turkish-ner-cased"
_ner_pipeline = None            # lazy
_ner_load_failed = False

# --- Heuristik (kural tabanlı) isim + adres maskeleme ---
# Türkçe büyük harfle başlayan ad-soyad dizisi (1-3 kelime).
_TR_NAME = r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){1,2}"
# Kişiyi işaret eden roller (yüksek precision bağlam).
_PERSON_ROLE = (
    r"Davac[ıi](?:lar)?|Daval[ıi](?:lar)?|Vekil(?:i|leri)?|Müvekkil(?:i|im)?|"
    r"San[ıi]k|Müşteki|Mağdur|Borçlu|Alacakl[ıi]|Tan[ıi]k|Bilirkişi|"
    r"Sayın|Sn\.|Av\.|Avukat|Dr\.|Prof\."
)
# "Davacı Ahmet Yılmaz", "vekili Av. Mehmet Demir", "Sayın Ayşe Kaya"
# Rol kelimesi büyük/küçük harf DUYARSIZ ((?i:...)); isim kısmı Title-case zorunlu
# (yanlışlıkla küçük harfli kelimeleri isim sanmamak için).
_PERSON_CTX = re.compile(
    rf"(?P<role>(?i:{_PERSON_ROLE}))\s*:?\s*"
    rf"(?:(?i:Av\.|Avukat|Dr\.|Prof\.)\s+)?(?P<name>{_TR_NAME})"
)
# Adres birimleri: "Bağdat Caddesi", "Cumhuriyet Mah.", "Gül Sokak"
_ADDRESS_UNIT = re.compile(
    r"\b[A-ZÇĞİÖŞÜ][\wçğıöşü.]+\s+"
    r"(?:Mahallesi|Mah\.|Caddesi|Cad\.|Sokak|Sok\.|Sk\.|Bulvar[ıi]|Bulv\.)\b"
)
_ADDRESS_NO = re.compile(r"\bNo[:.]?\s*\d+[A-Za-z]?\b", re.IGNORECASE)
_ADDRESS_UNIT_NO = re.compile(r"\b(?:Daire|Kat|Blok|D)[:.]?\s*\d+\b", re.IGNORECASE)


def ner_available() -> bool:
    """En güçlü isim/adres (NER) katmanı kullanılabilir mi?"""
    return bool(_NER_MODEL_NAME) and not _ner_load_failed


def name_layer() -> str:
    """Aktif en güçlü isim-maskeleme katmanı: 'ner' veya 'heuristic'."""
    return "ner" if ner_available() else "heuristic"


def _get_ner():
    """NER pipeline'ını lazy yükle. Başarısız olursa None döner (regex'e düşeriz)."""
    global _ner_pipeline, _ner_load_failed
    if _ner_pipeline is not None or _ner_load_failed or not _NER_MODEL_NAME:
        return _ner_pipeline
    try:
        from transformers import pipeline  # type: ignore
        _ner_pipeline = pipeline(
            "token-classification",
            model=_NER_MODEL_NAME,
            aggregation_strategy="simple",
        )
        log.info("PII NER modeli yüklendi: %s", _NER_MODEL_NAME)
    except Exception as e:
        _ner_load_failed = True
        log.warning("PII NER modeli yüklenemedi (%s): %s — isim/adres maskelenmeyecek.",
                    _NER_MODEL_NAME, e)
    return _ner_pipeline


class RedactionMap:
    """Maskeleme ↔ orijinal değer haritası — geri yükleme için."""
    def __init__(self):
        self.forward: dict[str, str] = {}   # placeholder → original
        self.reverse: dict[str, str] = {}   # original → placeholder
        # İsim/adres (NER) katmanı bu redaksiyon için gerçekten çalıştı mı?
        self.names_redacted: bool = False

    def get_or_create(self, label: str, original: str) -> str:
        if original in self.reverse:
            return self.reverse[original]
        ph = f"<{label}_{uuid.uuid4().hex[:8]}>"
        self.forward[ph] = original
        self.reverse[original] = ph
        return ph


def _redact_heuristic(text: str, mapping: RedactionMap) -> str:
    """Model gerektirmeyen kural tabanlı kişi adı + adres maskeleme.

    Yüksek precision için isimleri yalnızca rol bağlamında (Davacı/Vekili/Av./...)
    yakalar; bu sayede 'Yargıtay', 'Mahkeme' gibi büyük harfli hukuk terimlerini
    yanlışlıkla maskelemez.
    """
    out = text

    # 1) Bağlamsal kişi adları — rol/ünvanı KORU, yalnızca ismi maskele.
    def _person(m: re.Match) -> str:
        name = m.group("name")
        ph = mapping.get_or_create("PERSON", name)
        mapping.names_redacted = True
        full = m.group(0)
        # İsmi tam olarak yerinde değiştir, geri kalan her şeyi (rol, ünvan,
        # boşluklar) aynen koru → unredact ile birebir geri yüklenebilir.
        ns = m.start("name") - m.start()
        ne = m.end("name") - m.start()
        return full[:ns] + ph + full[ne:]
    out = _PERSON_CTX.sub(_person, out)

    # 2) Adres birimleri ("X Caddesi", "Y Mahallesi" ...)
    def _addr(m: re.Match) -> str:
        mapping.names_redacted = True
        return mapping.get_or_create("ADDRESS", m.group(0))
    out = _ADDRESS_UNIT.sub(_addr, out)
    out = _ADDRESS_NO.sub(_addr, out)
    out = _ADDRESS_UNIT_NO.sub(_addr, out)

    return out


def _redact_with_ner(text: str, mapping: RedactionMap) -> str:
    """NER varlıklarını (kişi/yer/kurum) maskele. NER yoksa metni aynen döndürür."""
    ner = _get_ner()
    if ner is None:
        return text
    try:
        entities = ner(text)
    except Exception as e:
        log.warning("NER çıkarımı başarısız: %s", e)
        return text

    # Çakışmayı önlemek için sondan başa doğru değiştir.
    spans = []
    for ent in entities:
        grp = str(ent.get("entity_group") or ent.get("entity") or "").upper()
        label = _NER_LABEL_MAP.get(grp)
        if not label:
            continue
        start, end = ent.get("start"), ent.get("end")
        if start is None or end is None:
            continue
        word = text[start:end].strip()
        if len(word) < 2:
            continue
        spans.append((start, end, label, word))

    spans.sort(key=lambda s: s[0], reverse=True)
    out = text
    for start, end, label, word in spans:
        ph = mapping.get_or_create(label, word)
        out = out[:start] + ph + out[end:]
    if spans:
        mapping.names_redacted = True
    return out


def redact(text: str) -> tuple[str, RedactionMap]:
    """PII'leri maskele. (masked_text, map) döner.

    Önce (varsa) NER ile isim/yer/kurum, sonra regex ile yapısal PII maskelenir.

    Kullanım:
        masked, m = redact(user_text)
        if not m.names_redacted:
            # isim/adres maskelenmedi — yurt dışı LLM'e göndermeden önce karar ver
            ...
        llm_response = await llm.generate(masked)
        final = unredact(llm_response, m)
    """
    if not text:
        return text, RedactionMap()

    mapping = RedactionMap()
    out = text

    # 1) Heuristik (kural tabanlı isim/adres) — her zaman, ÖNCE.
    #    Güçlü bağlamsal kalıp ("Davacı Ad Soyad") tam ismi yakalar; böylece
    #    NER'in ismi parçalı yakalayıp ilk adı açıkta bırakması önlenir.
    out = _redact_heuristic(out, mapping)

    # 2) NER (en geniş kapsam) — varsa, kalan serbest varlıkları yakalar.
    out = _redact_with_ner(out, mapping)

    # 3) Regex (yapısal PII) — her zaman
    for label, pat in PATTERNS:
        def _sub(match: re.Match) -> str:
            return mapping.get_or_create(label, match.group(0))
        out = pat.sub(_sub, out)

    return out, mapping


def unredact(text: str, mapping: RedactionMap) -> str:
    """LLM yanıtındaki placeholder'ları orijinal değerlerle değiştir."""
    if not mapping.forward:
        return text
    result = text
    for ph, orig in mapping.forward.items():
        result = result.replace(ph, orig)
    return result


def audit_pii(text: str) -> dict:
    """Metinde hangi PII tipleri var? (KVKK audit için).

    NOT: Bu sayım yalnızca regex katmanını yansıtır; isim/adres tespiti için
    `ner_available()` True olmalıdır. `names_layer_active` bayrağı, isim/adres
    katmanının yapılandırılıp yapılandırılmadığını gösterir.
    """
    findings: dict[str, int] = {}
    for label, pat in PATTERNS:
        matches = pat.findall(text)
        if matches:
            findings[label.lower()] = len(matches)
    return {
        "contains_pii": bool(findings),
        "types": list(findings.keys()),
        "counts": findings,
        "total_matches": sum(findings.values()),
        # İsim/adres katmanı her zaman aktiftir (en az heuristik); 'name_layer'
        # aktif en güçlü katmanı bildirir.
        "names_layer_active": True,
        "name_layer": name_layer(),
    }
