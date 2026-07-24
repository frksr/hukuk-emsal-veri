"""UYAP'tan indirilen dosyaları parse et.

Avukatlar UYAP avukat portalından dosyaları PDF, DOCX, UDF (UYAP'ın kendi
formatı) veya bazen XML/JSON olarak alabilir. Bu modül hepsini ortak text
formatına çevirir.

Metadata çıkarımı:
- Esas no (örn 2024/1234)
- Karar no (örn 2024/5678)
- Mahkeme
- Taraflar (anonim — KVKK)
- Tarih
"""
from __future__ import annotations
import io
import re
import zipfile
from typing import Optional
from xml.etree import ElementTree as ET

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


def _strip_rtf(rtf_bytes: bytes) -> str:
    """Basit, bağımlılıksız RTF → düz metin çözücü.

    UDF içindeki metin blokları RTF olarak saklanır (bkz. parse_udf). Tam bir
    RTF spec implementasyonu değildir; kontrol kelimelerini/gruplarını
    (fonttbl, colortbl, pict, ...) temizleyip okunabilir metni çıkarır —
    arama/RAG indexleme amaçlı yeterli doğrulukta.
    """
    try:
        text = rtf_bytes.decode("cp1254", errors="ignore")
    except Exception:
        text = rtf_bytes.decode("latin-1", errors="ignore")

    out: list[str] = []
    i, n = 0, len(text)
    depth = 0
    skip_group_depth: Optional[int] = None
    SKIP_WORDS = {"fonttbl", "colortbl", "stylesheet", "info", "pict", "object",
                  "footer", "header", "generator", "*"}

    while i < n:
        ch = text[i]
        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth -= 1
            if skip_group_depth is not None and depth < skip_group_depth:
                skip_group_depth = None
            i += 1
            continue
        if ch == "\\":
            m = re.match(r"\\([a-zA-Z]+)(-?\d+)?[ ]?", text[i:])
            if m:
                word = m.group(1)
                i += m.end()
                if word in ("par", "line"):
                    out.append("\n")
                elif word == "tab":
                    out.append("\t")
                elif word in SKIP_WORDS:
                    skip_group_depth = depth
                continue
            m2 = re.match(r"\\'([0-9a-fA-F]{2})", text[i:])
            if m2:
                if skip_group_depth is None:
                    try:
                        out.append(bytes([int(m2.group(1), 16)]).decode("cp1254", errors="ignore"))
                    except Exception:
                        pass
                i += m2.end()
                continue
            if i + 1 < n and text[i + 1] in "{}\\":
                if skip_group_depth is None:
                    out.append(text[i + 1])
                i += 2
                continue
            i += 1
            continue
        if skip_group_depth is None:
            out.append(ch)
        i += 1
    return "".join(out)


def parse_udf(content: bytes) -> str:
    """UYAP .udf → düz metin.

    UDF, teknik olarak bir ZIP arşividir: içinde XML yapısal veri, RTF
    formatında metin blokları ve (varsa) PKCS#7 dijital imza barındırır.
    Tek bir sabit iç dosya adı garanti edilmediğinden arşivdeki tüm girdiler
    taranır: RTF içerik metne çevrilir, XML içerik etiketlerinden metin
    çıkarılır, düz metin girdileri doğrudan alınır. İmza dosyaları atlanır.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as e:
        raise ValueError(
            "Geçerli bir UDF/ZIP arşivi değil. Dosyanın bozulmadığından emin "
            f"olun veya UYAP Doküman Editörü ile PDF'e çevirip tekrar yükleyin. ({e})"
        )

    blocks: list[str] = []
    for name in zf.namelist():
        lower = name.lower()
        if lower.endswith("/") or "signature" in lower or lower.endswith((".p7s", ".p7m")):
            continue
        try:
            data = zf.read(name)
        except Exception:
            continue
        if not data:
            continue

        stripped = data.lstrip()
        if stripped[:5] == b"{\\rtf":
            blocks.append(_strip_rtf(data))
        elif lower.endswith(".xml") or stripped[:1] == b"<":
            try:
                root = ET.fromstring(data)
                blocks.append(" ".join(t.strip() for t in root.itertext() if t and t.strip()))
            except ET.ParseError:
                continue
        elif lower.endswith(".txt"):
            try:
                blocks.append(data.decode("utf-8"))
            except UnicodeDecodeError:
                blocks.append(data.decode("cp1254", errors="replace"))

    combined = "\n\n".join(b for b in blocks if b and b.strip())
    if not combined.strip():
        raise ValueError(
            "UDF içinden metin çıkarılamadı. Dosyayı UYAP Doküman Editörü ile "
            "PDF'e çevirip tekrar yüklemeyi deneyin."
        )
    return normalize_text(combined)


def parse_file(content: bytes, extension: str) -> str:
    ext = extension.lower().lstrip(".")
    if ext == "pdf":
        return parse_pdf(content)
    if ext in ("docx", "doc"):
        return parse_docx(content)
    if ext == "udf":
        return parse_udf(content)
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
