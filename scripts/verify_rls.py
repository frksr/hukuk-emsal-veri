"""RLS tenant izolasyonu canlı doğrulama (local Docker Postgres'e karşı).

Çalıştır:
    python -m scripts.verify_rls

İki rol kullanır:
    app_user    (NOBYPASSRLS) → RLS'e tabi; tenant context set_config ile verilir.
    app_service (BYPASSRLS)    → kurulum verisini cross-tenant yazar.

Doğrulananlar:
    1) Context=A iken yalnızca A'nın dokümanları görünür.
    2) Context=B iken yalnızca B'nin dokümanları görünür.
    3) Context YOK iken hiçbir doküman görünmez (RLS blokluyor).
    4) Context=A iken B için INSERT reddedilir (WITH CHECK).
    5) tenant_members alt-sorgusu sonsuz döngüye girmiyor.
"""
from __future__ import annotations
import asyncio
import os

import asyncpg

APP_USER_DSN = os.environ.get(
    "APP_USER_DSN", "postgresql://app_user:app_user_pw@localhost:5432/hukuk_emsal")
SERVICE_DSN = os.environ.get(
    "SERVICE_DSN", "postgresql://app_service:app_service_pw@localhost:5432/hukuk_emsal")

TA = "11111111-1111-1111-1111-111111111111"  # tenant A
TB = "22222222-2222-2222-2222-222222222222"  # tenant B
UA = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"  # user A (member of A)
UB = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"  # user B (member of B)

PASS, FAIL = "✅ PASS", "❌ FAIL"
results: list[tuple[bool, str]] = []


def check(cond: bool, label: str):
    results.append((cond, label))
    print(f"  {PASS if cond else FAIL}  {label}")


async def setup(svc: asyncpg.Connection):
    # Temizle (idempotent)
    await svc.execute("DELETE FROM tenant_documents WHERE tenant_id = ANY($1::uuid[])", [TA, TB])
    await svc.execute("DELETE FROM tenant_members WHERE tenant_id = ANY($1::uuid[])", [TA, TB])
    await svc.execute("DELETE FROM tenants WHERE id = ANY($1::uuid[])", [TA, TB])
    await svc.execute("DELETE FROM users WHERE id = ANY($1::uuid[])", [UA, UB])

    await svc.execute(
        "INSERT INTO tenants (id, name, slug) VALUES ($1,'Tenant A','rls-a'),($2,'Tenant B','rls-b')",
        TA, TB)
    await svc.execute(
        "INSERT INTO users (id, email, name) VALUES ($1,'rls-a@test.local','A'),($2,'rls-b@test.local','B')",
        UA, UB)
    await svc.execute(
        "INSERT INTO tenant_members (tenant_id, user_id, role) VALUES ($1,$2,'owner'),($3,$4,'owner')",
        TA, UA, TB, UB)
    await svc.execute(
        "INSERT INTO tenant_documents (tenant_id, uploaded_by, title) VALUES ($1,$2,'A-DOC'),($3,$4,'B-DOC')",
        TA, UA, TB, UB)


async def as_user(conn: asyncpg.Connection, user_id: str | None):
    """Context'li sorgu — db_session ile aynı mantık (transaction + set_config)."""
    async with conn.transaction():
        if user_id:
            await conn.execute("SELECT set_config('app.current_user_id', $1, true)", user_id)
        rows = await conn.fetch("SELECT title FROM tenant_documents ORDER BY title")
        return [r["title"] for r in rows]


async def main():
    svc = await asyncpg.connect(SERVICE_DSN)
    usr = await asyncpg.connect(APP_USER_DSN)
    try:
        await setup(svc)

        # 1) Context = A
        titles_a = await as_user(usr, UA)
        check(titles_a == ["A-DOC"], f"Context=A yalnızca A-DOC görür (görülen: {titles_a})")

        # 2) Context = B
        titles_b = await as_user(usr, UB)
        check(titles_b == ["B-DOC"], f"Context=B yalnızca B-DOC görür (görülen: {titles_b})")

        # 3) Context YOK
        titles_none = await as_user(usr, None)
        check(titles_none == [], f"Context yok → 0 doküman (görülen: {titles_none})")

        # 4) Context=A iken B için INSERT reddedilmeli
        insert_blocked = False
        try:
            async with usr.transaction():
                await usr.execute("SELECT set_config('app.current_user_id', $1, true)", UA)
                await usr.execute(
                    "INSERT INTO tenant_documents (tenant_id, uploaded_by, title) VALUES ($1,$2,'HACK')",
                    TB, UA)
        except asyncpg.PostgresError:
            insert_blocked = True
        check(insert_blocked, "Context=A iken B-tenant'a INSERT RLS ile reddedildi")

        # 4b) Sızıntı kontrolü: HACK dokümanı oluşmadı mı? (service ile bak)
        hack = await svc.fetchval("SELECT COUNT(*) FROM tenant_documents WHERE title='HACK'")
        check(hack == 0, f"Cross-tenant INSERT veri yazmadı (HACK sayısı: {hack})")

        # 5) Service (BYPASSRLS) hepsini görür
        all_titles = [r["title"] for r in await svc.fetch(
            "SELECT title FROM tenant_documents WHERE tenant_id = ANY($1::uuid[]) ORDER BY title", [TA, TB])]
        check(all_titles == ["A-DOC", "B-DOC"], f"Service tüm tenant'ları görür (görülen: {all_titles})")

        # temizlik
        await svc.execute("DELETE FROM tenant_documents WHERE tenant_id = ANY($1::uuid[])", [TA, TB])
        await svc.execute("DELETE FROM tenant_members WHERE tenant_id = ANY($1::uuid[])", [TA, TB])
        await svc.execute("DELETE FROM tenants WHERE id = ANY($1::uuid[])", [TA, TB])
        await svc.execute("DELETE FROM users WHERE id = ANY($1::uuid[])", [UA, UB])
    finally:
        await svc.close()
        await usr.close()

    ok = sum(1 for c, _ in results if c)
    print(f"\n{ok}/{len(results)} kontrol geçti")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
