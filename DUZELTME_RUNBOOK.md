# Düzeltme Runbook — "Sayfa Açılmıyor" (Cloud Run / hukuk-api)

> Bu rehber, paylaştığın API loglarındaki kırık duruma özeldir. Genel kurulum için
> `infra/gcp/DEPLOY_GCP.md`'ye bak; burada sadece **mevcut bozuk deploy'u düzeltme**
> adımları var.

---

## 0) Önce teşhis — log satırları neyi söylüyor?

API **çökmüyor**, ayağa kalkıyor (`Application startup complete`, `STARTUP TCP probe
succeeded ... port 8000`). Sorun, **yanlış imajın eksik konfigürasyonla** deploy
edilmesi. Kanıtlar:

| Log satırı | Anlamı | Kök neden |
|---|---|---|
| `Uvicorn running on ... :8000`, 2 worker | Sade `Dockerfile` çalışıyor | Deploy `cloudbuild.yaml`/`Dockerfile.api` ile yapılmamış (muhtemelen `gcloud run deploy --source`) |
| `DB başlatma başarısız: DATABASE_URL ... yok` | Postgres DSN env yok | Secret Manager sırları servise bağlanmamış |
| `Waitlist tablo oluşturma başarısız: SERVICE_DATABASE_URL / DATABASE_URL yok` | DB'ye hiç bağlanılamıyor | Aynı sebep |
| `RAG warmup başarısız: Collection [hukuk_kararlari] does not exist` | Vektör verisi yok | Sade `Dockerfile` `seed_data/chroma_db`'yi image'a GÖMMEZ; runtime boş Chroma yaratır |
| `RAG warmup başarısız: table collections already exists` | 2 worker boş Chroma'yı aynı anda kuruyor (race) | Aynı sebep — veri olmadığı için |
| `Hatırlatıcı dispatch hatası: ... yok` | Arka plan döngüsü DB'siz | Aynı DB sebebi |

**Sonuç:** Deploy edilen şey = verisiz + veritabanısız bir backend. Ayrıca API'de
`/` route'u **yok**, sadece `/api/*` var — çıplak URL'de 404 görmek normaldir. Asıl
site ayrı `hukuk-web` (Next.js) servisinde.

**Hedef:** `Dockerfile.api` imajını + Secret Manager sırlarını + GCS'teki vektör
verisini kullanarak `cloudbuild.yaml` üzerinden yeniden deploy etmek.

Aşağıdaki ortam değişkenlerini bir kez ayarla (kendi değerlerinle):

```bash
export PROJECT=hukukemsal-prod          # gerçek proje ID'n
export REGION=europe-west1
export AR=hukuk
export SQL=hukuk-pg                      # Cloud SQL instance adı
export DATA_BUCKET=${PROJECT}-data
export TS_BUCKET=${PROJECT}-tenant-storage
gcloud config set project $PROJECT

# Cloud SQL bağlantı adı (PROJECT:REGION:INSTANCE) — birçok adımda lazım:
export SQL_CONN=$(gcloud sql instances describe $SQL --format='value(connectionName)')
echo "SQL_CONN=$SQL_CONN"
```

---

## 1) Ön-kontrol — neyin var, neyin eksik?

Düzeltmeye geçmeden önce eksikleri tespit et. Hangi adımı atlayabileceğini bu belirler.

```bash
# a) Vektör verisi GCS'te mi? (fetch-data bunu indiriyor)
gcloud storage ls gs://$DATA_BUCKET/chroma_db/ | head
gcloud storage ls gs://$DATA_BUCKET/all_decisions.parquet

# b) Secret'lar var mı?
for s in DATABASE_URL SERVICE_DATABASE_URL ADMIN_DATABASE_URL NEXTAUTH_SECRET \
         MASTER_ENCRYPTION_KEY ANTHROPIC_API_KEY GOOGLE_API_KEY \
         IYZICO_API_KEY IYZICO_SECRET_KEY IYZICO_WEBHOOK_SECRET \
         SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASS SMTP_FROM ADMIN_EMAIL; do
  gcloud secrets describe $s >/dev/null 2>&1 && echo "OK   $s" || echo "EKSİK $s"
done

# c) Cloud SQL instance ayakta mı?
gcloud sql instances describe $SQL --format='value(state)'

# d) Mevcut Cloud Run servisi hangi imaj/port ile çalışıyor?
gcloud run services describe hukuk-api --region=$REGION \
  --format='value(spec.template.spec.containers[0].image, spec.template.spec.containers[0].ports[0].containerPort)'
```

