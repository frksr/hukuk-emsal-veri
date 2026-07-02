# Production Deploy — Google Cloud (Cloud Run + Cloud SQL + Cloud Build)

Mimari:
- **Cloud Run** — `hukuk-api` (FastAPI) ve `hukuk-web` (Next.js) ayrı servisler.
- **Cloud SQL (PostgreSQL 16)** — uygulama veritabanı (RLS).
- **Artifact Registry** — Docker imajları.
- **Secret Manager** — tüm sırlar (DB DSN, NEXTAUTH, iyzico, SMTP, API anahtarları…).
- **GCS** — `data-bucket` (2.1GB ChromaDB + kararlar parquet'i; build'de image'a gömülür) ve `tenant-storage` (UYAP şifreli belgeleri; Cloud Run'a volume mount).
- **Cloud Build** — git push → build (api+web) → deploy.

Aşağıdaki değişkenleri kendine göre ayarla:
```bash
export PROJECT=hukukemsal-prod
export REGION=europe-west1
export AR=hukuk
export SQL=hukuk-pg
export DATA_BUCKET=${PROJECT}-data
export TS_BUCKET=${PROJECT}-tenant-storage
gcloud config set project $PROJECT
```

---

## 1) API'leri aç + Artifact Registry

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  sqladmin.googleapis.com secretmanager.googleapis.com \
  artifactregistry.googleapis.com storage.googleapis.com

gcloud artifacts repositories create $AR \
  --repository-format=docker --location=$REGION
```

## 2) Cloud SQL (PostgreSQL)

```bash
gcloud sql instances create $SQL \
  --database-version=POSTGRES_16 --region=$REGION \
  --tier=db-custom-1-3840 --storage-type=SSD --storage-size=20GB
gcloud sql databases create hukuk_emsal --instance=$SQL
# Sahip/owner kullanıcı (migration + service işlemleri):
gcloud sql users create hukuk --instance=$SQL --password='GUCLU_SIFRE_1'
# Request-scope (RLS'e tabi) kullanıcı:
gcloud sql users create app_user --instance=$SQL --password='GUCLU_SIFRE_2'

# Bağlantı adı (PROJECT:REGION:INSTANCE):
gcloud sql instances describe $SQL --format='value(connectionName)'
```

> **RLS / Cloud SQL notu:** Kod 3 DSN kullanır — `DATABASE_URL` (RLS'e tabi `app_user`),
> `SERVICE_DATABASE_URL` ve `ADMIN_DATABASE_URL` (RLS bypass + DDL → `hukuk` sahibi).
> Cloud SQL'de gerçek `BYPASSRLS` rolü oluşturmak kısıtlıdır; bu yüzden service/admin
> için **tablo sahibi `hukuk`** kullanılır ve migration'da `FORCE ROW LEVEL SECURITY`
> uygulanMAZ (sahip rol RLS'i bypass eder, `app_user` ise tabidir). 07_rls_hardening'i
> prod'da çalıştırırken FORCE satırını atla (aşağıda migration adımına bak).

Cloud SQL DSN'leri (unix socket — Cloud Run buradan bağlanır):
```
DATABASE_URL          = postgresql://app_user:GUCLU_SIFRE_2@/hukuk_emsal?host=/cloudsql/PROJECT:REGION:INSTANCE
SERVICE_DATABASE_URL  = postgresql://hukuk:GUCLU_SIFRE_1@/hukuk_emsal?host=/cloudsql/PROJECT:REGION:INSTANCE
ADMIN_DATABASE_URL    = postgresql://hukuk:GUCLU_SIFRE_1@/hukuk_emsal?host=/cloudsql/PROJECT:REGION:INSTANCE
```

## 3) GCS bucket'lar + vektör verisini yükle

```bash
gcloud storage buckets create gs://$DATA_BUCKET --location=$REGION
gcloud storage buckets create gs://$TS_BUCKET  --location=$REGION

# 2.1GB ChromaDB + parquet'i (lokal data/ klasöründen) bir kez yükle:
gcloud storage rsync -r ./data/chroma_db gs://$DATA_BUCKET/chroma_db
gcloud storage cp ./data/final/all_decisions.parquet gs://$DATA_BUCKET/all_decisions.parquet
```
Cloud Build her build'de bu veriyi indirip image'a gömer (cloudbuild.yaml `fetch-data`).

## 4) Migration (şema)

Workstation'dan Cloud SQL Auth Proxy ile:
```bash
# proxy'yi indir, ardından:
./cloud-sql-proxy PROJECT:REGION:INSTANCE &     # localhost:5432 açar
export ADMIN_DATABASE_URL='postgresql://hukuk:GUCLU_SIFRE_1@localhost:5432/hukuk_emsal'
python scripts/init_db.py        # 01..25 migration'ları uygular
```
> 07_rls_hardening prod'da `app_user` rolüne parola atamadığı için: rolleri yukarıda
> Cloud SQL'de oluşturduk. `app_user`'a tablo yetkilerini ver:
> `GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO app_user;`
> (init_db sonrası proxy üzerinden `psql` ile çalıştırılabilir.) FORCE RLS'i prod'da
> uygulamıyoruz; `app_user` policy'lere tabi, `hukuk` (sahip) bypass eder.

## 5) Secret Manager — sırları oluştur

Her biri için (örnek):
```bash
printf '%s' 'postgresql://app_user:...@/hukuk_emsal?host=/cloudsql/PROJECT:REGION:INSTANCE' \
  | gcloud secrets create DATABASE_URL --data-file=-
