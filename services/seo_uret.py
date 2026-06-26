"""Otomatik SEO üretimi — blog makaleleri için.

Admin panelde "SEO üret" tetiklendiğinde çağrılır:
  - meta_title, meta_description, keywords, slug, FAQ üretir (LLM; yoksa heuristik)
  - bir SEO skoru (0-100) + iyileştirme notları döndürür

Tasarım: LLM erişilemezse (key yok / hata) sessizce HEURİSTİK üretime düşer;
böylece panel her durumda çalışır. Üretilen alanlar admin tarafından düzenlenebilir.
"""
from __future__ import annotations

import json
import re
import unicodedata

_TR_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
})


def slugify(text: str, max_len: int = 80) -> str:
    """Türkçe-duyarlı URL slug üretir: 'İhtarname Örneği' -> 'ihtarname-ornegi'."""
    if not text:
        return ""
    s = text.translate(_TR_MAP)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:max_len].strip("-")


def _kelime_sayisi(metin: str) -> int:
    return len(re.findall(r"\w+", metin or "", flags=re.UNICODE))


def _ozet_metin(body: str, n: int = 300) -> str:
    duz = re.sub(r"[#*_>`\[\]()]", " ", body or "")
    duz = re.sub(r"\s+", " ", duz).strip()
    return duz[:n]


def seo_skor_hesapla(makale: dict) -> tuple[int, list[str]]:
    """0-100 SEO skoru + eksik/öneri notları (heuristik kontrol listesi)."""
    notlar: list[str] = []
    skor = 0

    title = (makale.get("meta_title") or makale.get("title") or "").strip()
    if 30 <= len(title) <= 60:
        skor += 20
    else:
        notlar.append(
            f"Başlık (meta_title) {len(title)} karakter — ideal 30-60. "
            "Anahtar kelime başta olmalı."
        )

    desc = (makale.get("meta_description") or "").strip()
    if 120 <= len(desc) <= 160:
        skor += 20
    else:
        notlar.append(
            f"Açıklama (meta_description) {len(desc)} karakter — ideal 120-160."
        )

    kw = makale.get("keywords") or []
    if len(kw) >= 3:
        skor += 15
    else:
        notlar.append("En az 3 anahtar kelime ekleyin.")

    kelime = _kelime_sayisi(makale.get("body") or "")
    if kelime >= 300:
        skor += 20
    else:
        notlar.append(
            f"Gövde ~{kelime} kelime — en az 300 kelime önerilir (E-E-A-T)."
        )

    faq = makale.get("faq") or []
    if isinstance(faq, list) and len(faq) >= 2:
        skor += 15
    else:
        notlar.append("En az 2 SSS ekleyin (FAQPage rich result fırsatı).")

    slug = (makale.get("slug") or "").strip()
    if slug and re.fullmatch(r"[a-z0-9-]+", slug):
        skor += 10
    else:
        notlar.append("Geçerli bir slug üretin (yalnız küçük harf, rakam, tire).")

    return min(skor, 100), notlar


def _llm_seo(title: str, body: str) -> dict | None:
    """LLM ile SEO alanlarını üret. Erişilemezse None döner."""
    try:
        from llm.provider import generate, is_available
        if not is_available():
            return None
    except Exception:
        return None

    sistem = (
        "Sen Türk hukuku odaklı bir SEO editörüsün. Sana bir blog makalesinin "
        "başlığı ve gövdesi verilir. SADECE geçerli JSON döndür; açıklama yazma. "
        "Alanlar: meta_title (30-60 karakter, hedef anahtar kelime başta), "
        "meta_description (120-160 karakter, eylem çağrılı), keywords (5-8 öğeli "
        "Türkçe anahtar kelime dizisi), faq (3 öğe; her biri {soru, cevap}). "
        "Türkçe yaz, abartılı vaatlerden kaçın, YMYL hukuk içeriği için ölçülü ol."
    )
    kullanici = (
        f"BAŞLIK:\n{title}\n\nGÖVDE (ilk 4000 karakter):\n{(body or '')[:4000]}\n\n"
        "JSON şeması:\n"
        '{"meta_title": "...", "meta_description": "...", '
        '"keywords": ["...","..."], "faq": [{"soru":"...","cevap":"..."}]}'
    )
    try:
        ham = generate(sistem, kullanici, max_tokens=1200, temperature=0.4)
    except Exception:
        return None

    # JSON'u ayıkla (model bazen ```json ... ``` ile sarabilir).
    m = re.search(r"\{.*\}", ham or "", flags=re.DOTALL)
    if not m:
        return None
    try:
        veri = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(veri, dict):
        return None
    return veri


def makale_seo_uret(title: str, body: str, mevcut_slug: str | None = None) -> dict:
    """Makale için tüm SEO alanlarını üret (LLM; yoksa heuristik).

    Returns:
      {slug, meta_title, meta_description, keywords[list], faq[list],
       seo_score[int], seo_notes[list], kaynak: 'llm'|'heuristik'}
    """
    title = (title or "").strip()
    body = body or ""

    llm = _llm_seo(title, body)
    kaynak = "llm" if llm else "heuristik"

    if llm:
        meta_title = (llm.get("meta_title") or title)[:65]
        meta_description = (llm.get("meta_description") or _ozet_metin(body, 160))[:170]
        keywords = [str(k).strip() for k in (llm.get("keywords") or []) if str(k).strip()]
        faq_ham = llm.get("faq") or []
        faq = []
        for f in faq_ham if isinstance(faq_ham, list) else []:
            soru = str(f.get("soru") or f.get("question") or "").strip()
            cevap = str(f.get("cevap") or f.get("answer") or "").strip()
            if soru and cevap:
                faq.append({"soru": soru, "cevap": cevap})
    else:
        # Heuristik fallback
        meta_title = title[:60]
        meta_description = _ozet_metin(body, 160)
        # Basit anahtar kelime çıkarımı: başlıktaki anlamlı kelimeler
        durak = {"ve", "ile", "için", "nasıl", "nedir", "mi", "mı", "bir", "bu"}
        kelimeler = [w.lower() for w in re.findall(r"\w+", title, re.UNICODE)]
        keywords = []
        for w in kelimeler:
            if len(w) > 2 and w not in durak and w not in keywords:
                keywords.append(w)
        keywords = keywords[:8]
        faq = []

    slug = (mevcut_slug or "").strip() or slugify(title)

    makale = {
        "slug": slug,
        "meta_title": meta_title,
        "meta_description": meta_description,
        "keywords": keywords,
        "faq": faq,
        "title": title,
        "body": body,
    }
    skor, notlar = seo_skor_hesapla(makale)

    return {
        "slug": slug,
        "meta_title": meta_title,
        "meta_description": meta_description,
        "keywords": keywords,
        "faq": faq,
        "seo_score": skor,
        "seo_notes": notlar,
        "kaynak": kaynak,
    }
