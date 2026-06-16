# Lokal Test → Production Geçiş Rehberi

> Güncelleme: 2026-06-12. Bu doküman, lokalde uçtan uca test ve ardından production'a
> çıkış için **tek referans noktasıdır**. Detay gereken yerlerde mevcut dokümanlara
> (SETUP_LOCAL.md, TEST_PLAN.md, DEPLOY_PHASE0.md, DEPLOY_VOLUME.md) link verir.

## İçindekiler

1. [Mimari Özet](#1-mimari-özet)
2. [Bu Revizyonla Yapılan Düzeltmeler](#2-bu-revizyonla-yapılan-düzeltmeler)
3. [BÖLÜM A — Lokal Test](#bölüm-a--lokal-test)
4. [BÖLÜM B — Production'a Geçiş](#bölüm-b--productiona-geçiş)
5. [Ortam Değişkenleri Referansı](#ortam-değişkenleri-referansı)
6. [Sorun Giderme](#sorun-giderme)

---

## 1. Mimari Özet

| Bileşen | Teknoloji | Lokal | Production |
|---|---|---|---|
| Backend API | FastAPI (`api/`) | `uvicorn` :8000 | Railway/Fly.io (Dockerfile) |
| Frontend | Next.js 14 (`web/`) | `npm run dev` :3000 | Vercel |
| Veritabanı | PostgreSQL 16 + RLS | docker-compose :5432 | Railway/Neon managed PG |
| Vektör DB | ChromaDB (~2 GB) | `data/chroma_db/` | Kalıcı volume `/data/chroma_db` |
| Karar metinleri | Parquet (~52 MB) | `data/final/all_decisions.parquet` | Volume `/data/final/...` |
| E-posta | SMTP | Mailpit (docker) :1026/:8025 | Resend / Postmark / SES |
| Ödeme | iyzico | Sandbox API | Production API |
| LLM | Anthropic / Gemini | API key | API key (ayrı prod key önerilir) |
| Streamlit (`app/`) | — | Legacy/dahili demo | **Deploy edilmez** |

Kritik güvenlik katmanı: Postgres **RLS** (tenant izolasyonu). Backend iki rolle bağlanır:
`app_user` (RLS'e tabi, `DATABASE_URL`) ve `app_service` (BYPASSRLS, `SERVICE_DATABASE_URL`).
Migration'lar ise tablo **owner** rolüyle koşar (`ADMIN_DATABASE_URL`).

## 2. Bu Revizyonla Yapılan Düzeltmeler

Analizde bulunan ve düzeltilen eksikler — eski talimatlarla çakışırsa **bu doküman geçerlidir**:

1. **`Dockerfile`** — `data/final/` ve `data/chroma_db/` `COPY` satırları kaldırıldı.
   `.dockerignore` bu yolları zaten hariç tutuyordu → **docker build her koşulda kırılıyordu**.
   Artık veri stratejisi tek: kalıcı volume + `scripts/seed_volume.py` (bkz. DEPLOY_VOLUME.md).
   Ayrıca `scripts/` image'a eklendi (migration/seed/admin scriptleri container içinde lazım).
2. **`scripts/init_db.py`** — migration listesinde `07_rls_hardening.sql` ve
   `09_rls_fix_recursion.sql` eksikti → `--reset` veya managed PG kurulumunda **RLS
   sertleştirmesi hiç uygulanmıyordu** (ciddi güvenlik açığı). Eklendi.
   `08_local_roles.sql` (zayıf dev parolaları) sadece `--local-roles` flag'i ile uygulanır.
   Script artık `ADMIN_DATABASE_URL`'i tercih eder ve `app_user`/`app_service` DSN'i
   görürse uyarır.
3. **`.env.example`** — `ADMIN_DATABASE_URL` eklendi.
4. **`web/.env.local.example`** — zorunlu olduğu halde eksik olan `NEXTAUTH_URL`,
   `NEXTAUTH_SECRET`, `DATABASE_URL` eklendi.

---

# BÖLÜM A — Lokal Test

## A.1 Ön Koşullar

- Docker Desktop (çalışır durumda)
- Python 3.11+
- Node.js 18+
- `data/chroma_db/` ve `data/final/all_decisions.parquet` mevcut (repo'da var, git'te değil)

## A.2 Ortam Dosyaları

```bash
# Repo kökünde
cp .env.example .env        # zaten varsa atla
cd web && cp .env.local.example .env.local && cd ..
```

`.env` içinde **mutlaka** doldurulması gerekenler (yoksa API açılmaz / istekler patlar):

| Değişken | Nasıl üretilir / değer |
|---|---|
| `DATABASE_URL` | `postgresql://app_user:app_user_pw@localhost:5432/hukuk_emsal` |
| `SERVICE_DATABASE_URL` | `postgresql://app_service:app_service_pw@localhost:5432/hukuk_emsal` |
| `ADMIN_DATABASE_URL` | `postgresql://hukuk:<POSTGRES_PASSWORD>@localhost:5432/hukuk_emsal` |
| `NEXTAUTH_SECRET` | `openssl rand -base64 32` — **web/.env.local ile birebir aynı olmalı** |
| `MASTER_ENCRYPTION_KEY` | `openssl rand -base64 32` — kaybolursa tenant verisi okunamaz |
| `ANTHROPIC_API_KEY` *veya* `GOOGLE_API_KEY` | LLM özellikleri için en az biri |

`web/.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8000`,
`NEXTAUTH_URL=http://localhost:3000`, `NEXTAUTH_SECRET` (backend ile aynı),
`DATABASE_URL` (owner rolü `hukuk` kullanılabilir).

## A.3 Altyapıyı Başlat (Postgres + Mailpit)

```bash
docker compose up -d
docker compose ps          # ikisi de "healthy"/"running" olmalı
```

- Postgres → `localhost:5432`
- Mailpit SMTP → `localhost:1026`, Web UI → http://localhost:8025

**İlk açılışta** `infra/db/*.sql` dosyalarının TAMAMI (01→10, RLS sertleştirme ve lokal
roller dahil) `docker-entrypoint-initdb.d` üzerinden alfabetik sırayla otomatik uygulanır.
`init_db.py` çalıştırmanıza gerek yok.

> Volume zaten varsa (eski kurulum) init script'leri ÇALIŞMAZ. Şemayı sıfırdan kurmak için:
> `docker compose down -v && docker compose up -d`
> veya mevcut veriyi koruyarak: `python scripts/init_db.py --local-roles`

## A.4 Backend

```bash
pip install -r requirements-dev.txt   # requirements.txt'i de içerir
uvicorn api.main:app --reload --port 8000
```

Doğrulama:

```bash
curl -s http://localhost:8000/api/health
# Beklenen: {"ok": true, ...} + rag/llm durum alanları
```

`rag` alanı boş/erişilemez görünüyorsa `data/chroma_db/` yolunu ve `CHROMA_DIR`'in lokalde
**boş bırakıldığını** kontrol edin (boşsa varsayılan `data/chroma_db` kullanılır).

## A.5 Admin Kullanıcı + iyzico Sandbox

```bash
python scripts/create_admin.py --email admin@hukukemsal.tr --password <parola> --name "Admin"

# iyzico sandbox plan/ürünlerini oluştur (IYZICO_API_KEY/SECRET sandbox değerleri .env'de olmalı)
python scripts/setup_iyzico_plans.py
# Çıktıdaki plan referans kodlarını .env'e yaz: IYZICO_PLAN_PRO_SOLO=... vb.
# NOT: Bu adım idempotent DEĞİL ve DB reset'te kaybolmaz ama .env'deki ID'ler sandbox'ta kalır.
```

## A.6 Frontend

```bash
cd web
npm install
npm run dev          # http://localhost:3000
```

Hızlı kontrol: `/giris` ile admin hesabına giriş → arama sayfasında bir emsal araması →
sonuç geliyor mu?

## A.7 Otomatik Testler

```bash
# Postgres ayakta olmalı (test_db_integration RLS testleri canlı DB ister)
python -m pytest tests/ -v

# RLS tenant izolasyonunu canlı doğrula (app_user/app_service rolleriyle)
python -m scripts.verify_rls

# Modül bütünlüğü (network gerektirmez)
python scripts/smoke_test.py
```

Frontend tarafı:

```bash
cd web && npm run lint && npm run type-check && npm run build
```

`npm run build`'in lokalde hatasız geçmesi, Vercel deploy'unun ön koşuludur.

## A.8 Fonksiyonel Test Turu

Tam liste **TEST_PLAN.md**'de (20 kategori). Production'a çıkmadan asgari tur:

1. Kayıt → doğrulama e-postası **Mailpit UI**'da (http://localhost:8025) görünüyor mu?
2. Giriş/çıkış, şifre sıfırlama akışı.
3. Emsal arama → sonuç → karar detay sayfası (`/karar/[id]`).
4. Dilekçe/ihtarname üretimi (LLM key'i ile) → Word export.
5. UYAP doküman yükleme → PII maskeleme çalışıyor mu?
6. Faiz hesaplayıcı + zamanaşımı modülleri.
7. Billing: sandbox kartla abonelik → webhook → planın aktifleşmesi.
8. Admin panel: kullanıcı listesi, metrikler.
9. İki ayrı tenant hesabıyla **çapraz veri erişimi DENENMELİ ve BAŞARISIZ olmalı** (RLS).
10. `python -m pytest tests/ -v` yeşil.

---

# BÖLÜM B — Production'a Geçiş

Hedef mimari (DEPLOY_PHASE0.md ile uyumlu): **Railway** (backend + Postgres) +
**Vercel** (frontend) + **Cloudflare** (DNS). Fly.io alternatifi için DEPLOY_VOLUME.md.

## B.0 Çıkış Öncesi Kontrol Listesi

- [ ] Bölüm A'daki tüm testler yeşil (özellikle A.7 + A.8 madde 9)
- [ ] `npm run build` lokalde hatasız
- [ ] `docker build -t hukuk-api .` lokalde hatasız (artık veri kopyalamadığı için hızlı)
- [ ] Tüm secret'lar **yeniden üretildi** (lokal değerler ASLA prod'a taşınmaz)
- [ ] `MASTER_ENCRYPTION_KEY` güvenli kasada (1Password/KMS) yedekli — kaybı = veri kaybı
- [ ] iyzico production sözleşmesi/key'leri hazır
- [ ] Domain + Cloudflare hesabı hazır

## B.1 Secret'ların Üretimi

```bash
openssl rand -base64 32   # NEXTAUTH_SECRET (prod)
openssl rand -base64 32   # MASTER_ENCRYPTION_KEY (prod) → kasaya yedekle!
```

Lokal `.env`'deki hiçbir parola/key prod'da kullanılmamalı. `08_local_roles.sql`
**production'da asla uygulanmaz** (init_db.py varsayılan olarak uygulamaz).

## B.2 Production Veritabanı

1. Railway'de PostgreSQL 16 servisi oluştur, admin DSN'ini al.
2. Migration'ları uygula (lokal makineden veya Railway shell'den):

```bash
ADMIN_DATABASE_URL="postgresql://postgres:...@.../railway" python scripts/init_db.py
# 01..07, 09, 10 uygulanır; 08 (lokal roller) uygulanmaz — doğru davranış.
```

3. Uygulama rollerine **güçlü** parolalar ata:

```sql
ALTER ROLE app_user    PASSWORD '<güçlü-parola-1>';
ALTER ROLE app_service PASSWORD '<güçlü-parola-2>';
```

4. Prod `DATABASE_URL` → `app_user`, `SERVICE_DATABASE_URL` → `app_service` DSN'leri.
5. Admin kullanıcı: `python scripts/create_admin.py --email ... --password ...`
   (env'de prod DSN'lerle).

## B.3 Backend Deploy (Railway)

1. GitHub repo'yu push'la, Railway'de "Deploy from GitHub" → Dockerfile otomatik algılanır.
2. **Kalıcı volume** ekle, mount path: `/data`.
3. Environment variables (tam liste aşağıdaki referans tabloda). Kritikler:

```
DATABASE_URL, SERVICE_DATABASE_URL          (B.2'deki prod DSN'ler)
NEXTAUTH_SECRET                             (prod değeri — Vercel ile aynı)
MASTER_ENCRYPTION_KEY                       (prod değeri)
ANTHROPIC_API_KEY / GOOGLE_API_KEY
APP_ENV=production
ALLOWED_ORIGINS=https://hukukemsal.tr,https://www.hukukemsal.tr
CHROMA_DIR=/data/chroma_db
DECISIONS_PARQUET=/data/final/all_decisions.parquet
TENANT_CHROMA_DIR=/data/tenant_chroma
TENANT_STORAGE_ROOT=/data/tenant_storage
SMTP_* (B.5), IYZICO_* (B.6), SENTRY_DSN (B.7), EVDS_API_KEY
```

4. **Veriyi volume'a seed et** (tek seferlik):

```bash
# Lokalde tarball hazırla
tar czf chroma_db.tgz -C data chroma_db
# R2/S3'e yükle, presigned URL al; sonra Railway shell'de:
CHROMA_DIR=/data/chroma_db python -m scripts.seed_volume --source "https://<presigned-url>/chroma_db.tgz"
# Parquet'i de kopyala (küçük; aynı yöntem veya scp/railway cp)
# Hedef: /data/final/all_decisions.parquet
```

Script idempotenttir; volume doluysa atlar. Detay: DEPLOY_VOLUME.md.

5. Servisi yeniden başlat → `https://<railway-url>/api/health` → `"ok": true` ve `rag`
   alanında koleksiyon istatistikleri dolu olmalı.

## B.4 Frontend Deploy (Vercel)

1. Vercel'de projeyi import et (repo kökü; `vercel.json` build'i `web/`'e yönlendirir).
2. Environment variables:

```
NEXT_PUBLIC_API_URL=https://api.hukukemsal.tr   (veya Railway URL'i)
NEXT_PUBLIC_SITE_URL=https://hukukemsal.tr
NEXTAUTH_URL=https://hukukemsal.tr
NEXTAUTH_SECRET=<backend ile AYNI prod değeri>
DATABASE_URL=<prod app_user DSN — NextAuth kullanıcı sorguları için>
API_INTERNAL_URL=<backend iç URL — SSR karar sayfaları>
```

3. Deploy → build log'da `next-sitemap` postbuild adımının geçtiğini doğrula.

## B.5 DNS + E-posta

1. Cloudflare DNS: `hukukemsal.tr` → Vercel, `api.hukukemsal.tr` → Railway
   (CNAME; adım adım DEPLOY_PHASE0.md §DNS).
2. SMTP sağlayıcı (Resend/Postmark/SES): domain doğrulama (SPF + DKIM + DMARC kayıtları),
   sonra Railway env: `SMTP_HOST/PORT/USER/PASS`, `SMTP_FROM=noreply@hukukemsal.tr`.
3. Test: prod'da kayıt ol → e-posta gerçekten geliyor mu, spam'e düşüyor mu?

## B.6 iyzico Production

1. Production API key/secret → Railway env (`IYZICO_BASE_URL=https://api.iyzipay.com`).
2. Production planlarını oluştur: `python scripts/setup_iyzico_plans.py` (prod key'lerle)
   → çıkan plan kodlarını `IYZICO_PLAN_*` env'lerine yaz.
3. iyzico panelinde webhook URL'i: `https://api.hukukemsal.tr/api/billing/webhook`
   ve `IYZICO_WEBHOOK_SECRET`'ı env'e ekle.
4. Düşük tutarlı gerçek kartla bir abonelik testi + iade.

## B.7 Observability + Operasyon

- **Sentry**: backend `SENTRY_DSN` + `SENTRY_TRACES_SAMPLE_RATE=0.1`; web için
  `NEXT_PUBLIC_SENTRY_DSN` (opsiyonel).
- **Uptime**: UptimeRobot/BetterStack → `https://api.hukukemsal.tr/api/health` (1 dk).
- **DB yedek**: Railway otomatik backup'ı aç + haftalık `pg_dump` harici kopya.
- **Volume yedek**: chroma tarball'ı zaten R2/S3'te; tenant verisi için periyodik snapshot.
- **Cron job'lar** (Railway cron veya scheduler):
  - `python scripts/emsal_alarm_job.py` — günlük (emsal alarmları)
  - `python scripts/update_faiz_oranlari.py --evds` — günlük/haftalık (EVDS_API_KEY ile)

## B.8 Go-Live Smoke Testi

Sırayla, hepsi prod URL'lerde:

1. `curl https://api.hukukemsal.tr/api/health` → ok + rag dolu.
2. https://hukukemsal.tr açılıyor, statik sayfalar ve `/karar/[id]` SSR çalışıyor.
3. Kayıt → e-posta → doğrulama → giriş.
4. Emsal arama → sonuç → detay.
5. Dilekçe üretimi (LLM prod key) → Word export indirilebiliyor.
6. Abonelik satın alma (test) → webhook → plan aktif.
7. İkinci hesapla çapraz tenant erişim denemesi → **reddedilmeli**.
8. Sentry'de test hatası görünüyor mu? (`/api/health`'e kasıtlı bozuk istek vb.)
9. CORS: farklı origin'den istek reddediliyor mu?

## B.9 Geri Dönüş (Rollback) Planı

- Vercel: önceki deployment'a "Promote" (saniyeler).
- Railway: önceki image'a redeploy; migration geri alma gerekiyorsa `pg_dump` yedeğinden restore.
- Veri bozulması şüphesinde: volume'u read-only alıp tarball yedeğinden yeni volume seed'le.

---

## Ortam Değişkenleri Referansı

| Değişken | Lokal | Production | Zorunlu |
|---|---|---|---|
| `DATABASE_URL` | app_user@localhost | app_user@railway | ✅ (yoksa API açılmaz) |
| `SERVICE_DATABASE_URL` | app_service@localhost | app_service@railway | ✅ (yoksa RLS 2. katman pasif) |
| `ADMIN_DATABASE_URL` | hukuk@localhost | admin DSN (sadece migration) | migration için |
| `NEXTAUTH_SECRET` | dev değeri | prod değeri (web+api AYNI) | ✅ |
| `MASTER_ENCRYPTION_KEY` | dev değeri | prod değeri (kasada yedekli) | ✅ |
| `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | en az biri | en az biri (prod key) | LLM için ✅ |
| `APP_ENV` | development | production | önerilir |
| `ALLOWED_ORIGINS` | localhost:3000 | prod domainler | prod'da ✅ |
| `CHROMA_DIR` | (boş → data/chroma_db) | /data/chroma_db | prod'da ✅ |
| `DECISIONS_PARQUET` | (boş) | /data/final/all_decisions.parquet | prod'da ✅ |
| `TENANT_CHROMA_DIR` | (boş) | /data/tenant_chroma | prod'da ✅ |
| `TENANT_STORAGE_ROOT` | data/tenant_storage | /data/tenant_storage | ✅ |
| `SMTP_HOST/PORT/USER/PASS/FROM` | localhost:1026 (Mailpit) | Resend/Postmark/SES | ✅ |
| `IYZICO_*` | sandbox | production + webhook secret | billing için ✅ |
| `SENTRY_DSN` | boş | dolu | önerilir |
| `EVDS_API_KEY` | opsiyonel | dolu (faiz otomasyonu) | önerilir |
| `PII_NER_MODEL` | default | default | opsiyonel |
| `PII_BLOCK_FOREIGN_LLM_WITHOUT_NER` | 0 | **1 önerilir** (KVKK) | opsiyonel |
| Web: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SITE_URL`, `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, `DATABASE_URL`, `API_INTERNAL_URL` | lokal değerler | prod değerler | ✅ |

## Sorun Giderme

| Belirti | Muhtemel neden / çözüm |
|---|---|
| API açılışta `RuntimeError: DATABASE_URL ... yok` | `.env` yüklenmemiş; uvicorn'u repo kökünden çalıştırın |
| Açılışta encryption hatası | `MASTER_ENCRYPTION_KEY` boş — üretin ve `.env`'e yazın |
| Login 401 / JWT decode hatası | Backend ve web `NEXTAUTH_SECRET` değerleri farklı |
| `/api/health`'te `rag` boş | `CHROMA_DIR` yanlış / volume seed edilmemiş → `scripts/seed_volume.py` |
| `infinite recursion detected in policy` | Migration 09 uygulanmamış → `python scripts/init_db.py` |
| RLS hiç engellenmiyor | `DATABASE_URL` owner/superuser ile bağlanıyor → app_user DSN kullanın |
| Docker build `COPY data/...` hatası | Eski Dockerfile — güncel sürümde veri COPY'si yok, `git pull` |
| Mailpit'e mail düşmüyor | `SMTP_PORT=1026` (1025 değil — host port mapping) |
| Vercel build OK ama login patlıyor | Vercel'de `DATABASE_URL`/`NEXTAUTH_SECRET` env eksik |
| `docker compose up` şemayı kurmadı | Eski volume var → `docker compose down -v` veya `init_db.py --local-roles` |

## Önerilen Sonraki Adımlar (opsiyonel, bloker değil)

1. **CI**: GitHub Actions — push'ta `pytest` + `npm run build` (repo'da henüz workflow yok).
2. iyzico plan ID'lerini env yerine DB config tablosunda tutmak (reset dayanıklılığı).
3. `MASTER_ENCRYPTION_KEY`'i KMS'e taşımak (kod zaten "production'da KMS" notu içeriyor).
4. Staging ortamı (Railway'de ikinci servis + Vercel preview).
