"""PII (Kişisel Veri) maskeleme + geri yükleme.

LLM'e gönderilen metinde kişisel veriler placeholder ile değiştirilir; yanıt
geldiğinde geri konur.

KAPSAM ve DÜRÜST SINIRLAR (önemli — KVKK uyumu için):
    * Regex katmanı (her zaman aktif): TCKN, IBAN, telefon, kredi kartı, e-posta,
      plaka gibi YAPISAL/FORMATLI verileri yakalar.
    * Regex TEK BAŞINA kişi adlarını, taraf/vekil isimlerini, açık adres
      metinlerini, kurum adlarını YAKALAYAMAZ. Bunlar için isim varlık tanıma
      (NER) gerekir.
    * NER katmanı (opsiyonel): PII_NER_MODEL env'i ayarlıysa Türkçe bir NER
      modeli (ör. BERTurk-NER) ile PERSON / LOCATION / ORGANIZATION varlıkları da
      maskelenir. Model yoksa bu katman DEVRE DIŞIDIR.

    Bu yüzden: NER kapalıyken "LLM hiçbir kişisel veri görmez / KVKK m.9 (yurt
    dışı aktarım) ihlali oluşmaz" iddiası DOĞRU DEĞİLDİR — isimler/adresler yurt
    dışı LLM sağlayıcısına (Anthropic/Google) gidebilir. Üretimde ya NER açılmalı
    ya da yurt içinde barındırılan bir model kullanılmalı ya da kullanıcıdan açık
    rıza/aydınlatma alınmalıdır. `redact()` dönüşündeki RedactionMap.names_redacted
    bayrağı, isim katmanının gerçekten çalışıp çalışmadığını bildirir; çağıran
    katman buna göre karar vermelidir (örn. NER yoksa yurt dışı LLM'e göndermeyi
    reddet).
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


def ner_available() -> bool:
    """İsim/adres (NER) katmanı kullanılabilir mi?"""
    return bool(_NER_MODEL_NAME) and not _ner_load_failed


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

    # 1) NER (isim/adres) — opsiyonel
    out = _redact_with_ner(out, mapping)

    # 2) Regex (yapısal PII) — her zaman
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
        "names_layer_active": ner_available(),
    }
