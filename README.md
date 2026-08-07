# hukuk-emsal-veri

**Hukukçu Yapay Zekası** — Türk hukukunda emsal karar arama ve belge üretimi için
çok kiracılı (multi-tenant), abonelik tabanlı SaaS.

> **Not:** Bu depo bir "scraper kümesi" olarak başladı; bugün üretim SaaS'ının
> tamamını (backend + web + altyapı) barındırıyor. Scraper'lar hâlâ burada ve
> veri hattının ilk adımı.

---

## Ne yapıyor?

| Modül | Açıklama |
|---|---|
| **Emsal arama** | pgvector + tam metin hibrit arama, benzerlik eşikli, karar bazında çeşitlendirilmiş |
| **Dilekçe üretimi** | Emsallere atıflı dilekçe taslağı (LLM), atıflar programatik doğrulanır |
| **Karşı argüman** | Kendi tezine karşı argüman analizi |
| **İhtarname** | Alacak / kira-tahliye ihtarnamesi |
| **Karar özeti** | Uzun kararın sade Türkçe özeti |
| **Faiz hesaplayıcı** | Yasal / ticari avans / TCMB reeskont, dönem kırılımlı |
| **Zamanaşımı** | Kategori + kesilme tarihleriyle hesaplama |
| **Sözleşme analizi** | Risk maddesi tespiti |
| **KVKK uyum** | Sektöre göre checklist + uyum skoru |
| **UYAP dosya analizi** | Kullanıcının dosyalarını yükleyip kendi verisi üzerinde arama (tenant izolasyonlu, şifreli) |
| **Hatırlatıcılar** | Duruşma/süre takibi, e-posta bildirimi, .ics dışa aktarma |
| **Blog / SEO** | İçerik CMS'i + publisher API + otomatik SEO üretimi |

---

## Mimari

```
                 ┌─────────────────────────────┐
  Tarayıcı  ───► │  Next.js (App Router)       │   Vercel / Cloud Run
                 │  web/ — SSR + server proxy  │
                 └──────────────┬──────────────┘
                                │  /api/proxy/* (NextAuth JWT eklenir)
                 ┌──────────────▼──────────────┐
                 │  FastAPI                    │   Cloud Run
                 │  api/ + services/           │
                 └──────┬───────────────┬──────┘
                        │               │
        ┌───────────────▼──┐    ┌───────▼────────────┐
        │ Postgres+pgvector│    │ LLM / Embedding API│
        │ RLS ile izolasyon│    │ Anthropic / Google │
        └──────────────────┘    └────────────────────┘
```

| Katman | Teknoloji |
|---|---|
| Backend | Python 3.11, FastAPI, asyncpg, psycopg |
| Frontend | Next.js 14 (App Router), TypeScript (strict), Tailwind |
| Veri | Postgres + pgvector (HNSW), karar metni için Parquet/DuckDB |
| Kimlik | NextAuth (JWT) · API anahtarı (public v1) · eklenti token'ı |
| Ödeme | iyzico v2 (abonelik + tek seferlik ek paket) |
| Dağıtım | GCP Cloud Build → Cloud Run; alternatif Railway/Vercel |

**Güvenlik temelleri**

- **Tenant izolasyonu**: Postgres RLS + ayrı `app_user` (NOBYPASSRLS) havuzu.
  Doğrulama: `python -m scripts.verify_rls`
- **Şifreleme**: tenant başına DEK, master key ile sarmalanır (envelope).
  Tenant silinince DEK silinir → veri **kriptografik olarak** kurtarılamaz.
- **PII**: LLM/embedding API'sine giden her metin 3 katmanlı maskelemeden geçer
  (`services/pii_redaction.py`); regresyonu `tests/test_pii_leak_e2e.py` korur.
- **İstemci IP**: `X-Forwarded-For` güvenilir proxy zincirinden çözülür
  (`api/net.py`, `TRUSTED_PROXY_HOPS`).

---

## Kurulum (lokal)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env        # değerleri doldurun
docker compose up -d db     # Postgres + pgvector

python -m scripts.init_db --local-roles   # şema + RLS rolleri
python -m scripts.create_admin            # ilk admin

uvicorn api.main:app --reload --port 8000
```

Frontend:

```bash
cd web
cp .env.local.example .env.local
npm ci
npm run dev        # http://localhost:3000
```

Ayrıntılı rehber: [`SETUP_LOCAL.md`](SETUP_LOCAL.md) ·
[`LOKAL_TEST_VE_PRODUCTION_REHBERI.md`](LOKAL_TEST_VE_PRODUCTION_REHBERI.md)

---

## Test

```bash
# Backend — DB gerektirmeyenler
PYTHONPATH=. pytest --ignore=tests/test_db_integration.py

# Kapsam raporu
PYTHONPATH=. pytest --ignore=tests/test_db_integration.py \
       --cov=api --cov=services --cov=common --cov-report=term-missing

