"""KVKK uyumluluğu için kişisel veri tespit + maskeleme."""
import re

# Türkiye'ye özgü PII regex pattern'leri
PATTERNS = {
    "tckn": re.compile(r"\b[1-9]\d{10}\b"),  # 11 haneli TC kimlik
    "phone": re.compile(r"\b(?:0?5\d{2}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2})\b"),
    "iban": re.compile(r"\bTR\d{2}\s?(?:\d{4}\s?){5}\d{2}\b"),
    "email": re.compile(r"\b[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"),
}


def find_pii(text: str) -> dict[str, list[str]]:
    """Metindeki PII örneklerini bul (audit için)."""
    findings = {}
    for name, pat in PATTERNS.items():
        matches = pat.findall(text)
        if matches:
            findings[name] = matches[:5]  # ilk 5 örnek
    return findings


def anonymize(text: str) -> tuple[str, dict[str, int]]:
    """PII'yi placeholder'larla değiştir, sayım döndür."""
    counts = {}
    for name, pat in PATTERNS.items():
        text, n = pat.subn(f"[{name.upper()}]", text)
        if n > 0:
            counts[name] = n
    return text, counts


def audit(text: str) -> dict:
    """Audit raporu döndür: PII içeriyor mu, hangi türler."""
    findings = find_pii(text)
    return {
        "contains_pii": bool(findings),
        "types": list(findings.keys()),
        "method": "regex_v1",
    }
