"""Admin kullanıcı oluştur veya mevcut kullanıcıyı admin'e çevir.

Çalıştır:
  python scripts/create_admin.py --email admin@hukukcuyapayzekasi.com --password yourpass --name "Sen"
  python scripts/create_admin.py --promote your@email.com    # mevcut user'ı admin yap
"""
from __future__ import annotations
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import asyncpg
import bcrypt


async def create_admin(conn, email: str, password: str, name: str):
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

    # User var mı?
    existing = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
    if existing:
        # Mevcut user'ı admin'e çevir + şifre güncelle
        await conn.execute(
            """UPDATE users SET role = 'admin', password_hash = $1,
               email_verified = COALESCE(email_verified, NOW()),
               is_active = TRUE
               WHERE id = $2""",
            pw_hash, existing,
        )
        print(f"✓ Mevcut kullanıcı admin'e güncellendi: {email}")
        return existing

    user_id = await conn.fetchval(
        """INSERT INTO users (email, name, password_hash, role,
                              email_verified, kvkk_accepted_at)
           VALUES ($1, $2, $3, 'admin', NOW(), NOW())
           RETURNING id""",
        email.lower(), name, pw_hash,
    )

    # Otomatik enterprise tenant ekle
    tenant_id = await conn.fetchval(
        """INSERT INTO tenants (name, slug, type, plan_tier, max_users,
                                max_uyap_documents, max_monthly_queries)
           VALUES ($1, $2, 'enterprise', 'enterprise', 50, 100000, 100000)
           RETURNING id""",
        f"{name} - Admin Workspace",
        f"admin-{str(user_id)[:8]}",
    )

    await conn.execute(
        """INSERT INTO tenant_members (tenant_id, user_id, role, accepted_at)
           VALUES ($1, $2, 'owner', NOW())""",
        tenant_id, user_id,
    )

    print(f"✓ Admin oluşturuldu: {email}")
    print(f"  User ID: {user_id}")
    print(f"  Tenant ID: {tenant_id} (Enterprise plan)")
    return user_id


async def promote(conn, email: str):
    result = await conn.execute(
        "UPDATE users SET role = 'admin' WHERE email = $1", email,
    )
    if "1" in result:
        print(f"✓ {email} admin'e çevrildi.")
    else:
        print(f"✗ {email} bulunamadı.")


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--email")
    p.add_argument("--password")
    p.add_argument("--name", default="Sistem Yöneticisi")
    p.add_argument("--promote", help="Mevcut user'ı admin yap (sadece email)")
    args = p.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("✗ DATABASE_URL env eksik.")
        sys.exit(1)

    conn = await asyncpg.connect(dsn)
    try:
        if args.promote:
            await promote(conn, args.promote)
        elif args.email and args.password:
            await create_admin(conn, args.email, args.password, args.name)
        else:
            print("Kullanım:")
            print("  python scripts/create_admin.py --email X --password Y --name Z")
            print("  python scripts/create_admin.py --promote your@email.com")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
