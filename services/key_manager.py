"""Per-tenant DEK yaşam döngüsü yöneticisi.

- get_tenant_dek(tenant_id): tenant'ın DEK'ini döndürür; yoksa rastgele üretip
  master ile sarmalayarak DB'ye yazar (lazy provisioning).
- destroy_tenant_dek(tenant_id): wrapped DEK satırını siler → kriptografik silme.

Çözülmüş (ham) DEK'ler süreç-içi LRU cache'te tutulur; restart'ta temizlenir.
DB tablosu: tenant_encryption_keys (bkz. infra/db/07_rls_hardening.sql).
"""
from __future__ import annotations
import logging
from collections import OrderedDict

from api.db import service_session
from services.encryption import generate_dek, wrap_dek, unwrap_dek

log = logging.getLogger("services.key_manager")

# tenant_id -> ham DEK (sınırlı boyutlu cache; en eski düşer)
_DEK_CACHE: "OrderedDict[str, bytes]" = OrderedDict()
_CACHE_MAX = 512


def _cache_get(tenant_id: str) -> bytes | None:
    dek = _DEK_CACHE.get(tenant_id)
    if dek is not None:
        _DEK_CACHE.move_to_end(tenant_id)
    return dek


def _cache_put(tenant_id: str, dek: bytes) -> None:
    _DEK_CACHE[tenant_id] = dek
    _DEK_CACHE.move_to_end(tenant_id)
    while len(_DEK_CACHE) > _CACHE_MAX:
        _DEK_CACHE.popitem(last=False)


async def get_tenant_dek(tenant_id: str) -> bytes:
    """Tenant'ın ham DEK'ini döndür. Yoksa üret + DB'ye sarmalayarak yaz.

    Yarış (aynı tenant'a eşzamanlı ilk yazım) durumunda
    `ON CONFLICT DO NOTHING` + tekrar SELECT ile tek DEK garanti edilir.
    """
    cached = _cache_get(tenant_id)
    if cached is not None:
        return cached

    # tenant_encryption_keys RLS ile app_user'a tümüyle kapalıdır; yalnızca
    # service rolü (BYPASSRLS) erişebilir.
    async with service_session() as conn:
        row = await conn.fetchrow(
            "SELECT wrapped_dek, dek_iv FROM tenant_encryption_keys WHERE tenant_id = $1",
            tenant_id,
        )
        if row is None:
            dek = generate_dek()
            wrapped, iv = wrap_dek(dek)
            await conn.execute(
                """INSERT INTO tenant_encryption_keys (tenant_id, wrapped_dek, dek_iv)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (tenant_id) DO NOTHING""",
                tenant_id, wrapped, iv,
            )
            # Eşzamanlı başka bir istek yazmış olabilir → kesin kaydı oku.
            row = await conn.fetchrow(
                "SELECT wrapped_dek, dek_iv FROM tenant_encryption_keys WHERE tenant_id = $1",
                tenant_id,
            )

    dek = unwrap_dek(bytes(row["wrapped_dek"]), bytes(row["dek_iv"]))
    _cache_put(tenant_id, dek)
    return dek


async def destroy_tenant_dek(tenant_id: str) -> bool:
    """Wrapped DEK'i kalıcı olarak sil (kriptografik silme).

    Dönüş: bir satır silindiyse True. Silindikten sonra bu tenant'ın şifreli
    verisi geri çözülemez.
    """
    _DEK_CACHE.pop(tenant_id, None)
    async with service_session() as conn:
        result = await conn.execute(
            "DELETE FROM tenant_encryption_keys WHERE tenant_id = $1",
            tenant_id,
        )
    deleted = result.endswith(" 1")
    if deleted:
        log.info("tenant=%s DEK silindi (crypto-shredding).", tenant_id)
    return deleted