# RLS + kriptografik silme (canlı Postgres gerekir)
RUN_DB_TESTS=1 PYTHONPATH=. pytest tests/test_db_integration.py
PYTHONPATH=. python -m scripts.verify_rls

# Frontend — tip kontrolü GERÇEK kapıdır (ignoreBuildErrors kapalı)
cd web && npx tsc --noEmit
```

CI (`.github/workflows/ci.yml`) her PR'da: tüm pytest paketi + coverage,
kritik ruff kuralları, Postgres'li RLS entegrasyon işi, `tsc --noEmit`,
`next build`, pip-audit / npm audit / gitleaks.

### RAG kalitesi

Emsal aramanın doğruluğu ölçülebilir olmalıdır — yanlış emsal bu üründeki en
ağır hata türüdür.

```bash
python -m scripts.rag_eval                    # recall@k, precision@k, MRR
python -m scripts.rag_eval --esik-tara        # en uygun benzerlik eşiğini bul
python -m scripts.rag_eval --min-recall 0.70  # regresyon kapısı (exit 1)
```

Altın standart set ve küratörleme rehberi: [`evals/README.md`](evals/README.md)

---

## Veri hattı (scraper → arama)

```bash
# 1) Kaynaklardan topla (HUDOC · AYM · Danıştay · Yargıtay)
python scripts/run_scraper.py --source hudoc --max 200

# 2) Birleştir + tekilleştir → parquet
python -m pipelines.export_final

# 3) Parçala
python -m pipelines.chunk

# 4) Embed et → pgvector
python -m pipelines.embed          # model değiştiyse: --recreate
```

`pipelines/embed.py`, tabloda **farklı bir modelle** üretilmiş vektör bulursa
çalışmayı durdurur — karışık semantik uzaylar benzerlik skorlarını sessizce
anlamsızlaştırdığı için.

Kapsam raporu: `python -m analytics.coverage`

**Bilinen kapsam sınırı:** Mevcut veri ağırlıklı olarak **icra / tahsilat /
ihtar** hukukudur (`queries/keywords.yaml`). UYAP Emsal Karar Bankası ve ilk
derece/istinaf kararları henüz taranmıyor. `scripts/rag_eval.py` çıktısındaki
kategori kırılımı bu boşluğu gösterir.

---

## Operasyon

```bash
# Günlük bakım (KVKK kalıcı silme + faiz oranları + emsal alarmları)
python -m scripts.cron_daily            # --dry-run ile önce prova
```

Prod'da bu iş Cloud Scheduler + Cloud Run Job ile her gece koşar:
`./infra/gcp/setup_gcp.sh cron`

| Uç | Amaç |
|---|---|
| `GET /api/health` | **Liveness** — process ayakta mı? Bağımlılıklara bakmaz. |
| `GET /api/ready` | **Readiness** — DB dahil sağlıklı mı? Erişilemezse **503**. LB ve uptime izleme bunu kullanmalı. |

Loglar `LOG_FORMAT=json` ile yapısaldır ve her satır `request_id` taşır;
yanıtlardaki `X-Request-Id` header'ı ile eşleşir.

Dağıtım: [`DEPLOY.md`](DEPLOY.md) · [`infra/gcp/DEPLOY_GCP.md`](infra/gcp/DEPLOY_GCP.md)
Felaket kurtarma: [`DR_RUNBOOK.md`](DR_RUNBOOK.md)

---

## Dizin yapısı

```
api/            FastAPI uygulaması
  routers/      30 router (arama, dilekçe, billing, uyap, admin, v1 …)
  auth.py       JWT / API key / eklenti token doğrulama, require_admin
  db.py         RLS'e tabi havuz + servis (BYPASSRLS) havuzu
  kota.py       plan/kredi kotası — advisory lock ile atomik
  net.py        güvenilir proxy ile istemci IP çözümü
  logging_setup.py  yapısal log + korelasyon kimliği
services/       iş mantığı (rag, grounding, billing, encryption, pii_redaction …)
common/         scraper yardımcıları (normalize, anonymize, http, job_queue)
scrapers/       HUDOC · AYM · Danıştay · Yargıtay
pipelines/      export_final → chunk → embed
scripts/        CLI: init_db, cron_daily, rag_eval, verify_rls, purge_deleted …
evals/          RAG altın standart seti
infra/db/       numaralı SQL migration'lar
infra/gcp/      kurulum + dağıtım betikleri
web/            Next.js uygulaması
tests/          pytest paketi
```

---

## Yasal

Toplanan kararlar kamuya açıktır; toplu indirme TOS açısından gri alandır.
Yayımlamadan önce KVKK görüşü + lisans seçimi gerekir. Üretilen hiçbir çıktı
hukuki tavsiye değildir — avukat kontrolü zorunludur.
