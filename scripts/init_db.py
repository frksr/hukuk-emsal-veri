"""Tüm DB migration'larını sırayla uygula.

Çalıştır:
  python scripts/init_db.py
  python scripts/init_db.py --reset          # tüm tabloları drop edip yeniden kur (DİKKAT)
  python scripts/init_db.py --local-roles    # 08_local_roles.sql'i de uygula (SADECE lokal dev)

DSN seçimi:
  Migration'lar tablo owner'ı / admin rolü ile koşmalıdır (app_user RLS'e tabi,
  DDL yetkisi yok). Öncelik sırası: ADMIN_DATABASE_URL > DATABASE_URL.
  Production'da ADMIN_DATABASE_URL'e provider'ın admin DSN'ini verin.

NOT: Lokal Docker'da infra/db/ klasörü docker-entrypoint-initdb.d'ye mount
edildiği için İLK kurulumda tüm .sql dosyaları otomatik uygulanır; bu script
yalnızca sonradan eklenen migration'lar, --reset veya production (managed
Postgres) için gerekir.
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
    "07_rls_hardening.sql",      # FORCE RLS + app_user/app_service rolleri
    # 08_local_roles.sql        → SADECE lokal dev (--local-roles flag'i ile)
    "09_rls_fix_recursion.sql",  # RLS infinite recursion düzeltmesi
    "10_saved_decisions.sql",
    "11_generated_documents.sql",
    "12_user_notes.sql",
    "13_usage_credits.sql",
    "14_reminders.sql",
    "15_history_pref.sql",
    "16_billing_profile.sql",
    "17_app_config.sql",
    "18_email_verification.sql",  # e-posta doğrulama (kod + link)
    "19_pgvector.sql",            # Önkoşul: Cloud SQL'de 'vector' eklentisi etkin olmalı
    "20_blog_articles.sql",
    "21_onboarding.sql",
    "22_nps_responses.sql",
    "23_reminder_retry.sql",
    "24_waitlist_crm.sql",
    "25_sablonlar_alarmlar.sql",  # dilekce_sablonlari tablosu (Şablonlar sekmesi)
]

# Lokal dev rol parolaları — production'da ASLA uygulanmaz.
LOCAL_ONLY_MIGRATION = "08_local_roles.sql"


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
    p.add_argument(
        "--local-roles", action="store_true",
        help="08_local_roles.sql'i de uygula (SADECE lokal dev — zayıf parolalar!)",
    )
    args = p.parse_args()

    dsn = os.environ.get("ADMIN_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        print("✗ ADMIN_DATABASE_URL veya DATABASE_URL env eksik.")
        sys.exit(1)
    if "app_user" in dsn or "app_service" in dsn:
        print("⚠ DSN app_user/app_service rolü içeriyor — migration'lar tablo OWNER")
        print("  rolü ister (lokal: 'hukuk', cloud: provider admin kullanıcısı).")
        print("  ADMIN_DATABASE_URL env'ine owner DSN'i verin.")

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

        migrations = list(MIGRATIONS)
        if args.local_roles:
            # 08, 07'nin oluşturduğu rollere parola atar → 07'den hemen sonra
            idx = migrations.index("07_rls_hardening.sql") + 1
            migrations.insert(idx, LOCAL_ONLY_MIGRATION)
            print("⚠ --local-roles: 08_local_roles.sql uygulanacak (lokal dev parolaları)")

        print("Migration'lar uygulanıyor:")
        ok = 0
        for m in migrations:
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

        print(f"\n✓ {ok}/{len(migrations)} migration uygulandı.")
        print()
        print("Sonraki adım: 'uvicorn api.main:app --reload --port 8000'")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
