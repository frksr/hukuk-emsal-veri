"""Türkçe hukuki metin normalizasyonu."""
import re
import unicodedata

_REPLACEMENTS = {
    "Ý": "İ", "ý": "ı", "Þ": "Ş",
    "þ": "ş", "Ð": "Ğ", "ð": "ğ",
}

_WHITESPACE_RE = re.compile(r"\s+")
_PAGE_NUMBER_RE = re.compile(r"^\s*-?\s*\d+\s*-?\s*$", re.MULTILINE)


def normalize_text(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    for k, v in _REPLACEMENTS.items():
        text = text.replace(k, v)
    text = _PAGE_NUMBER_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def clean_html_to_text(html: str) -> str:
    """HTML'den karar metnini ayıkla — script/style atılır, sadece görünür içerik."""
    if not html:
        return ""
    from selectolax.parser import HTMLParser
    tree = HTMLParser(html)
    # JavaScript ve CSS bloklarını sil
    for sel in ("script", "style", "noscript", "iframe", "head"):
        for node in tree.css(sel):
            node.decompose()
    body = tree.body or tree.root
    text = body.text(separator="\n") if body else ""
    return normalize_text(text)


def extract_case_no(text):
    m = re.search(r"\bE(?:sas)?\.?\s*[:\.]?\s*(\d{4}/\d+)", text)
    return m.group(1) if m else None


def extract_decision_no(text):
    m = re.search(r"\bK(?:arar)?\.?\s*[:\.]?\s*(\d{4}/\d+)", text)
    return m.group(1) if m else None


def extract_decision_date(text):
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", text)
    if not m:
        return None
    d, mo, y = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


def tr_fold(s):
    if not s:
        return ""
    s = s.replace("İ", "i").replace("I", "ı")
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s


def detect_keywords(text, keywords):
    folded = tr_fold(text)
    return [k for k in keywords if tr_fold(k) in folded]
