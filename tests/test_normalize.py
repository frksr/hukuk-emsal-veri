"""normalize.py birim testleri."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.normalize import (
    normalize_text, extract_case_no, extract_decision_no,
    extract_decision_date, detect_keywords,
)


def test_normalize_basic():
    assert normalize_text("  hello   world  \n\n") == "hello world"


def test_normalize_turkish_chars():
    src = "Ýstanbul Þehri"  # OCR bozuk
    out = normalize_text(src)
    assert "İstanbul" in out
    assert "Şehri" in out


def test_normalize_empty():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""


def test_normalize_strips_page_numbers():
    src = "Paragraf 1\n- 5 -\nParagraf 2"
    out = normalize_text(src)
    assert "Paragraf 1" in out
    assert "Paragraf 2" in out


def test_extract_case_no():
    assert extract_case_no("Esas: 2023/1234 Karar: 2024/5678") == "2023/1234"
    assert extract_case_no("E. 2022/999") == "2022/999"
    assert extract_case_no("metin yok") is None


def test_extract_decision_no():
    assert extract_decision_no("Esas: 2023/1234 Karar: 2024/5678") == "2024/5678"
    assert extract_decision_no("K. 2021/42") == "2021/42"


def test_extract_decision_date():
    assert extract_decision_date("Karar tarihi: 15.03.2024") == "2024-03-15"
    assert extract_decision_date("Tarih: 01/12/2023") == "2023-12-01"
    assert extract_decision_date("yok") is None


def test_detect_keywords():
    text = "İcra takibi başlatılmış, ihtarname tebliğ edilmiştir."
    found = detect_keywords(text, ["icra", "ihtar", "haciz", "tahsilat"])
    assert "icra" in found
    assert "ihtar" in found
    assert "haciz" not in found


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


# ---------------------------------------------------------------------------
# HTML kirliliği — kaçışlı HTML regresyonu
# ---------------------------------------------------------------------------
# Danıştay/Yargıtay API'leri karar metnini JSON içinde KAÇIŞLI HTML olarak
# gönderebiliyor. Eski kod "metinde '<' var mı" diye bakıp kaçışlı hâli düz
# metin sanıyor, entity'ler çözülünce ham HTML kullanıcıya + embedding'e +
# tam metin indeksine olduğu gibi giriyordu.

from common.normalize import clean_html_to_text, html_izi_var_mi

_KARAR_HTML = (
    '<html><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
    '</head><body leftmargin="25"><b><font face="Verdana" size="2">'
    'Danıştay 9. Daire 2023/2318 E. , 2025/843 K.</font></b><br>'
    '<p align="justify"><font face="Verdana">Esas No : 2023/2318</font></p>'
    '</body></html>'
)


def test_ham_html_temizlenir():
    out = clean_html_to_text(_KARAR_HTML)
    assert not html_izi_var_mi(out)
    assert "Danıştay 9. Daire" in out
    assert "2023/2318" in out
    assert "Verdana" not in out and "charset" not in out


def test_kacisli_html_de_temizlenir():
    """ASIL REGRESYON: HTML entity olarak kaçışlanmış geldiğinde."""
    kacisli = _KARAR_HTML.replace("<", "&lt;").replace(">", "&gt;")
    out = clean_html_to_text(kacisli)
    assert not html_izi_var_mi(out), out[:120]
    assert "Danıştay 9. Daire" in out
    assert "Verdana" not in out


def test_cift_kacisli_html_de_temizlenir():
    cift = _KARAR_HTML.replace("<", "&amp;lt;").replace(">", "&amp;gt;")
    assert not html_izi_var_mi(clean_html_to_text(cift))


def test_head_icerigi_metne_girmez():
    """<meta charset> gibi içerik embedding'e gitmemeli."""
    out = clean_html_to_text(_KARAR_HTML)
    for cop in ("http-equiv", "charset", "UTF-8", "leftmargin"):
        assert cop not in out


def test_duz_metin_bozulmaz():
    """İçinde '<' geçen normal hukuki metin zarar görmemeli."""
    duz = "Faiz oranı % 5 < % 9 olduğundan alacak azalmıştır. Esas No : 2023/1"
    assert "2023/1" in clean_html_to_text(duz)
    assert "%" in clean_html_to_text(duz)


def test_bos_girdi():
    assert clean_html_to_text("") == ""
    assert clean_html_to_text(None) == ""


def test_html_izi_tespiti():
    assert html_izi_var_mi('<font face="x">')
    assert html_izi_var_mi("&lt;font&gt;")
    assert html_izi_var_mi("&nbsp;")
    assert not html_izi_var_mi("Danıştay 9. Daire 2023/2318 E.")
    assert not html_izi_var_mi("")


def test_scraperlar_ham_htmlparser_kullanmiyor():
    """Regresyon kilidi: '<' kontrolüne dayalı eski desen geri gelmesin."""
    import re
    from pathlib import Path

    kok = Path(__file__).resolve().parent.parent
    for ad in ("danistay.py", "yargitay.py"):
        kaynak = (kok / "scrapers" / ad).read_text(encoding="utf-8")
        assert not re.search(r'if\s+"<"\s+in\s+candidate', kaynak), (
            f"scrapers/{ad}: kaçışlı HTML'i düz metin sanan eski kontrol geri gelmiş."
        )
        assert "clean_html_to_text" in kaynak, f"scrapers/{ad}: clean_html_to_text kullanılmıyor."
