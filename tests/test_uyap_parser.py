"""services/uyap_parser.py birim testleri (UDF parser dahil)."""
import io
import sys
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.uyap_parser import (
    parse_file, parse_udf, _strip_rtf, extract_metadata, guess_document_type,
)


def _make_udf(rtf_body: bytes, extra_entries: dict[str, bytes] | None = None) -> bytes:
    """Test için basit bir UDF (zip+RTF) arşivi üretir."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("content.rtf", rtf_body)
        for name, data in (extra_entries or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_strip_rtf_basic():
    rtf = rb"{\rtf1\ansi\deff0 {\fonttbl{\f0 Times;}}Merhaba d\'fcnya\par Bu ikinci sat\'fdr.}"
    out = _strip_rtf(rtf)
    assert "Merhaba" in out
    assert "\n" in out  # \par -> newline


def test_strip_rtf_skips_fonttbl_content():
    rtf = rb"{\rtf1{\fonttbl{\f0 Arial;}{\f1 Times New Roman;}}Asil metin burada.}"
    out = _strip_rtf(rtf)
    assert "Arial" not in out
    assert "Asil metin burada." in out


def test_parse_udf_extracts_text_from_rtf_entry():
    rtf = rb"{\rtf1\ansi Esas No: 2024/123 Karar No: 2024/456 Yarg\'fdtay 12. Hukuk Dairesi\par}"
    content = _make_udf(rtf)
    text = parse_udf(content)
    assert "2024/123" in text
    assert "2024/456" in text


def test_parse_udf_skips_signature_entries():
    rtf = rb"{\rtf1 Karar metni burada test amacli yeterince uzun bir icerik olsun diye.\par}"
    content = _make_udf(rtf, extra_entries={"signature.p7s": b"\x00\x01binary-signature-data"})
    text = parse_udf(content)
    assert "Karar metni" in text


def test_parse_udf_bad_zip_raises():
    try:
        parse_udf(b"not a zip file at all")
        assert False, "ValueError bekleniyordu"
    except ValueError as e:
        assert "ZIP" in str(e) or "zip" in str(e)


def test_parse_udf_empty_archive_raises():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("signature.p7s", b"only a signature, no text")
    try:
        parse_udf(buf.getvalue())
        assert False, "ValueError bekleniyordu (metin çıkarılamadı)"
    except ValueError as e:
        assert "metin" in str(e).lower()


def test_parse_file_dispatches_udf():
    rtf = rb"{\rtf1 Dilek\'e7e metni test icin yeterince uzun bir paragraf olsun burada.\par}"
    content = _make_udf(rtf)
    text = parse_file(content, "udf")
    assert "Dilek" in text


def test_parse_file_unsupported_ext():
    try:
        parse_file(b"veri", "exe")
        assert False, "ValueError bekleniyordu"
    except ValueError:
        pass


def test_extract_metadata_from_udf_text():
    rtf = rb"{\rtf1 Istanbul 12. Icra Mahkemesi Esas: 2024/1234 Karar: 2024/5678 Karar tarihi: 15.03.2024\par}"
    content = _make_udf(rtf)
    text = parse_udf(content)
    meta = extract_metadata(text)
    assert meta["case_no"] == "2024/1234"
    assert meta["decision_no"] == "2024/5678"


def test_guess_document_type_udf_dilekce():
    text = "Sayın Hakim, açıklamalarımı sunarım. " * 5
    assert guess_document_type(text, "dilekce.udf") == "dilekce"


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
