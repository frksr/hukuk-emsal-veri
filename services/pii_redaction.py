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

# PLATE regex'inin mahkeme/daire atıflarıyla ("12 HD 2021", "3 CD 456") çakışmasını
# önlemek için: harf grubu bilinen bir yargı kısaltmasıysa plaka DEĞİLDİR.
_PLATE_HARIC = {"HD", "CD", "HGK", "CGK", "İBK", "IBK", "BİM", "BIM", "BAM", "AYM", "D", "E", "K"}
_PLATE_PARCALA = re.compile(r"\d{1,2}\s?([A-ZÇĞIİÖŞÜ]{1,3})\s?\d{1,4}")


def _plaka_mi(eslesme: str) -> bool:
    """Eşleşme gerçek bir plaka mı, yoksa yargı atfı mı? (kalite koruması)."""
    m = _PLATE_PARCALA.search(eslesme)
    if not m:
        return True
    return m.group(1).upper() not in _PLATE_HARIC

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
# NOT: kelimeler arası [ \t] — \s KULLANMA: satır sonunu aşan eşleşme, bir
# sonraki satırın rol kelimesini ("Davalı") isme dahil edip o satırdaki asıl
# ismi MASKESİZ bırakıyordu (sızıntı testiyle yakalandı).
_TR_NAME = r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:[ \t]+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){1,2}"
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


# NER modelleri (~512 token) uzun metni sessizce keser → uzun UYAP belgelerinde
# sonraki sayfalar maskesiz kalırdı. Metin örtüşmeli pencerelere bölünüp her
# pencere ayrı işlenir; span ofsetleri global konuma çevrilir.
_NER_PENCERE = int(os.environ.get("PII_NER_WINDOW_CHARS", "1500"))
_NER_ORTUSME = int(os.environ.get("PII_NER_OVERLAP_CHARS", "200"))


def _redact_with_ner(text: str, mapping: RedactionMap) -> str:
    """NER varlıklarını (kişi/yer/kurum) maskele. NER yoksa metni aynen döndürür.

    Uzun metinler örtüşmeli pencerelerle işlenir (512-token kesme sorunu).
    """
    ner = _get_ner()
    if ner is None:
        return text

    # Pencereleri hazırla: (global_offset, parça)
    pencereler: list[tuple[int, str]] = []
    if len(text) <= _NER_PENCERE:
        pencereler.append((0, text))
    else:
        adim = max(_NER_PENCERE - _NER_ORTUSME, 1)
        i = 0
        while i < len(text):
            pencereler.append((i, text[i:i + _NER_PENCERE]))
            i += adim

    spans: list[tuple[int, int, str, str]] = []
    gorulen: set[tuple[int, int]] = set()  # örtüşme bölgesindeki mükerrer span'lar
    for offset, parca in pencereler:
        try:
            entities = ner(parca)
        except Exception as e:
            log.warning("NER çıkarımı başarısız (pencere %d): %s", offset, e)
            continue
        for ent in entities:
            grp = str(ent.get("entity_group") or ent.get("entity") or "").upper()
            label = _NER_LABEL_MAP.get(grp)
            if not label:
                continue
            start, end = ent.get("start"), ent.get("end")
            if start is None or end is None:
                continue
            g_start, g_end = offset + start, offset + end
            if (g_start, g_end) in gorulen:
                continue
            gorulen.add((g_start, g_end))
            word = text[g_start:g_end].strip()
            if len(word) < 2:
                continue
            spans.append((g_start, g_end, label, word))

    # Çakışan span'ları ele (uzun olan kazanır), sondan başa uygula.
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    secili: list[tuple[int, int, str, str]] = []
    son_bitis = -1
    for s in spans:
        if s[0] >= son_bitis:
            secili.append(s)
            son_bitis = s[1]

    out = text
    for start, end, label, word in reversed(secili):
        ph = mapping.get_or_create(label, word)
        out = out[:start] + ph + out[end:]
    if secili:
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
        def _sub(match: re.Match, _label: str = label) -> str:
            # Yargı atıflarını ("12 HD 2021") plaka sanma — kalite koruması.
            if _label == "PLATE" and not _plaka_mi(match.group(0)):
                return match.group(0)
            return mapping.get_or_create(_label, match.group(0))
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


# Placeholder biçimi: <LABEL_hex8>. LLM bazen biçimi bozar (kalın, boşluk,
# &lt;/&gt; kaçışı) — toleranslı kalıplar bunlar için.
_PH_KESIN = re.compile(r"<([A-Z_]+)_([0-9a-f]{8})>")
_PH_TOLERANSLI = re.compile(
    r"(?:<|&lt;)\s*\**\s*([A-Z_]+)\s*_\s*([0-9a-f]{8})\s*\**\s*(?:>|&gt;)"
)


def unredact_safe(text: str, mapping: RedactionMap) -> str:
    """Dayanıklı geri yükleme:

    1. Birebir değiştirme (hızlı yol).
    2. LLM'in biçimini bozduğu placeholder'ları toleranslı kalıpla yakala,
       hex kimliğinden orijinali bul.
    3. Hâlâ çözülemeyen placeholder kaldıysa kullanıcıya SIZDIRMA —
       "[gizlenmiş bilgi]" ile değiştir ve logla.
    """
    result = unredact(text, mapping)
    if not mapping.forward:
        return result

    # Hex kimliği → orijinal (etiketten bağımsız arama için)
    hex_map = {}
    for ph, orig in mapping.forward.items():
        m = _PH_KESIN.fullmatch(ph)
        if m:
            hex_map[m.group(2)] = orig

    def _tolerant(m: re.Match) -> str:
        orig = hex_map.get(m.group(2))
        return orig if orig is not None else m.group(0)

    result = _PH_TOLERANSLI.sub(_tolerant, result)

    # Son süpürme: çözülemeyen placeholder kalmasın.
    kalan = _PH_TOLERANSLI.findall(result)
    if kalan:
        log.warning("unredact_safe: %d çözülemeyen placeholder '[gizlenmiş bilgi]' ile değiştirildi.", len(kalan))
        result = _PH_TOLERANSLI.sub("[gizlenmiş bilgi]", result)
    return result


# Embedding'e giden metin için jenerik etiketler — geri yükleme GEREKMEZ,
# rastgele hex yerine kararlı token'lar semantik gürültüyü azaltır.
_EMBED_ETIKET = {
    "PERSON": "[KİŞİ]", "LOCATION": "[YER]", "ORG": "[KURUM]",
    "ADDRESS": "[ADRES]", "TCKN": "[TCKN]", "IBAN": "[IBAN]",
    "PHONE": "[TELEFON]", "CREDIT_CARD": "[KART]", "EMAIL": "[EPOSTA]",
    "PLATE": "[PLAKA]",
}


def redact_for_embedding(text: str) -> str:
    """Dış embedding API'sine gönderilecek metni anonimleştir.

    redact() ile aynı üç katmanı kullanır; placeholder'lar geri-yüklemesiz
    jenerik etiketlere ([KİŞİ], [TCKN] ...) indirgenir. KVKK garantisi:
    tenant belgeleri ve sorgular embedding sağlayıcısına bu fonksiyondan
    geçmeden ASLA gönderilmemelidir (bkz. services/tenant_rag.py).
    """
    if not text:
        return text
    masked, _mapping = redact(text)

    def _generic(m: re.Match) -> str:
        return _EMBED_ETIKET.get(m.group(1), "[GİZLİ]")

    return _PH_KESIN.sub(_generic, masked)


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
