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


def test_heuristic_masks_role_prefixed_names():
    """Heuristik katman (NER olmadan da) rol bağlamındaki kişi adlarını maskeler."""
    text = "Davacı Ahmet Yılmaz, davalı Mehmet Demir aleyhine dava açmıştır."
    masked, m = pii.redact(text)
    assert m.names_redacted is True
    assert "Ahmet" not in masked
    assert "Mehmet" not in masked
    # Rol kelimeleri korunur
    assert "Davacı" in masked and "davalı" in masked
    # Birebir geri yüklenebilir
    assert pii.unredact(masked, m) == text


def test_heuristic_masks_address():
    text = "Adres: Bağdat Caddesi No:12 Daire:5"
    masked, m = pii.redact(text)
    assert "Bağdat Caddesi" not in masked
    assert m.names_redacted is True
    assert pii.unredact(masked, m) == text


def test_court_names_not_false_positive():
    """Rol öneki olmayan mahkeme/kurum adları heuristik tarafından maskelenmez."""
    text = "Yargıtay 12. Hukuk Dairesi ve Bölge Adliye Mahkemesi kararı."
    masked, m = pii.redact(text)
    assert "Yargıtay" in masked
    assert "Mahkemesi" in masked


def test_audit_pii_reports_name_layer():
    a = pii.audit_pii("TCKN: 12345678901")
    assert a["contains_pii"] is True
    # İsim katmanı her zaman aktif (en az heuristik)
    assert a["names_layer_active"] is True
    assert a["name_layer"] in ("ner", "heuristic")


def test_empty_text():
    masked, m = pii.redact("")
    assert masked == ""
    assert m.forward == {}
