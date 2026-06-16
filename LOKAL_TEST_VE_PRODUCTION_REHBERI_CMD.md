# Lokal Test → Production Geçiş Rehberi (Windows CMD)

> Güncelleme: 2026-06-13. Bu sürüm, tüm komutları **Windows CMD (komut istemi)** için yazar
> ve lokal portları **8000→8010 (backend)**, **3000→3010 (frontend)** olarak değiştirir
> (8000 ve 3000'de başka projeler çalıştığı için). Postgres `5432`, Mailpit `1026/8025`
> değişmez — bunlar 8000/3000 ile çakışmaz.
>
> Detay gereken yerlerde mevcut dokümanlara (SETUP_LOCAL.md, TEST_PLAN.md, DEPLOY_PHASE0.md,
> DEPLOY_VOLUME.md) bakın.

## Port Haritası (bu sürüm)

| Servis | Eski port | Bu sürümde |
|---|---|---|
| Backend API (uvicorn) | 8000 | **8010** |
| Frontend (Next.js) | 3000 | **3010** |
| PostgreSQL | 5432 | 5432 (değişmedi) |
| Mailpit SMTP | 1026 | 1026 (değişmedi) |
| Mailpit Web UI | 8025 | 8025 (değişmedi) |

> Not: Backend ve frontend doğrudan çalıştırıldığı için (docker değil) portu sadece çalıştırma
> komutunda değiştirmek yeterli. Ancak portu değiştirdiğinde **birbirine bakan env değerlerini**
> de güncellemen şart: `NEXT_PUBLIC_API_URL` → 8010, `NEXTAUTH_URL` / `NEXT_PUBLIC_SITE_URL` → 3010,
> ve backend `.env` içindeki `ALLOWED_ORIGINS` → `http://localhost:3010` içermeli.

## İçindekiler
1. [Mimari Özet](#1-mimari-özet)
2. [BÖLÜM A — Lokal Test](#bölüm-a--lokal-test)
3. [BÖLÜM B — Production'a Geçiş](#bölüm-b--productiona-geçiş)
4. [Ortam Değişkenleri Referansı](#ortam-değişkenleri-referansı)
5. [Sorun Giderme](#sorun-giderme)

---

## 1. Mimari Özet

| Bileşen | Teknoloji | Lokal | Production |
|---|---|---|---|
| Backend API | FastAPI (`api/`) | `uvicorn` :8010 | Railway/Fly.io (Dockerfile) |
| Frontend | Next.js 14 (`web/`) | `npm run dev -- -p 3010` :3010 | Vercel |
| Veritabanı | PostgreSQL 16 + RLS | docker-compose :5432 | Railway/Neon managed PG |
| Vektör DB | ChromaDB (~2 GB) | `data\chroma_db\` | Kalıcı volume `/data/chroma_db` |
| Karar metinleri | Parquet (~52 MB) | `data\final\all_decisions.parquet` | Volume `/data/final/...` |
| E-posta | SMTP | Mailpit (docker) :1026/:8025 | Resend / Postmark / SES |
| Ödeme | iyzico | Sandbox API | Production API |
| LLM | Anthropic / Gemini | API key | API key (ayrı prod key önerilir) |
| Streamlit (`app/`) | — | Legacy/dahili demo | **Deploy edilmez** |

Kritik güvenlik katmanı: Postgres **RLS** (tenant izolasyonu). Backend iki rolle bağlanır:
`app_user` (RLS'e tabi, `DATABASE_URL`) ve `app_service` (BYPASSRLS, `SERVICE_DATABASE_URL`).
Migration'lar ise tablo **owner** rolüyle koşar (`ADMIN_DATABASE_URL`).

> CMD ipuçları: CMD'de değişken atama `set "VAR=deger"` ile yapılır (PowerShell değil).
> Satır içi `VAR=deger komut` sözdizimi **CMD'de çalışmaz** — önce `set`, sonra komut.
> Dosya kopyalama `copy`, klasör değiştirme `cd`. `&&` zincirleme CMD'de de geçerlidir.

---

# BÖLÜM A — Lokal Test

## A.1 Ön Koşullar
- Docker Desktop (çalışır durumda)
- Python 3.11+  (`py --version` veya `python --version`)
- Node.js 18+   (`node --version`)
- `data\chroma_db\` ve `data\final\all_decisions.parquet` mevcut (repo'da var, git'te değil)

## A.2 Ortam Dosyaları

```bat
REM Repo kökünde
copy .env.example .env
cd web && copy .env.local.example .env.local && cd ..
```

`.env` içinde **mutlaka** doldurulması gerekenler:

| Değişken | Değer |
|---|---|
| `DATABASE_URL` | `postgresql://app_user:app_user_pw@localhost:5432/hukuk_emsal` |
| `SERVICE_DATABASE_URL` | `postgresql://app_service:app_service_pw@localhost:5432/hukuk_emsal` |
| `ADMIN_DATABASE_URL` | `postgresql://hukuk:<POSTGRES_PASSWORD>@localhost:5432/hukuk_emsal` |
| `NEXTAUTH_SECRET` | aşağıdaki komutla üret — **web\.env.local ile birebir aynı olmalı** |
| `MASTER_ENCRYPTION_KEY` | aşağıdaki komutla üret — kaybolursa tenant verisi okunamaz |
| `ANTHROPIC_API_KEY` *veya* `GOOGLE_API_KEY` | LLM özellikleri için en az biri |
| `ALLOWED_ORIGINS` | **`http://localhost:3010,http://127.0.0.1:3010`** (yeni frontend portu!) |

Secret üretimi (CMD — kriptografik olarak güvenli, PowerShell çağrısıyla):

```bat
REM NEXTAUTH_SECRET için:
powershell -Command "$b=New-Object byte[] 32;[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b);[Convert]::ToBase64String($b)"

REM MASTER_ENCRYPTION_KEY için (tekrar çalıştır, ayrı değer):
powershell -Command "$b=New-Object byte[] 32;[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b);[Convert]::ToBase64String($b)"
```

> Git for Windows kuruluysa `openssl rand -base64 32` de çalışır; yukarıdaki PowerShell
> yöntemi hiçbir ek kuruluma ihtiyaç duymadan çalışır.

`web\.env.local` (yeni portlarla):

```
NEXT_PUBLIC_API_URL=http://localhost:8010
NEXT_PUBLIC_SITE_URL=http://localhost:3010
NEXTAUTH_URL=http://localhost:3010
NEXTAUTH_SECRET=<backend .env ile AYNI değer>
DATABASE_URL=postgresql://hukuk:<POSTGRES_PASSWORD>@localhost:5432/hukuk_emsal
```

## A.3 Altyapıyı Başlat (Postgres + Mailpit)

```bat
docker compose up -d
docker compose ps
```

- Postgres → `localhost:5432`
- Mailpit SMTP → `localhost:1026`, Web UI → http://localhost:8025

**İlk açılışta** `infra\db\*.sql` dosyalarının TAMAMI (01→10) otomatik uygulanır;
`init_db.py` çalıştırmana gerek yok.

> Volume zaten varsa init script'leri ÇALIŞMAZ. Şemayı sıfırdan kurmak için:
> ```bat
> docker compose down -v && docker compose up -d
> ```
> veya mevcut veriyi koruyarak:
> ```bat
> python scripts\init_db.py --local-roles
> ```

## A.4 Backend (port 8010)

```bat
pip install -r requirements-dev.txt
uvicorn api.main:app --reload --port 8010
```

Doğrulama (ayrı bir CMD penceresinde):

```bat
curl http://localhost:8010/api/health
REM Beklenen: {"ok": true, ...} + rag/llm durum alanları
```

`rag` alanı boş/erişilemez görünüyorsa `data\chroma_db\` yolunu ve `CHROMA_DIR`'in lokalde
**boş bırakıldığını** kontrol et (boşsa varsayılan `data\chroma_db` kullanılır).

## A.5 Admin Kullanıcı + iyzico Sandbox

```bat
python scripts\create_admin.py --email admin@hukukemsal.tr --password <parola> --name "Admin"

REM iyzico sandbox plan/ürünleri (IYZICO_API_KEY/SECRET sandbox değerleri .env'de olmalı)
python scripts\setup_iyzico_plans.py
REM Çıktıdaki plan referans kodlarını .env'e yaz: IYZICO_PLAN_PRO_SOLO=... vb.
```

## A.6 Frontend (port 3010)

```bat
cd web
npm install
npm run dev -- -p 3010
REM Tarayıcı: http://localhost:3010
```

> `npm run dev -- -p 3010` Next.js'e portu geçer (`--` sonrası argümanlar Next CLI'a iletilir).
> Alternatif: `set PORT=3010 && npm run dev`

Hızlı kontrol: `http://localhost:3010/giris` ile admin hesabına giriş → arama sayfasında bir
emsal araması → sonuç geliyor mu?

## A.7 Otomatik Testler

```bat
REM Postgres ayakta olmalı (RLS testleri canlı DB ister)
python -m pytest tests\ -v

REM RLS tenant izolasyonunu canlı doğrula
python -m scripts.verify_rls

REM Modül bütünlüğü (network gerektirmez)
python scripts\smoke_test.py
```

Frontend tarafı:

```bat
cd web
npm run lint && npm run type-check && npm run build
```

`npm run build`'in lokalde hatasız geçmesi, Vercel deploy'unun ön koşuludur.

## A.8 Fonksiyonel Test Turu

Tam liste **TEST_PLAN.md**'de. Asgari tur (URL'ler artık **3010** portunda):

1. Kayıt → doğrulama e-postası **Mailpit UI**'da (http://localhost:8025) görünüyor mu?
2. Giriş/çıkış, şifre sıfırlama akışı.
3. Emsal arama → sonuç → karar detay sayfası (`http://localhost:3010/karar/[id]`).
4. Dilekçe/ihtarname üretimi (LLM key'i ile) → Word export.
5. UYAP doküman yükleme → PII maskeleme çalışıyor mu?
6. Faiz hesaplayıcı + zamanaşımı modülleri.
7. Billing: sandbox kartla abonelik → webhook → planın aktifleşmesi.
8. Admin panel: kullanıcı listesi, metrikler.
9. İki ayrı tenant hesabıyla **çapraz veri erişimi DENENMELİ ve BAŞARISIZ olmalı** (RLS).
10. `python -m pytest tests\ -v` yeşil.

> CORS notu: backend `.env`'de `ALLOWED_ORIGINS` artık `http://localhost:3010` içermeli;
> aksi halde frontend'den (3010) gelen istekler CORS hatası alır.

---

# BÖLÜM B — Production'a Geçiş

Hedef mimari: **Railway** (backend + Postgres) + **Vercel** (frontend) + **Cloudflare** (DNS).

> Önemli: Production'da port çakışması **yok** — Railway ve Vercel kendi portlarını/HTTPS'i
> yönetir. 8010/3010 yalnızca **senin lokal makineni** ilgilendirir. Prod domainleri normal
> kalır (`hukukemsal.tr`, `api.hukukemsal.tr`).

## B.0 Çıkış Öncesi Kontrol Listesi
- [ ] Bölüm A'daki tüm testler yeşil (özellikle A.7 + A.8 madde 9)
- [ ] `npm run build` lokalde hatasız
- [ ] `docker build -t hukuk-api .` lokalde hatasız
- [ ] Tüm secret'lar **yeniden üretildi** (lokal değerler ASLA prod'a taşınmaz)
- [ ] `MASTER_ENCRYPTION_KEY` güvenli kasada (1Password/KMS) yedekli
- [ ] iyzico production sözleşmesi/key'leri hazır
- [ ] Domain + Cloudflare hesabı hazır

`docker build` (CMD, repo kökünde):

```bat
docker build -t hukuk-api .
```

## B.1 Secret'ların Üretimi (CMD)

```bat
REM NEXTAUTH_SECRET (prod):
powershell -Command "$b=New-Object byte[] 32;[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b);[Convert]::ToBase64String($b)"

REM MASTER_ENCRYPTION_KEY (prod) → kasaya yedekle!
powershell -Command "$b=New-Object byte[] 32;[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b);[Convert]::ToBase64String($b)"
```

Lokal `.env`'deki hiçbir parola/key prod'da kullanılmamalı.

## B.2 Production Veritabanı

1. Railway'de PostgreSQL 16 servisi oluştur, admin DSN'ini al.
2. Migration'ları lokal makinenden uygula (CMD — önce `set`, sonra çalıştır):

```bat
set "ADMIN_DATABASE_URL=postgresql://postgres:...@.../railway"
python scripts\init_db.py
REM 01..07, 09, 10 uygulanır; 08 (lokal roller) uygulanmaz — doğru davranış.
```

3. Uygulama rollerine **güçlü** parolalar ata (psql / Railway SQL konsolu):

```sql
ALTER ROLE app_user    PASSWORD '<güçlü-parola-1>';
ALTER ROLE app_service PASSWORD '<güçlü-parola-2>';
```

4. Prod `DATABASE_URL` → `app_user`, `SERVICE_DATABASE_URL` → `app_service` DSN'leri.
5. Admin kullanıcı (env'de prod DSN'lerle, CMD):

```bat
set "DATABASE_URL=<prod app_user DSN>"
set "SERVICE_DATABASE_URL=<prod app_service DSN>"
python scripts\create_admin.py --email ... --password ...
```

## B.3 Backend Deploy (Railway)

1. GitHub repo'yu push'la → Railway "Deploy from GitHub" → Dockerfile otomatik algılanır.
2. **Kalıcı volume** ekle, mount path: `/data`.
3. Environment variables (kritikler):

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

4. **Veriyi volume'a seed et** (tek seferlik). Tarball'ı lokalde Windows CMD ile hazırla:

```bat
REM Windows 10/11'de tar yerleşiktir
tar czf chroma_db.tgz -C data chroma_db
```

Tarball'ı R2/S3'e yükle, presigned URL al; sonra **Railway shell'de** (Linux — bash):

```bash
CHROMA_DIR=/data/chroma_db python -m scripts.seed_volume --source "https://<presigned-url>/chroma_db.tgz"
# Parquet'i de /data/final/all_decisions.parquet hedefine kopyala
```

> Not: Railway shell Linux'tur; oradaki komutlar bash'tir (CMD değil). Yalnızca **senin
> makinende** çalıştırdığın komutlar CMD'dir.

5. Servisi yeniden başlat → `https://<railway-url>/api/health` → `"ok": true` ve `rag` dolu.

## B.4 Frontend Deploy (Vercel)

1. Vercel'de projeyi import et (repo kökü; `vercel.json` build'i `web/`'e yönlendirir).
2. Environment variables (prod — lokal 3010/8010 **değil**):

```
NEXT_PUBLIC_API_URL=https://api.hukukemsal.tr
NEXT_PUBLIC_SITE_URL=https://hukukemsal.tr
NEXTAUTH_URL=https://hukukemsal.tr
NEXTAUTH_SECRET=<backend ile AYNI prod değeri>
DATABASE_URL=<prod app_user DSN>
API_INTERNAL_URL=<backend iç URL>
```

3. Deploy → build log'da `next-sitemap` postbuild adımının geçtiğini doğrula.

## B.5 DNS + E-posta

1. Cloudflare DNS: `hukukemsal.tr` → Vercel, `api.hukukemsal.tr` → Railway (CNAME).
2. SMTP sağlayıcı (Resend/Postmark/SES): SPF + DKIM + DMARC; sonra Railway env:
   `SMTP_HOST/PORT/USER/PASS`, `SMTP_FROM=noreply@hukukemsal.tr`.
3. Test: prod'da kayıt ol → e-posta geliyor mu, spam'e düşüyor mu?

## B.6 iyzico Production

1. Production API key/secret → Railway env (`IYZICO_BASE_URL=https://api.iyzipay.com`).
2. Production planları (prod key'lerle, CMD — env set edip lokalden de çalıştırabilirsin):

```bat
set "IYZICO_API_KEY=<prod key>"
set "IYZICO_SECRET=<prod secret>"
set "IYZICO_BASE_URL=https://api.iyzipay.com"
python scripts\setup_iyzico_plans.py
REM Çıkan plan kodlarını IYZICO_PLAN_* env'lerine yaz.
```

3. iyzico panelinde webhook URL'i: `https://api.hukukemsal.tr/api/billing/webhook`,
   `IYZICO_WEBHOOK_SECRET`'ı env'e ekle.
4. Düşük tutarlı gerçek kartla bir abonelik testi + iade.

## B.7 Observability + Operasyon
- **Sentry**: backend `SENTRY_DSN` + `SENTRY_TRACES_SAMPLE_RATE=0.1`; web `NEXT_PUBLIC_SENTRY_DSN`.
- **Uptime**: UptimeRobot/BetterStack → `https://api.hukukemsal.tr/api/health` (1 dk).
- **DB yedek**: Railway otomatik backup + haftalık `pg_dump`.
- **Volume yedek**: chroma tarball R2/S3'te; tenant verisi için periyodik snapshot.
- **Cron job'lar** (Railway cron):
  - `python scripts/emsal_alarm_job.py` — günlük
  - `python scripts/update_faiz_oranlari.py --evds` — günlük/haftalık

## B.8 Go-Live Smoke Testi (prod URL'ler — lokal port yok)
1. `curl https://api.hukukemsal.tr/api/health` → ok + rag dolu.
2. https://hukukemsal.tr açılıyor, `/karar/[id]` SSR çalışıyor.
3. Kayıt → e-posta → doğrulama → giriş.
4. Emsal arama → sonuç → detay.
5. Dilekçe üretimi (LLM prod key) → Word export.
6. Abonelik satın alma (test) → webhook → plan aktif.
7. İkinci hesapla çapraz tenant erişim denemesi → **reddedilmeli**.
8. Sentry'de test hatası görünüyor mu?
9. CORS: farklı origin'den istek reddediliyor mu?

## B.9 Geri Dönüş (Rollback)
- Vercel: önceki deployment'a "Promote".
- Railway: önceki image'a redeploy; gerekirse `pg_dump` yedeğinden restore.
- Veri bozulması: volume'u read-only alıp tarball yedeğinden yeni volume seed'le.

---

## Ortam Değişkenleri Referansı

| Değişken | Lokal (bu sürüm) | Production | Zorunlu |
|---|---|---|---|
| `DATABASE_URL` | app_user@localhost:5432 | app_user@railway | ✅ |
| `SERVICE_DATABASE_URL` | app_service@localhost:5432 | app_service@railway | ✅ |
| `ADMIN_DATABASE_URL` | hukuk@localhost:5432 | admin DSN (sadece migration) | migration için |
| `NEXTAUTH_SECRET` | dev değeri | prod değeri (web+api AYNI) | ✅ |
| `MASTER_ENCRYPTION_KEY` | dev değeri | prod değeri (kasada yedekli) | ✅ |
| `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | en az biri | en az biri (prod key) | LLM için ✅ |
| `APP_ENV` | development | production | önerilir |
| `ALLOWED_ORIGINS` | **http://localhost:3010** | prod domainler | ✅ |
| `CHROMA_DIR` | (boş → data\chroma_db) | /data/chroma_db | prod'da ✅ |
| `DECISIONS_PARQUET` | (boş) | /data/final/all_decisions.parquet | prod'da ✅ |
| `TENANT_CHROMA_DIR` | (boş) | /data/tenant_chroma | prod'da ✅ |
| `TENANT_STORAGE_ROOT` | data\tenant_storage | /data/tenant_storage | ✅ |
| `SMTP_HOST/PORT/USER/PASS/FROM` | localhost:1026 (Mailpit) | Resend/Postmark/SES | ✅ |
| `IYZICO_*` | sandbox | production + webhook secret | billing için ✅ |
| `SENTRY_DSN` | boş | dolu | önerilir |
| `EVDS_API_KEY` | opsiyonel | dolu | önerilir |
| Web: `NEXT_PUBLIC_API_URL` | **http://localhost:8010** | https://api.hukukemsal.tr | ✅ |
| Web: `NEXT_PUBLIC_SITE_URL` | **http://localhost:3010** | https://hukukemsal.tr | ✅ |
| Web: `NEXTAUTH_URL` | **http://localhost:3010** | https://hukukemsal.tr | ✅ |
| Web: `NEXTAUTH_SECRET` | dev (backend ile aynı) | prod (backend ile aynı) | ✅ |
| Web: `DATABASE_URL`, `API_INTERNAL_URL` | lokal değerler | prod değerler | ✅ |

## Sorun Giderme

| Belirti | Muhtemel neden / çözüm |
|---|---|
| `set VAR=... komut` tek satırda çalışmıyor | CMD'de satır içi env yok; önce `set "VAR=deger"`, sonra ayrı satırda komut |
| `'openssl' is not recognized` | Git for Windows kurulu değil → secret üretiminde PowerShell yöntemini kullan (A.2) |
| Frontend açılıyor ama API'ye bağlanamıyor | `web\.env.local` içindeki `NEXT_PUBLIC_API_URL=http://localhost:8010` mı? |
| Login sonrası CORS hatası | Backend `.env` → `ALLOWED_ORIGINS` içinde `http://localhost:3010` yok |
| `npm run dev` yine 3000 açıyor | `npm run dev -- -p 3010` kullan (veya `set PORT=3010 && npm run dev`) |
| Port 8010/3010 dolu | Başka bir port seç ve ilgili env değerlerini buna göre güncelle |
| API açılışta `RuntimeError: DATABASE_URL ... yok` | `.env` yüklenmemiş; uvicorn'u repo kökünden çalıştır |
| Açılışta encryption hatası | `MASTER_ENCRYPTION_KEY` boş — üret ve `.env`'e yaz |
| Login 401 / JWT decode hatası | Backend ve web `NEXTAUTH_SECRET` farklı |
| `/api/health`'te `rag` boş | `CHROMA_DIR` yanlış / volume seed edilmemiş → `scripts\seed_volume.py` |
| `infinite recursion detected in policy` | Migration 09 uygulanmamış → `python scripts\init_db.py` |
| RLS hiç engellenmiyor | `DATABASE_URL` owner/superuser ile bağlanıyor → app_user DSN kullan |
| Mailpit'e mail düşmüyor | `SMTP_PORT=1026` (1025 değil) |
| `docker compose up` şemayı kurmadı | Eski volume → `docker compose down -v` veya `init_db.py --local-roles` |
