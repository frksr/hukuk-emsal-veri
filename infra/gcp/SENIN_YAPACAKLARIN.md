# Senin Yapacakların — GCP Kurulum & Deploy

Bu klasöre 3 dosya hazırladım. Sen sadece **değerleri doldurup** scriptleri sırayla
çalıştıracaksın. Kaynak oluşturma/secret bağlama/deploy işini scriptler yapıyor.

| Dosya | Ne işe yarar | Senin işin |
|---|---|---|
| `deploy.env` | Proje/DB/bucket değerleri (tek kaynak) | `# DOLDUR` satırlarını doldur |
| `secrets.env.example` | API/iyzico/SMTP sırları şablonu | kopyala → `secrets.env` yap → doldur |
| `setup_gcp.sh` | Kaynakları kurar + deploy eder | çalıştır |
| `migrate_db.sh` | DB şeması + admin | çalıştır |

> **Not:** `deploy.env` ve `secrets.env` parola içerir; ikisi de `.gitignore`'a
> eklendi, git'e gitmez.

---

## Adım 1 — `deploy.env`'i doldur

`infra/gcp/deploy.env` dosyasını aç. Bilinen değerleri (instance `hukuk-emsal`,
db `hukuk-emsal-db`, bucket `hukuk-emsal-bucket`) önceden yazdım. Sen şunları gir:

- `PROJECT_ID` → gerçek GCP proje ID'n
- `REGION` → instance hangi bölgedeyse (varsayılan `europe-west1`)
- `DB_OWNER_PASSWORD` → DB owner (`hukuk`) parolası
- `DB_APP_PASSWORD` → app kullanıcısı (`app_user`) parolası
- `APP_ADMIN_PASSWORD` → uygulamadaki ilk admin parolası

> DB kullanıcı adlarını (`hukuk`, `app_user`) zaten farklı kurduysan, adları da
> kendine göre değiştir. Bu kullanıcılar yoksa script oluşturur; varsa parolasını
> günceller.

> `TS_BUCKET` (UYAP belgeleri için **yazılabilir** ikinci bucket) `hukuk-emsal-tenant`
> olarak ayarlı; yoksa script oluşturur. Ana `hukuk-emsal-bucket` salt-okunur tohum
> verisi içindir, ikisi ayrı olmalı.

---

## Adım 2 — `secrets.env`'i oluştur ve doldur

```bash
cd infra/gcp
cp secrets.env.example secrets.env
```

`secrets.env` içindeki `__DOLDUR__` alanlarını doldur:
`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, iyzico anahtarları + 4 plan kodu, SMTP bilgileri.

- `NEXTAUTH_SECRET` ve `MASTER_ENCRYPTION_KEY`'i **boş bırak** → script otomatik üretir.
- DB bağlantı adresleri (`DATABASE_URL` vb.) buraya GİRİLMEZ → script `deploy.env`'deki
  DB parolalarından otomatik üretir.

---

## Adım 3 — Veri kontrolü (vektör tohumu)

`hukuk_kararlari` collection'ı, build sırasında `gs://hukuk-emsal-bucket/chroma_db`'den
gelir. İki durum:

- **Lokalde `data/chroma_db` varsa:** bir şey yapma, `setup_gcp.sh` otomatik yükler.
- **Yoksa:** veriyi elle bucket'a yükle (yedeğin neredeyse):
  ```bash
  gcloud storage rsync -r ./data/chroma_db gs://hukuk-emsal-bucket/chroma_db
  gcloud storage cp ./data/final/all_decisions.parquet gs://hukuk-emsal-bucket/all_decisions.parquet
  ```
  Bu veri olmadan arama/RAG çalışmaz (loglarındaki "collection does not exist" tam bu).

---

## Adım 4 — Kurulumu çalıştır (kaynaklar + secret + IAM)

```bash
chmod +x infra/gcp/setup_gcp.sh infra/gcp/migrate_db.sh
./infra/gcp/setup_gcp.sh all
```

