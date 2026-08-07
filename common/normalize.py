"""Türkçe hukuki metin normalizasyonu."""
import html as _html
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


#: Metinde HTML kalıntısı olduğunu ele veren işaretler.
_HTML_IZI_RE = re.compile(
    r"<\s*(?:html|head|body|font|br|p|div|span|table|tr|td|meta|ul|li)\b|"
    r"&(?:lt|gt|amp|nbsp|quot|#\d+);",
    re.IGNORECASE,
)

#: `_HTML_IZI_RE` deseninin ham hâli — SQL/DuckDB tarafında AYNI tespiti
#: yapabilmek için dışa açık. Desen RE2 uyumlu (yalnızca `\b`, `\s`, `\d` ve
#: yakalamayan grup kullanıyor), dolayısıyla DuckDB `regexp_matches(x, ?, 'i')`
#: ile Python `re` birebir aynı sonucu verir — bkz. tests/test_bayat_tara.py
#: içindeki fark testi. İki yerde iki desen TUTMUYORUZ; sapma olursa test düşer.
HTML_IZI_DESENI = _HTML_IZI_RE.pattern

#: Kaç tur unescape+strip denenecek. Kaynak siteler bazen HTML'i JSON içinde
#: KAÇIŞLI (&lt;font&gt;) gönderiyor; bir tur unescape sonrası ortaya gerçek
#: HTML çıkıyor ve ikinci bir temizlik turu gerekiyor.
_MAX_TEMIZLIK_TURU = 3


def html_izi_var_mi(text: str) -> bool:
    """Metinde temizlenmemiş HTML kalıntısı var mı?"""
    return bool(text) and bool(_HTML_IZI_RE.search(text))


def clean_html_to_text(html: str) -> str:
    """HTML'den karar metnini ayıkla — script/style atılır, sadece görünür içerik.

    KAÇIŞLI HTML'E KARŞI DAYANIKLI
    ------------------------------
    Danıştay API'si karar metnini JSON içinde HTML-KAÇIŞLI gönderebiliyor
    (`&lt;font face=...&gt;`). Eski kod "metinde '<' var mı" diye bakıp
    kaçışlı hâli düz metin sanıyor, sonra normalize sırasında entity'ler
    çözülünce ham HTML kullanıcıya, embedding'e ve tam metin indeksine
    olduğu gibi giriyordu.

    Artık: unescape → strip → hâlâ HTML izi varsa tekrarla (en fazla 3 tur).
    """
    if not html:
        return ""
    from selectolax.parser import HTMLParser

    text = html
    for _ in range(_MAX_TEMIZLIK_TURU):
        # 1) Entity'leri çöz. Çift kaçışlı içerikte (&amp;lt;) bu tur yalnızca
        #    bir kat açar; kalan katlar sonraki turlarda çözülür.
        cozulmus = _html.unescape(text)

        # 2) Gerçek etiket varsa ayıkla. Yoksa (henüz kaçışlıysa) dokunma —
        #    bir sonraki tur bir kat daha unescape edecek.
        if "<" in cozulmus:
            tree = HTMLParser(cozulmus)
            # JavaScript, CSS ve <head> içeriği (meta/charset) metne girmemeli.
            for sel in ("script", "style", "noscript", "iframe", "head"):
                for node in tree.css(sel):
                    node.decompose()
            body = tree.body or tree.root
            cozulmus = body.text(separator="\n") if body else ""

        # İlerleme yoksa döngüde kalma (bozuk/parse edilemeyen içerik).
        if cozulmus == text:
            break
        text = cozulmus
        if not html_izi_var_mi(text):
            break

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
