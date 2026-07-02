# Felaket Kurtarma (DR) Runbook — Hukuk Emsal

**Kapsam:** GCP production ortamı (Cloud Run `hukuk-api`/`hukuk-web` + Cloud SQL
`hukuk-pg` + Secret Manager + GCS) ve Railway alternatifi.
**İlgili dokümanlar:** `infra/gcp/DEPLOY_GCP.md`, `DUZELTME_RUNBOOK.md`,
`SECURITY_HARDENING.md`.

Ortak değişkenler (DEPLOY_GCP.md ile aynı):

```bash
export PROJECT=hukukemsal-prod
export REGION=europe-west1
export SQL=hukuk-pg
export DATA_BUCKET=${PROJECT}-data
export TS_BUCKET=${PROJECT}-tenant-storage
gcloud config set project $PROJECT
```

---

## 1. MASTER_ENCRYPTION_KEY yedekleme prosedürü

> **Neden kritik:** Envelope encryption master key'i. Her tenant'ın DEK'i bu
> anahtarla sarmalanır (`services/key_manager.py`). **Kaybı = tüm tenant verisi
> kalıcı olarak okunamaz.** Hiçbir yedek bunu telafi edemez; DB yedeği elinizde
> olsa bile şifreli alanlar çözülemez.

### 1.1 Secret Manager sürümleme (birincil saklama)

Anahtar Secret Manager'da tutulur; her değişiklik **yeni sürüm** olarak eklenir,
eski sürümler asla silinmez (disable edilebilir ama `destroy` edilmez):

```bash
# Mevcut sürümleri gör:
gcloud secrets versions list MASTER_ENCRYPTION_KEY

# Değer değişecekse YENİ SÜRÜM ekle (üzerine yazma / silme YOK):
printf '%s' 'YENI_DEGER' | gcloud secrets versions add MASTER_ENCRYPTION_KEY --data-file=-

# Yanlışlıkla silmeye karşı: destroy iznini kimseye verme,
# secret'a silme koruması için IAM'i dar tut (sadece owner + Cloud Run runtime SA'ya accessor).
```