```
Oluşturulacak sırlar:
`DATABASE_URL`, `SERVICE_DATABASE_URL`, `ADMIN_DATABASE_URL`, `NEXTAUTH_SECRET`
(`openssl rand -base64 32`), `MASTER_ENCRYPTION_KEY` (`openssl rand -base64 32`),
`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `IYZICO_API_KEY`, `IYZICO_SECRET_KEY`,
`IYZICO_WEBHOOK_SECRET`, `IYZICO_PLAN_PRO_SOLO`, `IYZICO_PLAN_PRO_UYAP`,
`IYZICO_PLAN_TEAM`, `IYZICO_PLAN_TEAM_UYAP`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASS`, `SMTP_FROM`, `ADMIN_EMAIL`.

## 6) Cloud Build izinleri (servis hesabı)

```bash
PROJNUM=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
CB=$PROJNUM@cloudbuild.gserviceaccount.com
for ROLE in run.admin iam.serviceAccountUser cloudsql.client \
            secretmanager.secretAccessor artifactregistry.writer \
            storage.objectViewer; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:$CB" --role="roles/$ROLE"
done
```
> Cloud Run servislerinin çalışma (runtime) servis hesabına da
> `roles/cloudsql.client`, `roles/secretmanager.secretAccessor` ve `tenant-storage`
> bucket'ında `roles/storage.objectAdmin` ver.

## 7) Cloud Build trigger (git'ten)

```bash
gcloud builds triggers create github \
  --repo-name=hukuk-emsal-veri --repo-owner=<github-kullanici> \
  --branch-pattern='^main$' --build-config=cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_AR_REPO=$AR,_DATA_BUCKET=$DATA_BUCKET,_TS_BUCKET=$TS_BUCKET,_SQL_INSTANCE=PROJECT:REGION:INSTANCE,_SITE_URL=https://hukukcuyapayzekasi.com,_API_PUBLIC_URL=https://api.hukukcuyapayzekasi.com
```
İlk deploy: `main`'e push et (veya `gcloud builds submit --config cloudbuild.yaml --substitutions=...`).

## 8) Özel domain (Cloud Run domain mapping)

```bash
gcloud run domain-mappings create --service=hukuk-web --domain=hukukcuyapayzekasi.com --region=$REGION
gcloud run domain-mappings create --service=hukuk-api --domain=api.hukukcuyapayzekasi.com --region=$REGION
```
Çıkan DNS kayıtlarını alan adı sağlayıcına ekle. Domain belliyse trigger
substitution'larındaki `_SITE_URL` / `_API_PUBLIC_URL`'i güncelle ve yeniden deploy et
(NEXT_PUBLIC_* derleme anında gömüldüğü için web yeniden build edilmeli).

## 9) iyzico (production)

- iyzico panelinde **Webhook URL** = `https://api.hukukcuyapayzekasi.com/api/billing/webhook`
- Callback'ler `_SITE_URL` üzerinden otomatik (`/api/billing/subscription-callback`,
  `/api/billing/addon-callback`).
- `IYZICO_BASE_URL` cloudbuild'de `https://api.iyzipay.com` (canlı) olarak set.
- Canlı API/secret anahtarlarını ve pricing-plan referans kodlarını Secret Manager'a koy.

## 10) Admin kullanıcı oluştur

Proxy açıkken:
```bash
export ADMIN_DATABASE_URL='postgresql://hukuk:...@localhost:5432/hukuk_emsal'
python scripts/create_admin.py --email admin@hukukcuyapayzekasi.com --password 'GUCLU' --name 'Admin'
```

---

## Notlar / kontrol listesi
- **NEXT_PUBLIC_* derleme anında** gömülür → domain değişirse web yeniden build.
- **min-instances=1** (api): 2GB image soğuk başlatmayı önler (maliyet ↑; trafik artınca max-instances).
- **tenant-storage** Cloud Run'a gcsfuse ile mount; çok sayıda küçük şifreli dosya için yeterli, ileride Filestore'a taşınabilir.
- Vektör verisi salt-okunur; güncellenince `gs://$DATA_BUCKET`'a yeni veriyi yükleyip yeniden build et.
- **CORS**: `ALLOWED_ORIGINS=_SITE_URL` (api env). Birden fazla origin gerekiyorsa virgülle ekle.
- Sağlık ucu: `GET /api/health` (Cloud Run startup probe için kullanılabilir).
- Maliyet: Cloud SQL + 2 Cloud Run (min-instances=1) + egress. Beta için db-custom-1-3840 yeterli.
