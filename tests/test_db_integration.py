"""Canlı DB entegrasyon testleri (RLS izolasyonu + kriptografik silme).

Yalnızca RUN_DB_TESTS=1 iken ve local Docker Postgres ayaktayken çalışır:

    docker compose up -d postgres
    RUN_DB_TESTS=1 \
    DATABASE_URL=postgresql://app_user:app_user_pw@localhost:5432/hukuk_emsal \
    SERVICE_DATABASE_URL=postgresql://app_service:app_service_pw@localhost:5432/hukuk_emsal \
    MASTER_ENCRYPTION_KEY=... \
    pytest tests/test_db_integration.py
"""
import asyncio
import os

import pytest

if not os.environ.get("RUN_DB_TESTS"):
    pytest.skip("RUN_DB_TESTS set değil — canlı DB testleri atlanıyor.",
                allow_module_level=True)


def test_rls_isolation():
    from scripts.verify_rls import main
    assert asyncio.run(main()) == 0


def test_crypto_shredding_lifecycle():
    from cryptography.exceptions import InvalidTag
    from services.key_manager import get_tenant_dek, destroy_tenant_dek, _DEK_CACHE
    from services.encryption import encrypt_bytes, decrypt_bytes
    from api.db import service_session, close_pool

    TID = "33333333-3333-3333-3333-333333333333"

    async def run():
        async with service_session() as c:
            await c.execute("DELETE FROM tenants WHERE id=$1", TID)
            await c.execute("INSERT INTO tenants (id,name,slug) VALUES ($1,'Enc T','enc-t')", TID)
        dek1 = await get_tenant_dek(TID)
        ct, iv = encrypt_bytes(b"gizli", TID, dek1)
        assert decrypt_bytes(ct, iv, TID, dek1) == b"gizli"

        _DEK_CACHE.clear()
        assert await get_tenant_dek(TID) == dek1, "wrapped DEK DB-kalici olmali"

        assert await destroy_tenant_dek(TID) is True
        dek3 = await get_tenant_dek(TID)
        assert dek3 != dek1
        with pytest.raises(InvalidTag):
            decrypt_bytes(ct, iv, TID, dek3)  # crypto-shred: cozulemez

        async with service_session() as c:
            await c.execute("DELETE FROM tenants WHERE id=$1", TID)
        await close_pool()

    asyncio.run(run())