Kontroller:
- [ ] Secret üzerinde `secretmanager.versions.destroy` yetkisi yalnızca owner'da.
- [ ] Cloud Run runtime servis hesabında yalnızca `roles/secretmanager.secretAccessor`.
- [ ] Rotasyon yapılacaksa: önce tüm DEK'ler yeni master ile yeniden sarmalanmalı
      (re-wrap script'i gerekir) — **rotasyonu re-wrap olmadan yapma.**

### 1.2 Offline kopya (zorunlu, en az 2 nüsha)

1. Anahtarı güvenli bir makinede görüntüle (ekran görüntüsü ALMA, panoya kopyalayıp
   bulut not uygulamasına YAPIŞTIRMA):
   ```bash
   gcloud secrets versions access latest --secret=MASTER_ENCRYPTION_KEY
   ```
2. Değeri **kağıda yaz** veya şifreli bir USB'ye kaydet (ör. VeraCrypt konteyneri).
3. En az **2 fiziksel nüsha**, iki ayrı lokasyonda (ör. ofis kasası + banka kasası
   / evdeki kasa). Nüshanın üstüne anahtarın adını ve tarihi yaz; değeri hangi
   secret sürümüne karşılık geldiğini not et.
4. Parola yöneticisi (1Password/Bitwarden) kasasına da bir kopya konabilir —
   ancak bu offline nüshaların **yerine geçmez**.
5. Her yeni sürüm eklendiğinde offline nüshaları **aynı gün** güncelle.

- [ ] Offline nüsha 1 yerinde ve okunaklı (6 ayda bir kontrol)
- [ ] Offline nüsha 2 yerinde ve okunaklı (6 ayda bir kontrol)
- [ ] `NEXTAUTH_SECRET` ve DB parolaları için de aynı prosedür önerilir
      (kritiklik daha düşük: bunlar kayıpta yeniden üretilebilir, MASTER_KEY üretilemez).

---

## 2. Cloud SQL — yedekten geri dönüş

### 2.1 Yedek yapılandırması (bir kez, doğrula)

```bash
# Otomatik günlük yedek + PITR (point-in-time recovery) açık mı?
gcloud sql instances describe $SQL \
  --format='value(settings.backupConfiguration.enabled, settings.backupConfiguration.pointInTimeRecoveryEnabled)'

# Kapalıysa aç (gece 03:00 UTC yedeği + 7 gün WAL saklama):
gcloud sql instances patch $SQL \
  --backup-start-time=03:00 \
  --enable-point-in-time-recovery \
  --retained-transaction-log-days=7
```

Ek olarak haftalık **mantıksal yedek** (bölge felaketine ve instance silinmesine
karşı, GCS'e):

```bash
# Cloud SQL servis hesabına bucket yazma izni verdikten sonra:
gcloud sql export sql $SQL gs://$DATA_BUCKET/backups/hukuk_emsal_$(date +%Y%m%d).sql.gz \
  --database=hukuk_emsal
```

- [ ] Otomatik yedek + PITR açık
- [ ] Haftalık `sql export` cron'u (Cloud Scheduler veya elle, pazartesi)
- [ ] `gs://$DATA_BUCKET/backups/` altında son 4 haftanın dosyası duruyor

### 2.2 Geri dönüş — Senaryo A: veri bozulması / yanlış silme (aynı instance)

PITR ile bozulmadan **hemen önceki ana** klonla (mevcut instance'a dokunma):

```bash
gcloud sql instances clone $SQL ${SQL}-restore \
  --point-in-time='2026-07-02T10:30:00Z'   # UTC, bozulmadan önceki an
```

Sonra:
1. Klona Cloud SQL Auth Proxy ile bağlan, veriyi doğrula
   (`psql`: kritik tablolarda satır sayıları, en son kayıt zaman damgaları).
2. İki seçenek:
   - **Tam geçiş:** Secret Manager'daki `DATABASE_URL` / `SERVICE_DATABASE_URL` /
     `ADMIN_DATABASE_URL` secret'larına klonun bağlantı adıyla **yeni sürüm** ekle,
     `hukuk-api`'yi yeni Cloud SQL instance bağlantısıyla yeniden deploy et
     (cloudbuild `_SQL_INSTANCE` substitution'ı güncellenir).
   - **Kısmi kurtarma:** yalnızca bozulan tabloları klondan `pg_dump -t tablo` ile
     alıp prod'a geri yükle.
3. İş bitince klonu sil veya yeni prod yap.

### 2.3 Geri dönüş — Senaryo B: instance/bölge tamamen kayıp

1. Yeni instance kur (`DEPLOY_GCP.md` Bölüm 2: `POSTGRES_16`, aynı kullanıcılar
   `hukuk` + `app_user`).
2. En güncel mantıksal yedeği içe aktar:
   ```bash
   gcloud sql import sql ${SQL}-new gs://$DATA_BUCKET/backups/hukuk_emsal_YYYYMMDD.sql.gz \
     --database=hukuk_emsal
   ```
3. `app_user` GRANT'lerini doğrula (`DEPLOY_GCP.md` Bölüm 4 notu) — export/import
   sonrası GRANT'ler genelde korunur, yine de `\dp` ile kontrol et.
4. DSN secret'larına yeni sürüm ekle, api'yi yeni `_SQL_INSTANCE` ile deploy et.
5. RLS'i doğrula: `python -m scripts.verify_rls` (proxy üzerinden).

> **Not — pgvector:** Emsal RAG verisi (187K chunk) artık **pgvector'da**, yani
> Cloud SQL yedeğinin içindedir. Ayrı vektör DB yedeği gerekmez; ancak restore
> sonrası HNSW indekslerinin geldiğini doğrula
> (`\di` ile indeks listesi + örnek bir arama sorgusu).

### 2.4 Railway alternatifi

Railway Postgres kullanılıyorsa: Railway'in otomatik yedeği sınırlıdır —
**günlük `pg_dump`'ı kendin al**:

```bash
pg_dump "$DATABASE_URL" -Fc -f hukuk_emsal_$(date +%Y%m%d).dump
# Geri dönüş:
pg_restore -d "$NEW_DATABASE_URL" --clean --if-exists hukuk_emsal_YYYYMMDD.dump
```

Dump'ları Railway dışında bir yerde (GCS/S3/lokal + harici disk) sakla.

---

## 3. GCS tenant-storage yedeği

`gs://$TS_BUCKET` UYAP şifreli tenant belgelerini tutar (Cloud Run'a gcsfuse
mount). İçerik DEK ile şifreli olduğundan yedeğin kendisi düşük riskli, ama
kayıpta belgeler gider.

### 3.1 Koruma (bir kez kur)

```bash
# 1) Nesne sürümleme — yanlış silme/üzerine yazmaya karşı:
gcloud storage buckets update gs://$TS_BUCKET --versioning

# 2) Eski sürümleri 30 gün sonra temizleyen lifecycle (maliyet kontrolü):
#    lifecycle.json: {"rule":[{"action":{"type":"Delete"},
#      "condition":{"isLive":false,"daysSinceNoncurrentTime":30}}]}
gcloud storage buckets update gs://$TS_BUCKET --lifecycle-file=lifecycle.json

# 3) Günlük çapraz yedek (ayrı bucket, tercihen farklı region):
gcloud storage buckets create gs://${TS_BUCKET}-backup --location=europe-west4 2>/dev/null || true
gcloud storage rsync -r gs://$TS_BUCKET gs://${TS_BUCKET}-backup
```

Günlük rsync'i Cloud Scheduler + Cloud Run job veya Storage Transfer Service
ile zamanla.

### 3.2 Geri dönüş

```bash
# Tek dosya (sürümlemeden):
gcloud storage ls -a gs://$TS_BUCKET/tenants/<tenant_id>/     # generation numaralarını gör
gcloud storage cp gs://$TS_BUCKET/path/dosya#GENERATION gs://$TS_BUCKET/path/dosya

# Toplu (yedek bucket'tan):
gcloud storage rsync -r gs://${TS_BUCKET}-backup gs://$TS_BUCKET
```

> **Dikkat:** Belgeler tenant DEK'i ile şifrelidir. Dosyayı geri getirmek
> yetmez — ilgili tenant'ın `tenant_encryption_keys` satırı da DB'de olmalı.
> `purge_deleted.py` ile crypto-shred edilmiş tenant'ın dosyaları **bilerek**
> çözülemezdir; bu bir veri kaybı değil, KVKK m.7 gereğidir.

`gs://$DATA_BUCKET` (parquet + eski chroma verisi) salt-okunur ve lokalden
yeniden üretilebilir; sürümleme yeterli, çapraz yedek opsiyonel.

---

## 4. Restore tatbikatı checklist'i (6 ayda bir, ilki lansmandan önce)

Tatbikat prod'a dokunmaz; klon + geçici ortam üzerinde yapılır.

- [ ] **T-0:** Tatbikat başlangıç saatini not et.
- [ ] MASTER_ENCRYPTION_KEY offline nüshasını kasadan çıkar, Secret Manager'daki
      `latest` sürümle **birebir aynı** olduğunu doğrula.
- [ ] Cloud SQL'i PITR ile klonla (`2.2`), klon üzerinde:
  - [ ] Migration seviyesi doğru (en son migration uygulanmış görünüyor).
  - [ ] Kritik tablolarda satır sayıları makul (users, tenants,
        tenant_encryption_keys, subscriptions, emsal chunk tablosu).
  - [ ] `python -m scripts.verify_rls` → 6/6 geçiyor.
- [ ] Geçici bir `hukuk-api` revizyonunu klon DSN'i + **offline nüshadan girilen**
      MASTER_ENCRYPTION_KEY ile ayağa kaldır (ayrı Cloud Run servisi, public değil):
  - [ ] `/api/health` 200.
  - [ ] Test tenant'ında şifreli bir alan **çözülerek** okunabiliyor
        (master key + DEK zinciri çalışıyor — tatbikatın asıl amacı budur).
  - [ ] pgvector emsal araması sonuç döndürüyor.
- [ ] tenant-storage: yedek bucket'tan rastgele 3 dosya geri kopyala, uygulama
      üzerinden açılabildiğini doğrula.
- [ ] **T-son:** Toplam süreyi not et → gerçekleşen RTO. Aşağıdaki tabloyla
      karşılaştır; aşım varsa neden analizini yaz.
- [ ] Geçici servis ve klonu **sil**, tatbikat sonucunu tarihiyle bu dosyanın
      altına işle.

| Tatbikat tarihi | Süre (RTO gerçekleşen) | Sonuç | Notlar |
|---|---|---|---|
| _(ilk tatbikat — doldurulacak)_ | | | |

---

## 5. RTO / RPO hedef tablosu

| Bileşen | Senaryo | RPO (max veri kaybı) | RTO (max kesinti) | Mekanizma |
|---|---|---|---|---|
| Cloud SQL (uygulama DB + pgvector) | Veri bozulması / yanlış silme | ≤ 5 dk | 2 saat | PITR klon (2.2) |
| Cloud SQL | Instance/bölge kaybı | ≤ 24 saat (haftalık export ise ≤ 7 gün — günlük export önerilir) | 4 saat | `sql export` → yeni instance (2.3) |
| MASTER_ENCRYPTION_KEY | Secret Manager erişim kaybı | 0 (kayıp kabul edilemez) | 1 saat | Sürümleme + 2 offline nüsha (1) |
| GCS tenant-storage | Yanlış silme | 0 | 1 saat | Nesne sürümleme (3.1) |
| GCS tenant-storage | Bucket/bölge kaybı | ≤ 24 saat | 4 saat | Günlük çapraz rsync (3.1) |
| Cloud Run servisleri | Servis/revizyon bozulması | 0 (stateless) | 30 dk | Önceki revizyona rollback veya `cloudbuild.yaml` ile yeniden deploy |
| Secret'lar (DSN, iyzico, SMTP…) | Yanlış değer/silme | 0 | 30 dk | Secret Manager sürüm geçmişi |

> RPO'yu düşürmek istersen: Cloud SQL export'unu günlük yap (Cloud Scheduler) ve
> tenant-storage rsync'ini Storage Transfer Service ile saatlik çalıştır.

## 6. Felaket anında ilk 15 dakika (özet akış)

1. Belirtiyi sınıflandır: DB mi (5xx + log'da DSN/SQL hataları), storage mı
   (belge açılmıyor), key mi (decrypt hataları), servis mi (`/api/health` down)?
   → `gcloud run services logs read hukuk-api --region=$REGION --limit=50`
2. Servis sorunuysa önce **önceki revizyona rollback**:
   `gcloud run services update-traffic hukuk-api --region=$REGION --to-revisions=<onceki>=100`
3. DB sorunuysa Bölüm 2; storage ise Bölüm 3; decrypt hatasıysa Bölüm 1
   (secret sürümü yanlış mı değişmiş? `gcloud secrets versions list`).
4. Kullanıcıya durum bildirimi (status sayfası / e-posta) — 30 dk'yı aşacak
   kesintide zorunlu.
