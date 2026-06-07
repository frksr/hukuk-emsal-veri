"""services/encryption.py birim testleri — envelope encryption + crypto-shred mantığı."""
import os
import pytest
from cryptography.exceptions import InvalidTag

from services import encryption as enc


def test_dek_wrap_unwrap_roundtrip():
    dek = enc.generate_dek()
    assert len(dek) == 32
    wrapped, iv = enc.wrap_dek(dek)
    assert wrapped != dek
    assert enc.unwrap_dek(wrapped, iv) == dek


def test_generate_dek_is_random():
    assert enc.generate_dek() != enc.generate_dek()


def test_encrypt_decrypt_roundtrip():
    dek = enc.generate_dek()
    data = "Davacı kazandı. Gizli dosya içeriği.".encode()
    ct, iv = enc.encrypt_bytes(data, "tenant-a", dek)
    assert ct != data
    assert enc.decrypt_bytes(ct, iv, "tenant-a", dek) == data


def test_text_roundtrip():
    dek = enc.generate_dek()
    ct_b64, iv_b64 = enc.encrypt_text("merhaba dünya", "t1", dek)
    assert enc.decrypt_text(ct_b64, iv_b64, "t1", dek) == "merhaba dünya"


def test_wrong_tenant_aad_fails():
    """tenant_id AAD olarak bağlandığı için yanlış tenant ile çözme başarısız."""
    dek = enc.generate_dek()
    ct, iv = enc.encrypt_bytes(b"x", "tenant-a", dek)
    with pytest.raises(InvalidTag):
        enc.decrypt_bytes(ct, iv, "tenant-b", dek)


def test_tampered_ciphertext_fails():
    dek = enc.generate_dek()
    ct, iv = enc.encrypt_bytes(b"hello world data", "t", dek)
    tampered = bytes([ct[0] ^ 0xFF]) + ct[1:]
    with pytest.raises(InvalidTag):
        enc.decrypt_bytes(tampered, iv, "t", dek)


def test_crypto_shred_semantics():
    """DEK 'silindiğinde' (kaybolduğunda) veri başka DEK ile çözülemez.

    Kriptografik silmenin özü: wrapped DEK yok olunca ham DEK türetilemez ve
    farklı bir DEK ciphertext'i çözemez (InvalidTag)."""
    dek = enc.generate_dek()
    ct, iv = enc.encrypt_bytes(b"silinecek veri", "t", dek)
    other_dek = enc.generate_dek()  # DEK kaybedildi → elimizde farklı bir anahtar var
    with pytest.raises(InvalidTag):
        enc.decrypt_bytes(ct, iv, "t", other_dek)


def test_legacy_fallback_decryption():
    """Eski (deterministik) anahtarla şifrelenmiş kayıt, yeni DEK başarısız olunca
    legacy anahtarla çözülebilmeli (geriye dönük uyum)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    legacy_key = enc._legacy_tenant_key("tenant-x")
    iv = os.urandom(12)
    ct = AESGCM(legacy_key).encrypt(iv, b"eski kayit", associated_data=b"tenant-x")

    # Çözerken geçersiz bir 'yeni' DEK verilir → legacy fallback devreye girmeli.
    bogus_dek = enc.generate_dek()
    assert enc.decrypt_bytes(ct, iv, "tenant-x", bogus_dek) == b"eski kayit"
