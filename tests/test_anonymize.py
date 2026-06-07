"""anonymize.py birim testleri."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.anonymize import find_pii, anonymize, audit


def test_find_tckn():
    text = "Davacı 12345678901 numaralı kişi"
    f = find_pii(text)
    assert "tckn" in f


def test_find_phone():
    text = "İletişim: 05551234567"
    f = find_pii(text)
    assert "phone" in f


def test_find_iban():
    text = "Banka hesabı: TR33 0006 1005 1978 6457 8413 26"
    f = find_pii(text)
    assert "iban" in f


def test_find_email():
    text = "test@example.com adresine bildirim"
    f = find_pii(text)
    assert "email" in f


def test_no_pii_clean():
    text = "İcra takibinin iptaline karar verilmiştir."
    f = find_pii(text)
    assert f == {}


def test_anonymize_replaces():
    text = "TCKN: 12345678901 mail: a@b.com"
    out, counts = anonymize(text)
    assert "12345678901" not in out
    assert "[TCKN]" in out
    assert "[EMAIL]" in out
    assert counts["tckn"] == 1
    assert counts["email"] == 1


def test_audit_clean():
    text = "İcra hukuku kararı."
    a = audit(text)
    assert a["contains_pii"] is False
    assert a["types"] == []


def test_audit_dirty():
    text = "TC: 12345678901"
    a = audit(text)
    assert a["contains_pii"] is True
    assert "tckn" in a["types"]


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
