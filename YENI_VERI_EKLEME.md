# Yeni emsal karar ekleme — artımlı akış

Sisteme yeni karar eklerken **her şey baştan işlenmez.** Pahalı olan tek adım
(embedding) yalnızca yeni chunk'lar için çalışır. Aşağıda ne artımlı, ne değil
ve hangi tuzaklara dikkat etmek gerektiği var.

---

## Normal akış

```bash
# 1) Yeni kararları çek — ARTIMLI: son koşudan bu yana olanlar
python scripts/run_scraper.py --source yargitay --since-auto
python scripts/run_scraper.py --source danistay --since-auto

# 2) Parquet'i yeniden üret (tam yeniden yazım — ama BEDAVA, sadece CPU)
python -m pipelines.export_final

# 3) Chunk'la (tam yeniden yazım — yine bedava)
python -m pipelines.chunk

# 4) Embed et — SADECE YENİ chunk'lar API'ye gider
python -m pipelines.embed --prune  # --recreate KULLANMAYIN
```

`--prune`: metni kısalan kararlardan artakalan **yetim chunk**'ları siler
(bkz. aşağıdaki 3. boşluk). Yalnızca parquet'te BULUNAN kararların yetimlerini
siler — yarım bir parquet ile veri tabanını boşaltmaz.

İmleçleri görmek için:

```bash
python scripts/run_scraper.py --source yargitay --durum
```

```
kaynak       son karar       toplam  son koşu
yargitay     2026-07-14      48,213  2026-08-06T20:11:03+00:00
```

**4. adım kritik:** `pipelines/embed.py` tabloda zaten bulunan `chunk_id`'leri
atlar. 100.000 mevcut chunk'ınız varsa ve 500 yeni karar eklediyseniz,
yalnızca o 500 kararın chunk'ları embed edilir. **`--recreate` bayrağı tabloyu
BOŞALTIR ve her şeyi yeniden embed eder — tam faturayı ödersiniz.** Yalnızca
embedding modelini değiştirdiğinizde kullanın.

---

## Ne artımlı, ne değil

| Adım | Artımlı mı? | Maliyet |
|---|---|---|
| Scraper (indirme) | ✅ Evet — indirilmiş ID'ler atlanır | Ağ + zaman |
| `export_final` (parquet) | ❌ Tam yeniden üretim | Bedava (CPU, dakikalar) |
| `chunk` | ❌ Tam yeniden üretim | Bedava (CPU, dakikalar) |
| **`embed`** | ✅ **Evet — sadece yeni chunk'lar** | **API — asıl maliyet burada** |
| pgvector HNSW indeksi | ✅ Yeni satırlar mevcut indekse eklenir | Yok |
| Tam metin GIN indeksi | ✅ Aynı şekilde | Yok |

İndeksler **hiçbir zaman** yeniden inşa edilmez; Postgres yeni satırları var
olan indekse ekler. `32_`/`33_` migration'larını bir daha çalıştırmanıza gerek
yoktur.

`chunk_id` biçimi: `{karar_id}_c000`, `_c001`, ... Yani kimlik **kararın
kendisinden** türer, sırasından değil. Yeni karar eklemek mevcut chunk_id'leri
kaydırmaz — artımlı embed'in çalışmasının sebebi budur.

---

## ⚠️ Üç boşluk

### 1. Parquet imaja gömülü → her veri güncellemesi yeniden dağıtım ister

Karar **detay sayfası** metni `data/final/all_decisions.parquet`'ten okunur ve
bu dosya Docker imajına gömülür (`Dockerfile.api`, Cloud Build GCS'ten indirir).
Yani yeni kararlar arama sonuçlarında (pgvector) hemen görünür, ama detay
sayfalarında görünmesi için:

```bash
gsutil cp data/final/all_decisions.parquet gs://hukuk-emsal-bucket/
./infra/gcp/setup_gcp.sh deploy
```

Bu, veri ile kod dağıtımını birbirine bağlıyor. İleride parquet'i imajdan
çıkarıp doğrudan GCS'ten (veya tam metni Postgres'ten) okumak bu bağı koparır.

### 2. Tarih imleci — ✅ KAPATILDI (kaynak başına farklı derinlikte)

`--since-auto` artık `data/scrape_state.json` içindeki imleci kullanıyor.
İmleç, **görülen en yeni KARAR tarihidir** (koşu tarihi değil) ve yalnızca
ileri yönde güncellenir — yarım kalan bir koşu imleci geri çekmez.

30 günlük güvenlik payı var: kaynaklar geriye dönük yayın yapabildiği için
(bugün yayımlanan bir karar 3 hafta önce verilmiş olabilir) imleç olduğu gibi
kullanılsa aradan karar kaçardı.