- (a) boşsa → **Adım 3** (veri yükle).
- (b)'de "EKSİK" varsa → **Adım 4** (secret oluştur).
- (c) yoksa → `DEPLOY_GCP.md` Bölüm 2 (Cloud SQL kur) + **Adım 5** (migration).
- Hepsi varsa doğrudan → **Adım 6** (cloudbuild ile deploy).

---

## 2) cloudbuild.yaml placeholder'larını gerçek değerlerle doldur

`cloudbuild.yaml` içindeki şu satırlar hâlâ örnek değer; bu haliyle build `fetch-data`
adımında patlar:

```yaml
substitutions:
  _DATA_BUCKET: "REPLACE-data-bucket"       # → gerçek: ${PROJECT}-data
  _TS_BUCKET:   "REPLACE-tenant-storage"    # → gerçek: ${PROJECT}-tenant-storage
  _SQL_INSTANCE: "PROJECT:REGION:INSTANCE"  # → gerçek: $SQL_CONN değeri
```

İki seçenek:
- **Dosyayı düzenle** (commit'e gider, tekrarlanan deploy'lar için temiz), veya
- **Deploy anında `--substitutions` ile geç** (Adım 6'daki gibi; dosyayı kirletmez).

`_SITE_URL` / `_API_PUBLIC_URL` zaten gerçek domain'lerle dolu (`hukukcuyapayzekasi.com`).

---

## 3) Vektör verisini GCS'e yükle (collection hatasının çözümü)

`hukuk_kararlari` collection'ı, `Dockerfile.api` build sırasında GCS'ten indirilen
veriden gömülür. GCS boşsa önce yükle (lokalde `data/chroma_db` mevcutsa):

```bash
# Bucket'lar yoksa oluştur:
gcloud storage buckets create gs://$DATA_BUCKET --location=$REGION 2>/dev/null || true
gcloud storage buckets create gs://$TS_BUCKET  --location=$REGION 2>/dev/null || true

# ~2.1GB ChromaDB + parquet'i bir kez yükle:
gcloud storage rsync -r ./data/chroma_db gs://$DATA_BUCKET/chroma_db
gcloud storage cp ./data/final/all_decisions.parquet gs://$DATA_BUCKET/all_decisions.parquet

# Doğrula:
gcloud storage ls gs://$DATA_BUCKET/chroma_db/ | head
```

> Lokalde de veri yoksa, `chroma_db`'yi üreten pipeline'ı (`pipelines/embed.py`)
> çalıştırman ya da yedeği indirmen gerekir. Veri olmadan arama çalışmaz.

---

## 4) Secret Manager — eksik sırları oluştur

Adım 1b'de "EKSİK" çıkan her sır için. DSN'ler **unix socket** formatında olmalı
(Cloud Run Cloud SQL'e böyle bağlanır — `SQL_CONN` = `PROJECT:REGION:INSTANCE`):

```bash
# 3 DSN (DEPLOY_GCP.md'deki rol mantığı: app_user RLS'e tabi, hukuk = owner/admin)
printf '%s' "postgresql://app_user:GUCLU_SIFRE_2@/hukuk_emsal?host=/cloudsql/$SQL_CONN" \
  | gcloud secrets create DATABASE_URL --data-file=-
printf '%s' "postgresql://hukuk:GUCLU_SIFRE_1@/hukuk_emsal?host=/cloudsql/$SQL_CONN" \
  | gcloud secrets create SERVICE_DATABASE_URL --data-file=-
printf '%s' "postgresql://hukuk:GUCLU_SIFRE_1@/hukuk_emsal?host=/cloudsql/$SQL_CONN" \
  | gcloud secrets create ADMIN_DATABASE_URL --data-file=-

# Kriptografik anahtarlar:
openssl rand -base64 32 | gcloud secrets create NEXTAUTH_SECRET --data-file=-
openssl rand -base64 32 | gcloud secrets create MASTER_ENCRYPTION_KEY --data-file=-

# API anahtarları / iyzico / SMTP (gerçek değerlerle):
printf '%s' 'sk-ant-...'        | gcloud secrets create ANTHROPIC_API_KEY --data-file=-
printf '%s' 'AIza...'           | gcloud secrets create GOOGLE_API_KEY --data-file=-
printf '%s' '...'               | gcloud secrets create IYZICO_API_KEY --data-file=-
printf '%s' '...'               | gcloud secrets create IYZICO_SECRET_KEY --data-file=-
printf '%s' '...'               | gcloud secrets create IYZICO_WEBHOOK_SECRET --data-file=-
printf '%s' '...'               | gcloud secrets create IYZICO_PLAN_PRO_SOLO --data-file=-
printf '%s' '...'               | gcloud secrets create IYZICO_PLAN_PRO_UYAP --data-file=-
printf '%s' '...'               | gcloud secrets create IYZICO_PLAN_TEAM --data-file=-
printf '%s' '...'               | gcloud secrets create IYZICO_PLAN_TEAM_UYAP --data-file=-
printf '%s' 'smtp.example.com'  | gcloud secrets create SMTP_HOST --data-file=-
printf '%s' '587'               | gcloud secrets create SMTP_PORT --data-file=-
printf '%s' '...'               | gcloud secrets create SMTP_USER --data-file=-
printf '%s' '...'               | gcloud secrets create SMTP_PASS --data-file=-
printf '%s' 'no-reply@hukukcuyapayzekasi.com' | gcloud secrets create SMTP_FROM --data-file=-
printf '%s' 'admin@hukukcuyapayzekasi.com'    | gcloud secrets create ADMIN_EMAIL --data-file=-
```

> Sır **zaten varsa ama değeri yanlışsa** yeni sürüm ekle:
> `printf '%s' 'YENI_DEGER' | gcloud secrets versions add DATABASE_URL --data-file=-`
> (cloudbuild `:latest` etiketini bağlar.)

---

## 5) Veritabanı şeması (migration) — DB boşsa

Cloud SQL ilk kez kuruluyorsa veya tablolar yoksa, şemayı uygula. Cloud SQL Auth
Proxy ile workstation'dan:

```bash
# Proxy'yi indir (bir kez), sonra:
./cloud-sql-proxy $SQL_CONN &          # localhost:5432 açar
export ADMIN_DATABASE_URL='postgresql://hukuk:GUCLU_SIFRE_1@localhost:5432/hukuk_emsal'
python scripts/init_db.py              # 01..26 migration'ları sırayla uygular

# app_user'a tablo yetkileri (RLS'e tabi request kullanıcısı):
psql "$ADMIN_DATABASE_URL" -c \
  "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO app_user;"
```

> Prod'da `07_rls_hardening`'deki `FORCE ROW LEVEL SECURITY` satırı uygulanmaz
> (owner `hukuk` bypass etmeli). Detay: `DEPLOY_GCP.md` Bölüm 4.

Admin kullanıcı (proxy açıkken):

```bash
python scripts/create_admin.py --email admin@hukukcuyapayzekasi.com \
  --password 'GUCLU' --name 'Admin'
```

---

## 6) Doğru şekilde yeniden deploy et (asıl düzeltme)

**Elle `gcloud run deploy --source` KULLANMA** — o sade `Dockerfile`'ı seçer (port
8000, veri yok). Bunun yerine pipeline'ı çalıştır; `Dockerfile.api` ile build eder,
veriyi gömer, secret'ları bağlar:

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION=$REGION,_AR_REPO=$AR,\
_DATA_BUCKET=$DATA_BUCKET,_TS_BUCKET=$TS_BUCKET,_SQL_INSTANCE=$SQL_CONN,\
_SITE_URL=https://hukukcuyapayzekasi.com,\
_API_PUBLIC_URL=https://api.hukukcuyapayzekasi.com
```

> İlk kez build çalıştırıyorsan, Cloud Build servis hesabına izinleri ver
> (`DEPLOY_GCP.md` Bölüm 6): `run.admin, iam.serviceAccountUser, cloudsql.client,
> secretmanager.secretAccessor, artifactregistry.writer, storage.objectViewer`.
> Ayrıca Cloud Run runtime servis hesabına `cloudsql.client` +
> `secretmanager.secretAccessor` + tenant-storage bucket'ında `storage.objectAdmin`.

Bu deploy ayrıca servisi **port 8080**'e taşır (cloudbuild `--port=8080`), Cloud SQL
bağlar ve tüm `--set-secrets`'i uygular.

---

## 7) Doğrula

```bash
# Servis URL'sini al:
API_URL=$(gcloud run services describe hukuk-api --region=$REGION \
  --format='value(status.url)')

# Health — rag.collection sayısı > 0 ve llm.ok true olmalı:
curl -s "$API_URL/api/health" | jq

# Yeni logları izle — artık "DATABASE_URL yok" / "collection does not exist" OLMAMALI:
gcloud run services logs read hukuk-api --region=$REGION --limit=50
```

Beklenen `/api/health` çıktısı (özet):

```json
{
  "ok": true,
  "rag": { "count": 12345, ... },     // > 0
  "llm": { "ok": true, ... }
}
```

Sağlıklı startup loglarında artık şu uyarılar **görünmemeli**:
`DATABASE_URL ... yok`, `Collection [hukuk_kararlari] does not exist`.

---

## 8) Frontend (asıl "sayfa") kontrolü

Kullanıcının açtığı sayfa API değil, `hukuk-web` (Next.js) servisidir. API
düzeldikten sonra:

```bash
gcloud run services describe hukuk-web --region=$REGION --format='value(status.url)'
```

- `hukuk-web` deploy edilmiş mi? (cloudbuild `deploy-web` adımı bunu da yapar.)
- `NEXT_PUBLIC_API_URL=https://api.hukukcuyapayzekasi.com` build anında gömülü mü?
  (domain değişirse web **yeniden build** edilmeli — NEXT_PUBLIC_* derleme zamanı.)
- Domain mapping: `hukukcuyapayzekasi.com → hukuk-web`,
  `api.hukukcuyapayzekasi.com → hukuk-api` (`DEPLOY_GCP.md` Bölüm 8).
- CORS: API'de `ALLOWED_ORIGINS=https://hukukcuyapayzekasi.com` set (cloudbuild yapıyor).

---

## Özet kontrol listesi

- [ ] `cloudbuild.yaml` substitution'ları gerçek (`_DATA_BUCKET`, `_TS_BUCKET`, `_SQL_INSTANCE`)
- [ ] GCS `data-bucket`'ta `chroma_db/` + `all_decisions.parquet` dolu
- [ ] Secret Manager'da 3 DSN + diğer tüm sırlar mevcut (Adım 1b hepsi OK)
- [ ] Cloud SQL ayakta, migration uygulanmış, `app_user` yetkili
- [ ] Deploy **cloudbuild ile** yapıldı (elle `--source` değil)
- [ ] `/api/health` → `rag.count > 0`, `llm.ok = true`
- [ ] Loglarda DB/collection uyarısı yok
- [ ] `hukuk-web` deploy + domain mapping + doğru `NEXT_PUBLIC_API_URL`
