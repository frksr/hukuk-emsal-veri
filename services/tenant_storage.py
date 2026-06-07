"""Per-tenant şifreli dosya depolama.

Dev: local filesystem (data/tenant_storage/{tenant_id}/{doc_id}.enc)
Prod: S3 / Railway Volume / MinIO (aynı interface)

Şifreleme: per-tenant rastgele DEK (bkz. services/key_manager + encryption).
Tenant tamamen silinince purge_tenant() hem dosyaları siler hem DEK'i yok eder
(kriptografik silme — KVKK m.7).
"""
from __future__ import annotations
import os
from pathlib import Path

from services.encryption import encrypt_bytes, decrypt_bytes
from services.key_manager import get_tenant_dek, destroy_tenant_dek

STORAGE_ROOT = Path(os.environ.get("TENANT_STORAGE_ROOT", "data/tenant_storage"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def _path(tenant_id: str, doc_id: str, ext: str = "enc") -> Path:
    tdir = STORAGE_ROOT / tenant_id
    tdir.mkdir(parents=True, exist_ok=True)
    return tdir / f"{doc_id}.{ext}"


async def store(tenant_id: str, doc_id: str, raw_bytes: bytes) -> dict:
    """Şifreli sakla. Storage key + IV döner (DB'ye yaz)."""
    dek = await get_tenant_dek(tenant_id)
    ciphertext, iv = encrypt_bytes(raw_bytes, tenant_id, dek)
    p = _path(tenant_id, doc_id)
    p.write_bytes(ciphertext)
    return {
        "storage_key": str(p.relative_to(STORAGE_ROOT.parent)),
        "encryption_iv": iv,
        "file_size": len(raw_bytes),
    }


async def retrieve(tenant_id: str, doc_id: str, iv: bytes) -> bytes:
    """Şifreli dosyayı çöz, ham bytes döndür."""
    p = _path(tenant_id, doc_id)
    if not p.exists():
        raise FileNotFoundError(f"Dosya yok: {p}")
    dek = await get_tenant_dek(tenant_id)
    ciphertext = p.read_bytes()
    return decrypt_bytes(ciphertext, iv, tenant_id, dek)


def delete(tenant_id: str, doc_id: str):
    """Tek dosyayı sil."""
    p = _path(tenant_id, doc_id)
    if p.exists():
        p.unlink()


async def purge_tenant(tenant_id: str):
    """Tüm tenant verisini sil + DEK'i yok et (KVKK kriptografik silme).

    Sıra önemli: önce DEK silinir (veri artık çözülemez), sonra dosyalar.
    """
    await destroy_tenant_dek(tenant_id)
    tdir = STORAGE_ROOT / tenant_id
    if tdir.exists():
        import shutil
        shutil.rmtree(tdir)


# Geriye dönük uyum için eski isim.
async def delete_tenant_all(tenant_id: str):
    await purge_tenant(tenant_id)
