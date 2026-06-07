"""UYAP'tan indirilen dosyaları parse et.

Avukatlar UYAP avukat portalından dosyaları PDF, DOCX veya bazen XML/JSON
olarak alabilir. Bu modül hepsini ortak text formatına çevirir.

Metadata çıkarımı:
- Esas no (örn 2024/1234)
- Karar no (örn 2024/5678)
- Mahkeme
- Taraflar (anonim — KVKK)
- Tarih
"""
from __future__ import annotations
import re
from typing import Optional

from common.normalize import (
    normalize_text, extract_case_no, extract_decision_no, extract_decision_date,
)


def parse_pdf(content: bytes) -> str:
    """PDF → düz metin (pypdf)."""
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(content))
        texts = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                continue
        return normalize_text("\n\n".join(texts))
    except Exception as e:
        raise ValueError(f"PDF parse hatası: {e}")


def parse_docx(content: bytes) -> str:
    """DOCX → düz metin (python-docx)."""
    try:
        from docx import Document
        import io
        doc = Document(io.BytesIO(content))
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        return normalize_text("\n\n".join(paras))
    except Exception as e:
        raise ValueError(f"DOCX parse hatası: {e}")


def parse_txt(content: bytes) -> str:
    for enc in ("utf-8", "cp1254", "iso-8859-9"):
        try:
            return normalize_text(content.decode(enc))
        except UnicodeDecodeError:
            continue
    return normalize_text(content.decode("utf-8", errors="replace"))


def parse_file(content: bytes, extension: str) -> str:
    ext = extension.lower().lstrip(".")
    if ext == "pdf":
        return parse_pdf(content)
    if ext in ("docx", "doc"):
        return parse_docx(content)
    if ext in ("txt", "md"):
        return parse_txt(content)
    raise ValueError(f"Desteklenmeyen format: {ext}")


def extract_metadata(text: str) -> dict:
    """Karar/dilekçeden metadata çıkar (UYAP belgelerinde standart)."""
    if not text:
        return {}

    # Mahkeme tespit (örn: "İstanbul 12. İcra Mahkemesi")
    court_match = re.search(
        r"((?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+(?:Ağır\s+)?(?:Asliye|Sulh)?\s*(?:Hukuk|Ceza|İcra|Aile|İş|Vergi|Tüketici|Trafik|Fikri\s+ve\s+Sınai\s+Haklar)\s+Mahkemesi)+)|"
        r"(?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+\d+\.\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+Mahkemesi)|"
        r"(?:Yargıtay\s+\d+\.\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+Dairesi)|"
        r"(?:Danıştay\s+\d+\.\s+Dairesi)|"
        r"(?:Anayasa\s+Mahkemesi))",
        text[:3000],
    )

    return {
        "case_no": extract_case_no(text),
        "decision_no": extract_decision_no(text),
        "decision_date": extract_decision_date(text),
        "court": court_match.group(0) if court_match else None,
    }


def guess_document_type(text: str, filename: Optional[str] = None) -> str:
    """Dosyanın türünü tahmin et: dilekce | karar | sozlesme | ihtarname | evrak."""
    if not text:
        return "evrak"
    t_lower = text[:2000].lower()

    if any(k in t_lower for k in ["sayın hakim", "sayın mahkeme", "açıklamalarımı sun"]):
        return "dilekce"
    if any(k in t_lower for k in ["içtihat metni", "esas no:", "karar tarihi", "yargıtay"]):
        return "karar"
    if any(k in t_lower for k in ["ihtar eden", "muhatap", "ihtarname"]):
        return "ihtarname"
    if any(k in t_lower for k in ["sözleşme", "taraflar arasında", "iş bu sözleşme", "madde 1"]):
        return "sozlesme"

    if filename:
        fl = filename.lower()
        if "dilekce" in fl or "dilekçe" in fl:
            return "dilekce"
        if "karar" in fl:
            return "karar"
        if "sozlesme" in fl or "sözleşme" in fl:
            return "sozlesme"

    return "evrak"
