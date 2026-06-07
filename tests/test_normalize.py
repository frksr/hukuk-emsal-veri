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