| Kaynak | Filtre nerede? | Kazanç |
|---|---|---|
| **yargitay** | ✅ Sunucu (`baslangicTarihi`) | Eski sayfalar hiç gezilmez |
| **danistay** | ⚠️ İstemci (payload tarih kabul etmiyor) | Liste yine tam gelir, ama eski kararlar için **pahalı detay isteği yapılmaz** |
| hudoc / aym | ❌ Desteklenmiyor | `--since` verilirse uyarı basıp tam tarama yapar |

Danıştay'ın API'si tarih parametresi kabul etmediği için oradaki kazanç
kısmi. API'de böyle bir alan keşfedilirse `_build_payload`'a eklenmeli;
`SINCE_DESTEKLI` kümesi de güncellenmeli.

### 2b. İŞARETSİZ temizlenmiş chunk'lar — ✅ KAPATILDI (`--bayat-tara`)

2026-08-07'deki HTML onarımında ilk koşular metni temizledi ama
`embedding_model` sütununa BAYAT işaretini **yazmadı** (o güvenlik sonradan
eklendi). Sonuç: metni temiz, **vektörü HTML çöpünden üretilmiş** ~21.500
satır. DB'ye bakarak bunlar hiç kirli olmamış satırlardan ayırt edilemez;
`--reembed` onları sessizce atlar ve arama kalitesi bozuk kalır.

Kanıt **parquet'te**: parquet onarılmadığı sürece kirli metni hâlâ içerir.

```bash
# Kirli KARAR kimliklerini parquet'ten çıkar, o kararların TÜM chunk'larını
# BAYAT işaretle. Parquet onarımından ÖNCE çalıştırın.
python -m scripts.repair_html_kirliligi --skip-db --bayat-tara
```

Yalnızca `embedding_model IS NULL` satırlar işaretlenir — onarımdan sonra
düzgün embed edilmiş satırların imzası ezilmez. Zaten BAYAT olanlara
dokunulmaz, temiz kararlar hiç işaretlenmez (gereksiz API maliyeti doğmasın).

Parquet zaten onarıldıysa yedekten okuyun:

```bash
DECISIONS_PARQUET=data/final/all_decisions.parquet.html-kirli-yedek \
  python -m scripts.repair_html_kirliligi --skip-db --bayat-tara
```

### 3. Yetim (orphan) chunk temizliği — ✅ KAPATILDI (`--prune`)

Bir kararın metni **kısalırsa** chunk sayısı azalır. Örnek: HTML temizliğinden
sonra yeniden chunk'larsanız, 25 chunk'lık bir karar 20 chunk'a düşebilir.
`_c020`..`_c024` chunk'ları `rag_chunks` tablosunda **sonsuza dek kalır** —
`embed.py` silme yapmaz. Bu yetimler aramada eski/kirli metinle çıkmaya
devam eder.

**Ne zaman önemli:** yalnızca mevcut kararların metni değiştiğinde. Yeni karar
eklemek bu sorunu yaratmaz.

`python -m pipelines.embed --prune` bunları siler. **Güvenlik:** yalnızca
parquet'te BULUNAN kararların yetimleri silinir. Parquet'ten tamamen düşmüş
bir karara (eksik koşu, bozuk dosya) dokunulmaz — yarım bir parquet ile tüm
veri tabanını silmemek için.

Kontrol sorgusu:

```sql
SELECT decision_id, count(*) AS db_chunk
FROM rag_chunks GROUP BY decision_id
ORDER BY db_chunk DESC LIMIT 20;
```

---

## Model değiştirirseniz

Embedding modelini değiştirmek **tüm vektörleri geçersiz kılar** — farklı
semantik uzaylar karşılaştırılamaz. `pipelines/embed.py` bunu tespit edip
durur (`embedding_model` kolonu sayesinde). O durumda tam faturayı ödemek
zorundasınız:

```bash
python -m pipelines.embed --recreate
```

Bu yüzden model seçimini erken sabitleyin.

---

## Kontrol listesi — yeni veri sonrası

```sql
-- Chunk sayısı arttı mı?
SELECT count(*) FROM rag_chunks;

-- Embed edilmemiş (bayat) kalan var mı?
SELECT embedding_model, count(*) FROM rag_chunks GROUP BY 1;

-- Yeni kaynak/daire geldi mi?
SELECT source, court_chamber, count(*) FROM rag_chunks
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20;
```

Ardından kalite ölçümü:

```bash
python -m scripts.rag_eval --min-recall 0.70
```

Yeni veri recall'ı düşürdüyse (ör. alakasız bir alan eklendi) burada görürsünüz.
