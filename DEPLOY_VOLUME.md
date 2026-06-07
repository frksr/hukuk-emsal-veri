# Cloud Deploy — Kalıcı Volume + Vektör DB Seed

Kod git'ten çekilir; **büyük veri git'te TUTULMAZ** (bkz. `.gitignore`). Vektör DB
ve dosyalar kalıcı bir volume'da yaşar ve bir kez seed edilir.

## Volume'da yaşayan veriler

| Yol (volume) | Env | İçerik | Tip |
|---|---|---|---|
| `/data/chroma_db` | `CHROMA_DIR` | Public emsal vektör DB (~2GB) | salt-okunur, seed |
| `/data/final/all_decisions.parquet` | `DECISIONS_PARQUET` | Tam karar metni | salt-okunur, seed |
| `/data/tenant_chroma` | `TENANT_CHROMA_DIR` | Per-tenant vektör (kullanıcı yüklemeleri) | **OKU-YAZ, runtime** |
| `/data/tenant_storage` | `TENANT_STORAGE_ROOT` | Per-tenant şifreli dosyalar | **OKU-YAZ, runtime** |

> `tenant_chroma` ve `tenant_storage` runtime'da büyür → volume **kalıcı olmalı**
> (redeploy'da silinmemeli). Tek instance varsayımıyla çalışır; **çok instance**'a
> çıkacaksan bu ikisi paylaşılan depo gerektirir (managed Qdrant + S3) — o zaman
> "B" planına geçeriz.

## 1) Volume oluştur + env ayarla

**Fly.io**
```bash
fly volumes create hukuk_data --size 5 --region fra
```
`fly.toml`:
```toml
[mounts]
  source = "hukuk_data"
  destination = "/data"

[env]
  CHROMA_DIR = "/data/chroma_db"
  DECISIONS_PARQUET = "/data/final/all_decisions.parquet"
  TENANT_CHROMA_DIR = "/data/tenant_chroma"
  TENANT_STORAGE_ROOT = "/data/tenant_storage"
```

**Railway**: Service → Volumes → Mount path `/data`. Sonra Variables'a yukarıdaki
`CHROMA_DIR` vb. değerlerini ekle.

## 2) Veriyi paketle (lokalde, bir kez)

```bash
# Vektör DB tarball'ı (chroma_db/ önekiyle)
tar czf chroma_db.tgz -C data chroma_db
# (Opsiyonel) parquet
cp data/final/all_decisions.parquet .
```

## 3) Volume'u seed et (bir kez, idempotent)

`scripts/seed_volume.py` hedef doluysa atlar.

**Fly.io** — tarball'ı volume'a yükleyip makinede aç:
```bash
fly ssh console -C "mkdir -p /data"
fly sftp shell        # → put chroma_db.tgz /data/chroma_db.tgz ; put all_decisions.parquet /data/final/all_decisions.parquet
fly ssh console -C "cd /app && python -m scripts.seed_volume --source /data/chroma_db.tgz"
```

**Railway / herhangi bir platform** — tek seferlik bir URL'den (presigned S3/R2,
geçici link) çek (veri yine volume'da kalır):
```bash
# Service shell / one-off:
python -m scripts.seed_volume --source "https://<gecici-link>/chroma_db.tgz"
```

**Lokal mount** (volume'u lokal makineye bağladıysan):
```bash
CHROMA_DIR=/mnt/vol/chroma_db python -m scripts.seed_volume --source ./data/chroma_db
```

## 4) Doğrula

```bash
curl https://<api>/api/health    # rag.chunk_count > 0 ve available:true olmalı
```
Seed edilmemişse uygulama ÇÖKMEZ: arama boş döner, `/api/health` `rag.available:false`
raporlar (log'da "seed gerekli?" uyarısı).

## Yeniden üretim (alternatif)

Veri kaybolursa veya yeni dataset'le güncellenecekse, pipeline ile yeniden üret:
```bash
python -m pipelines.embed --input data/final/chunks.parquet --chroma-dir data/chroma_db --recreate
```
Sonra (2) ve (3) ile tekrar paketleyip seed et.
