"""Per-tenant envelope encryption (kriptografik silme uyumlu).

Model:
    master key (KMS/env)
        └─ wrap ──> per-tenant DEK (RASTGELE üretilir, DB'de wrapped saklanır)
                        └─ encrypt ──> tenant verisi

KVKK m.7 "silme hakkı" — kriptografik silme (crypto-shredding):
    Tenant'ın wrapped DEK satırı silinince (tenant_encryption_keys), DEK geri
    elde edilemez; master key durmaya devam etse bile o tenant'ın verisi
    matematiksel olarak ÇÖZÜLEMEZ hale gelir. Bu, gerçek bir silme garantisidir.

ÖNEMLİ (eski sürümden fark):
    Eski sürüm DEK'i `HKDF(master, salt=tenant_id)` ile deterministik türetiyor ve
    HİÇBİR YERDE saklamıyordu. O modelde "tenant silinince veri okunamaz" iddiası
    YANLIŞTI — master key elde oldukça tenant_id'den DEK her zaman yeniden
    türetilebilirdi. Geriye dönük uyum için eski türetme `_legacy_tenant_key` ile
    korunur; çözme sırasında yeni DEK başarısız olursa eski anahtar denenir.
    (Bu sayede eski şifreli kayıtlar okunmaya devam eder; yeni kayıtlar gerçek
    rastgele DEK ile şifrelenir.)

Bu modül SAF kripto sağlar (DB bilmez). DEK'in yaşam döngüsü (üret/sarmala/sakla/
sil) `services/key_manager.py` içindedir.
"""
from __future__ import annotations
import os
import base64
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.exceptions import InvalidTag

log = logging.getLogger("services.encryption")

_MASTER_KEY_RAW = os.environ.get("MASTER_ENCRYPTION_KEY", "")


def _master_key() -> bytes:
    """32-byte master key. Production'da KMS'ten gelmelidir."""
    if not _MASTER_KEY_RAW:
        raise RuntimeError(
            "MASTER_ENCRYPTION_KEY env yok. Production'da KMS önerilir.\n"
            "Dev için: openssl rand -base64 32"
        )
    raw = base64.b64decode(_MASTER_KEY_RAW)
    if len(raw) < 32:
        raise RuntimeError("Master key min 32 byte olmalı")
    return raw[:32]


# ---------------------------------------------------------------------------
# DEK üretimi + master ile sarmalama (wrap/unwrap)
# ---------------------------------------------------------------------------
def generate_dek() -> bytes:
    """Yeni rastgele 256-bit Data Encryption Key."""
    return os.urandom(32)


def wrap_dek(dek: bytes) -> tuple[bytes, bytes]:
    """DEK'i master key ile şifrele. (wrapped_dek, iv) döner — DB'de saklanır."""
    iv = os.urandom(12)
    aesgcm = AESGCM(_master_key())
    wrapped = aesgcm.encrypt(iv, dek, associated_data=b"tenant-dek-wrap-v1")
    return wrapped, iv


def unwrap_dek(wrapped_dek: bytes, iv: bytes) -> bytes:
    """DB'deki wrapped DEK'i master key ile çöz → ham DEK."""
    aesgcm = AESGCM(_master_key())
    return aesgcm.decrypt(iv, wrapped_dek, associated_data=b"tenant-dek-wrap-v1")


# ---------------------------------------------------------------------------
# Geriye dönük uyum: eski deterministik türetme (DEPRECATED)
# ---------------------------------------------------------------------------
def _legacy_tenant_key(tenant_id: str) -> bytes:
    """DEPRECATED — eski (saklamayan) HKDF türetmesi.

    Sadece eski şifreli kayıtları ÇÖZMEK için kullanılır. Yeni şifreleme bunu
    KULLANMAZ. Kriptografik silme garantisi YOKTU (bkz. modül docstring).
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=tenant_id.encode(),
        info=b"hukuk-emsal-tenant-dek-v1",
    )
    return hkdf.derive(_master_key())


# ---------------------------------------------------------------------------
# Veri şifreleme (DEK ile) — tenant_id sadece AAD (cryptographic binding) olarak
# ---------------------------------------------------------------------------
def encrypt_bytes(data: bytes, tenant_id: str, dek: bytes) -> tuple[bytes, bytes]:
    """Bytes şifrele. (ciphertext, iv) döner.

    `tenant_id` AAD olarak bağlanır: bir tenant'ın ciphertext+iv'si başka bir
    tenant bağlamında çözülmeye çalışılırsa doğrulama başarısız olur.
    """
    iv = os.urandom(12)  # GCM için 96-bit
    aesgcm = AESGCM(dek)
    ciphertext = aesgcm.encrypt(iv, data, associated_data=tenant_id.encode())
    return ciphertext, iv


def decrypt_bytes(ciphertext: bytes, iv: bytes, tenant_id: str, dek: bytes) -> bytes:
    """Şifreli bytes'ı çöz.

    Önce güncel DEK denenir; başarısız olursa (eski kayıt) legacy türetme
    denenir. İkisi de başarısızsa InvalidTag fırlatır.
    """
    aesgcm = AESGCM(dek)
    try:
        return aesgcm.decrypt(iv, ciphertext, associated_data=tenant_id.encode())
    except InvalidTag:
        # Eski sürümde şifrelenmiş olabilir — legacy anahtarla dene.
        legacy = AESGCM(_legacy_tenant_key(tenant_id))
        result = legacy.decrypt(iv, ciphertext, associated_data=tenant_id.encode())
        log.warning(
            "tenant=%s: kayıt legacy anahtarla çözüldü; yeni DEK'e migrate edilmeli.",
            tenant_id,
        )
        return result


def encrypt_text(text: str, tenant_id: str, dek: bytes) -> tuple[str, str]:
    """Metin → base64 ciphertext + base64 IV."""
    ct, iv = encrypt_bytes(text.encode("utf-8"), tenant_id, dek)
    return base64.b64encode(ct).decode(), base64.b64encode(iv).decode()


def decrypt_text(ciphertext_b64: str, iv_b64: str, tenant_id: str, dek: bytes) -> str:
    """Base64 ciphertext → düz metin."""
    ct = base64.b64decode(ciphertext_b64)
    iv = base64.b64decode(iv_b64)
    return decrypt_bytes(ct, iv, tenant_id, dek).decode("utf-8")
