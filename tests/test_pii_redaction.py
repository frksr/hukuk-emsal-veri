"""services/pii_redaction.py birim testleri."""
from services import pii_redaction as pii


def test_redact_unredact_roundtrip():
    text = "TCKN 12345678901, IBAN TR33 0006 1005 1978 6457 8413 26, mail a@b.com"
    masked, m = pii.redact(text)
    assert "12345678901" not in masked
    assert "a@b.com" not in masked
    # unredact orijinali geri getirir
    assert pii.unredact(masked, m) == text


def test_structural_pii_detected():
    text = "Tel: 05551234567 / TCKN: 12345678901"
    masked, m = pii.redact(text)
    assert "05551234567" not in masked
    assert "12345678901" not in masked


def test_same_value_same_placeholder():
    text = "a@b.com ... tekrar a@b.com"
    masked, m = pii.redact(text)
    # Aynı değer aynı placeholder ile eşlenir
    assert len(m.forward) == 1


def test_names_not_redacted_without_ner():
    """NER yoksa kişi adları MASKELENMEZ ve names_redacted False olmalı.

    Bu, abartılı 'LLM hiç kişisel veri görmez' iddiasını engelleyen güvenlik
    bayrağıdır."""
    text = "Davacı Ahmet Yılmaz, davalı Mehmet Demir'e karşı."
    masked, m = pii.redact(text)
    if not pii.ner_available():
        assert m.names_redacted is False
        # İsim hâlâ metinde (regex yakalayamaz)
        assert "Ahmet" in masked


def test_audit_pii_reports_names_layer_flag():
    a = pii.audit_pii("TCKN: 12345678901")
    assert a["contains_pii"] is True
    assert "names_layer_active" in a
    assert a["names_layer_active"] == pii.ner_available()


def test_empty_text():
    masked, m = pii.redact("")
    assert masked == ""
    assert m.forward == {}
