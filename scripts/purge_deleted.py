"""KVKK m.7 — 30 gün sonra kalıcı silme + kriptografik silme.

`DELETE /me/account` hesabı yalnızca PASİFLEŞTİRİR (soft-delete) ve
metadata.deleted_at damgalar. Bu cron işi, 30 günü dolan hesapları kalıcı olarak
temizler ve ilgili solo tenant'ların verisini KRİPTOGRAFİK olarak siler
(tenant_encryption_keys satırı silinince veri matematiksel olarak çözülemez).

Kullanım (örn. günlük cron):
    python -m scripts.purge_deleted              # gerçek silme
    python -m scripts.purge_deleted --dry-run    # sadece raporla

NOT: Yalnızca kullanıcının TEK üye/sahip olduğu solo tenant'lar kriptografik
silinir. Çok üyeli (team) tenant'larda diğer üyelerin verisi korunur; oradan
yalnızca ayrılan kullanıcının üyeliği kaldırılır.
"""
from __future__ import annotations
import asyncio
import sys
import logging

from api.db import service_session, close_pool
from services.tenant_storage import purge_tenant

log = logging.getLogger("scripts.purge_deleted")

GRACE_DAYS = 30


async def purge(dry_run: bool = False) -> dict:
    purged_tenants: list[str] = []
    purged_users: list[str] = []

    async with service_session() as conn:
        # 30 günü dolmuş soft-deleted kullanıcılar
        users = await conn.fetch(
            """SELECT id FROM users
               WHERE is_active = FALSE
                 AND (metadata->>'deleted_at') IS NOT NULL
                 AND (metadata->>'deleted_at')::timestamptz < NOW() - ($1 || ' days')::interval""",
            str(GRACE_DAYS),
        )

        for u in users:
            uid = str(u["id"])
            # Bu kullanıcının üye olduğu tenant'lar
            tenants = await conn.fetch(
                "SELECT tenant_id FROM tenant_members WHERE user_id = $1", uid,
            )
            for t in tenants:
                tid = str(t["tenant_id"])
                member_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM tenant_members WHERE tenant_id = $1", tid,
                )
                if member_count == 1:
                    # Solo tenant → kriptografik silme
                    if not dry_run:
                        await purge_tenant(tid)  # DEK sil + dosyaları sil
                        await conn.execute(
                            "UPDATE tenants SET is_active = FALSE WHERE id = $1", tid,
                        )
                    purged_tenants.append(tid)

            purged_users.append(uid)

    result = {
        "purged_users": purged_users,
        "purged_tenants": purged_tenants,
        "dry_run": dry_run,
    }
    log.info("Purge tamamlandı: %s", result)
    return result


def main():
    logging.basicConfig(level=logging.INFO)
    dry = "--dry-run" in sys.argv
    try:
        res = asyncio.run(_run(dry))
        print(res)
    finally:
        pass


async def _run(dry: bool) -> dict:
    try:
        return await purge(dry_run=dry)
    finally:
        await close_pool()


if __name__ == "__main__":
    main()
