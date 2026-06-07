# Faz 1 — Auth + Multi-Tenancy Altyapısı (DURUM)

## Tamamlanan dosyalar

### Veritabanı şeması
- `infra/db/01_init.sql` — Users, tenants, members, sessions, documents, usage_events, audit_log
- `infra/db/02_rls.sql` — Row-Level Security policies (tenant izolasyonu)
- `infra/db/03_seed.sql` — Development seed

### Backend (FastAPI)
- `api/db.py` — Postgres pool + tenant context manager
- `api/auth.py` — JWT verify + `get_current_user`, `require_plan`, `require_uyap` dependencies
- `api/rate_limit.py` — Tier bazlı günlük limit + usage_events log
- `api/routers/me.py` — `/api/me`, `/api/me/usage`, `/api/me/tenants`, `/api/me/searches`
- `api/main.py` — Lifespan'e DB pool eklendi, `me` router kaydedildi

### Frontend (Next.js + NextAuth.js v5)
- `web/lib/auth/config.ts` — NextAuth configuration
- `web/lib/auth/db.ts` — Postgres queries (getUserByEmail, authenticateUser, createUser)
- `web/auth.ts` — NextAuth handlers export
- `web/middleware.ts` — Route protection (/app/* → giriş gerekli)
- `web/app/api/auth/[...nextauth]/route.ts` — Auth route handler
- `web/app/api/auth/register/route.ts` — Kayıt endpoint'i
- `web/app/giris/` — Login sayfası + form
- `web/app/kayit/` — Register sayfası + form (KVKK onayı dahil)
- `web/app/hosgeldin/` — Onboarding success
- `web/app/app/layout.tsx` — Pro dashboard layout (auth required)
- `web/app/app/_sidebar.tsx` — Dashboard sidebar
- `web/app/app/page.tsx` — Dashboard ana sayfa

### Konfigürasyon
- `web/.env.local.example` — NEXTAUTH_SECRET, DATABASE_URL, SENTRY_DSN
- `web/package.json` — next-auth, pg, bcrypt eklendi
- `requirements.txt` — asyncpg, pyjwt, bcrypt, sentry-sdk eklendi

## Tier sistemi (kod içinde tanımlı)

```
anonim   → 20 emsal, 3 dilekçe, hesaplayıcılar sınırsız
free     → 40 emsal, 6 dilekçe (anonim x2)
pro_solo → sınırsız (UYAP yok)
pro_solo_uyap → sınırsız + 50 UYAP dosya / 200 sorgu/ay
team     → 5 kullanıcı, sınırsız
team_uyap → 5 kullanıcı + 250 dosya / 1000 sorgu/ay
enterprise → sınırsız UYAP dahil
```

## Sonraki adımlar — sen deploy yaparken ben paralel yapacaklar

1. **Mevcut router'larda rate_limit'i aktive et** — `Depends(rate_limit_for("arama"))` ekle
2. **Audit log middleware** — başarılı/başarısız işlemleri logla
3. **Email verification** akışı (opsiyonel ilk faz için)
4. **Password reset** akışı
5. **Abonelik sayfası** — `/app/ayarlar/abonelik` (iyzico entegrasyonu)

## DB kurulum (sen veya ben)

Postgres'i hazır olduğunda:

```bash
psql $DATABASE_URL -f infra/db/01_init.sql
psql $DATABASE_URL -f infra/db/02_rls.sql
psql $DATABASE_URL -f infra/db/03_seed.sql
```

Local development için Docker:
```bash
docker run -d --name hukuk-pg \
  -e POSTGRES_USER=hukuk \
  -e POSTGRES_PASSWORD=devpass \
  -e POSTGRES_DB=hukuk_emsal \
  -p 5432:5432 \
  postgres:16

# DATABASE_URL=postgresql://hukuk:devpass@localhost:5432/hukuk_emsal
```

## Hâlâ eksik (Faz 1 final için)

- [ ] Email verification (SMTP)
- [ ] Password reset flow
- [ ] iyzico billing entegrasyonu (Faz 2)
- [ ] Tenant invite flow (Team plan)
- [ ] Audit log UI (sadece admin için)
- [ ] User → admin upgrade flow
- [ ] Rate limit Redis backend (yüksek trafikte)
