"""Tüm DB migration'larını sırayla uygula.

Çalıştır:
  python scripts/init_db.py
  python scripts/init_db.py --reset    # tüm tabloları drop edip yeniden kur (DİKKAT)
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

MIGRATIONS = [
    "01_init.sql",
    "02_rls.sql",
    "03_seed.sql",
    "04_migration_002.sql",
    "05_migration_003.sql",
    "06_migration_004.sql",
    "10_saved_decisions.sql",
]


async def reset_database(conn: asyncpg.Connection):
    """Tüm tabloları drop et — DİKKAT, veri kaybı!"""
    print("⚠ Tüm public schema tablolarını drop ediyor...")
    await conn.execute("DROP SCHEMA IF EXISTS public CASCADE;")
    await conn.execute("CREATE SCHEMA public;")
    await conn.execute("GRANT ALL ON SCHEMA public TO public;")
    print("  ✓ Schema sıfırlandı.")


async def apply_migration(conn: asyncpg.Connection, filename: str) -> bool:
    path = Path(__file__).parent.parent / "infra" / "db" / filename
    if not path.exists():
        print(f"  ✗ Dosya yok: {path}")
        return False

    sql = path.read_text(encoding="utf-8")
    try:
        # Birden çok statement'ı destekle
        await conn.execute(sql)
        print(f"  ✓ {filename}")
        return True
    except asyncpg.exceptions.DuplicateObjectError as e:
        # Zaten varsa OK
        print(f"  ⊙ {filename} — bazı objeler zaten var (atlandı)")
        return True
    except Exception as e:
        print(f"  ✗ {filename} HATA: {e}")
        return False


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true", help="Tüm tabloları drop et (DİKKAT)")
    args = p.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("✗ DATABASE_URL env eksik. .env dosyasını kontrol et.")
        sys.exit(1)

    print("=" * 60)
    print("  Hukuk Emsal — DB Migration")
    print("=" * 60)
    print(f"  DSN: {dsn.split('@')[1] if '@' in dsn else dsn}")
    print()

    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        print(f"✗ Postgres'e bağlanılamadı: {e}")
        print("  Docker Postgres çalışıyor mu? 'docker compose up -d postgres'")
        sys.exit(1)

    try:
        if args.reset:
            confirm = input("⚠ TÜM VERİ SİLİNECEK. Devam? (yazın: SIL): ")
            if confirm == "SIL":
                await reset_database(conn)
            else:
                print("İptal edildi.")
                return

        print("Migration'lar uygulanıyor:")
        ok = 0
        for m in MIGRATIONS:
            if await apply_migration(conn, m):
                ok += 1

        # Şema doğrulama
        print("\n→ Şema doğrulama:")
        tables = await conn.fetch(
            """SELECT table_name FROM information_schema.tables
               WHERE table_schema = 'public' ORDER BY table_name"""
        )
        for t in tables:
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {t['table_name']}"
            )
            print(f"  ✓ {t['table_name']} ({count} satır)")

        print(f"\n✓ {ok}/{len(MIGRATIONS)} migration uygulandı.")
        print()
        print("Sonraki adım: 'uvicorn api.main:app --reload --port 8000'")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