Bu komut sırayla: API'leri açar, Artifact Registry repo'sunu, bucket'ları, DB
kullanıcılarını, **tüm secret'ları** oluşturur ve IAM izinlerini verir. Var olanları
atlar (idempotent — tekrar çalıştırman güvenli).

> İstersen tek tek de çalıştırabilirsin:
> `./infra/gcp/setup_gcp.sh secrets`, `... iam`, `... buckets` vb.

---

## Adım 5 — Veritabanı şemasını kur

```bash
./infra/gcp/migrate_db.sh
```

Cloud SQL Auth Proxy'yi otomatik indirir, `scripts/init_db.py` ile 01–18
migration'larını uygular, `app_user` yetkilerini verir ve ilk admini oluşturur.

> Gereksinim: lokalde `python` + proje bağımlılıkları (`pip install -r requirements.txt`)
> ve `psql` kurulu olmalı. `gcloud auth login` yapılmış olmalı.

---

## Adım 6 — Deploy et (API + Web)

```bash
./infra/gcp/setup_gcp.sh deploy
```

`cloudbuild.yaml`'ı çalıştırır: `Dockerfile.api` ile backend'i (vektör verisi gömülü)
ve `web/Dockerfile` ile frontend'i build edip Cloud Run'a deploy eder, secret'ları ve
Cloud SQL'i bağlar. Bu, **mevcut tek/bozuk servisi de günceller** (port 8080'e taşır).

> Bundan sonra her `git push` (trigger kurduysan) ya da bu komut yeniden deploy eder;
> secret/DB tekrar kurmana gerek kalmaz.

---

## Adım 7 — Doğrula

```bash
./infra/gcp/setup_gcp.sh verify
```

Beklenen: `/api/health` → `"ok": true`, `rag` içinde sayı **> 0**, `llm.ok = true`.
Yeni loglarda artık `DATABASE_URL yok` / `collection does not exist` **görünmemeli**.

---

## Adım 8 — Domain (site açılması için son adım)

Site `https://hukukcuyapayzekasi.com` adresinden açılacaksa domain eşlemesi:

```bash
gcloud run domain-mappings create --service=hukuk-web \
  --domain=hukukcuyapayzekasi.com --region=$REGION
gcloud run domain-mappings create --service=hukuk-api \
  --domain=api.hukukcuyapayzekasi.com --region=$REGION
```

Çıkan DNS kayıtlarını alan adı sağlayıcına ekle. `NEXT_PUBLIC_*` build anında gömülü
olduğu için domain değişirse web yeniden build edilmeli (deploy komutunu tekrar çalıştır).

---

## Hızlı özet (kopyala-yapıştır sıra)

```bash
# 1-2-3: deploy.env doldur, secrets.env oluştur+doldur, (gerekirse) veri yükle
cd infra/gcp && cp secrets.env.example secrets.env   # sonra ikisini doldur
cd ../..

chmod +x infra/gcp/setup_gcp.sh infra/gcp/migrate_db.sh
./infra/gcp/setup_gcp.sh all        # kaynaklar + secret + IAM
./infra/gcp/migrate_db.sh           # DB şeması + admin
./infra/gcp/setup_gcp.sh deploy     # API + Web build & deploy
./infra/gcp/setup_gcp.sh verify     # health kontrol
```

## Sık karşılaşılan hatalar

- **`secret not found` deploy'da** → `setup_gcp.sh secrets`'i tekrar çalıştır; `secrets.env`
  doğru doldurulmuş mu kontrol et.
- **`collection does not exist` hâlâ** → `gs://hukuk-emsal-bucket/chroma_db` boş; Adım 3.
- **`permission denied` build'de** → `setup_gcp.sh iam` çalıştır (servis hesabı rolleri).
- **DB bağlantı hatası** → `deploy.env`'deki DB parolaları ile Cloud SQL'deki kullanıcı
  parolaları uyuşmuyor; `setup_gcp.sh dbusers` parolayı senkronlar.
