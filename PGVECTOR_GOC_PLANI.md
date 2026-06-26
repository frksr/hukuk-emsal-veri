# Vektör Arama Göç Planı — Chroma → pgvector + API Embedding

**Tarih:** 2026-06-26
**Amaç:** Cloud Run'daki OOM (exit 137) çökmelerini kalıcı çözmek, maliyeti düşürmek
ve büyüyen emsal karar korpusuna hazır, ölçeklenebilir bir vektör arama mimarisi kurmak.

---

## 1. Problem ve kök neden

Loglarda `Killed` + `Container called exit(137)` görülüyor — bu klasik **OOM (bellek
taşması)** imzası. Mevcut kurulumda her Cloud Run instance'ı, startup'taki
`_rag_warmup` görevinde aynı anda şunları RAM'e yüklüyor:

- `intfloat/multilingual-e5-base` embedding modeli (torch fp32 ile ~2 GB),
- ChromaDB koleksiyonunu (HNSW indeksi tamamen belleğe).

4 GiB limit bu zirvede aşılıyor, Cloud Run instance'ı öldürüyor, tarayıcı
`ERR_CONNECTION_RESET` alıyor. "Arada bir" olması: indeks RAM'i limite yaklaşınca
ilk ağır istek taşmayı tetikliyor.

### Neden sadece "belleği artır" çözüm değil
`--memory=8Gi` + `--min-instances=1` instance'ı 7/24 açık tutar; trafik olmasa bile
ödenir ve maliyeti ~2 katına çıkarır. Asıl pahalı kalem bellek değil, **modeli ve
indeksi her instance'ın RAM'ine yüklemek.** Büyüdükçe (yeni kararlar eklendikçe) bu
model sürdürülemez: her veri eklemede image yeniden build/deploy gerekir ve indeks
her instance'ta şişer.

---

## 2. Hedef mimari

İki değişiklik birlikte sorunu kökten çözer:

### 2.1 Embedding'i API'ye taşı (container'da model yok)
- Embedding'ler **Google API** (`text-embedding-004`, 768-dim) ile üretilir.
- Container'da torch / sentence-transformers KALMAZ → imaj küçülür, **soğuk
  başlangıç hızlanır**, bellek 1 GiB'a iner.
- Modelsiz container → **`min-instances=0` (sıfıra ölçek)** gerçekten çalışır:
  boştayken maliyet ≈ 0.

### 2.2 Vektör deposunu Cloud SQL'e (pgvector) taşı
- Vektörler, zaten parasını ödediğin **Cloud SQL Postgres**'te `pgvector` ile tutulur.
- Yeni karar eklemek = `INSERT` → **image rebuild/redeploy yok.**
- İndeks DB'de yaşar, tüm instance'lar paylaşır, managed DB ile ölçeklenir.
- `asyncpg` zaten kurulu; RAG katmanı için sync erişim `psycopg` ile eklenir.

### 2.3 Sorgu embedding cache'i
- Aynı/normalize sorgunun embedding vektörü process içi **LRU + TTL cache**'te tutulur.
- Hukuk aramaları çok tekrar eder → API çağrılarını ve gecikmeyi ciddi düşürür.

### Mimari şema
```
İstemci → Cloud Run (FastAPI, 1Gi, min=0)
              │  embed_query(metin)  ── cache hit? ─→ vektör
              │        └─ cache miss ─→ Google Embedding API
              ▼
        Cloud SQL (pgvector)  ── ORDER BY embedding <=> $1 LIMIT k
```

---

## 3. Veri modeli (Cloud SQL / pgvector)

`infra/db/19_pgvector.sql` ile uygulanır.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Public emsal kararlar (10K+ ve büyüyecek)
CREATE TABLE rag_chunks (
  chunk_id      TEXT PRIMARY KEY,
  decision_id   TEXT,
  chunk_index   INT,
  document      TEXT NOT NULL,
  source        TEXT,
  court_chamber TEXT,
  case_no       TEXT,
  decision_no   TEXT,
  decision_date TEXT,
  topic_tags    TEXT,
  source_url    TEXT,
  embedding     vector(768) NOT NULL
);
CREATE INDEX rag_chunks_embedding_idx
  ON rag_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX rag_chunks_source_idx ON rag_chunks (source);

-- Tenant (kullanıcı) dosyaları — izolasyon: explicit tenant_id + (önerilen) RLS
CREATE TABLE tenant_rag_chunks (
  chunk_id    TEXT PRIMARY KEY,
  tenant_id   UUID NOT NULL,
  document_id TEXT NOT NULL,
  chunk_index INT,
  document    TEXT NOT NULL,
  meta        JSONB DEFAULT '{}'::jsonb,
  embedding   vector(768) NOT NULL
);
CREATE INDEX tenant_rag_chunks_embedding_idx
  ON tenant_rag_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX tenant_rag_chunks_tenant_idx ON tenant_rag_chunks (tenant_id);
```

> **Not (dim sınırı):** pgvector HNSW indeksi ≤ 2000 boyut destekler. Bu yüzden
> 768-dim model seçildi (`text-embedding-004`). `gemini-embedding-001` kullanılacaksa
> `output_dimensionality=768` ile kısaltılmalı (Matryoshka; kalite korunur).

> **İzolasyon:** Önceki Chroma kurulumu tenant başına ayrı klasörle uygulama
> seviyesinde izole ediyordu. Yeni kodda her tenant sorgusu **`WHERE tenant_id = $1`**
> ile filtrelenir (kod tenant_id'yi her zaman geçirir). Ek güvenlik için RLS politikası
> SQL dosyasında opsiyonel olarak verilir.

---

## 4. Kod değişiklikleri

| Dosya | Değişiklik |
|------|-----------|
| `services/embeddings.py` *(yeni)* | Provider-agnostic `embed_query` / `embed_passages`; Google provider; sorgu cache'i; (opsiyonel) lokal e5 provider — Faz 2 kaçış kapısı. |
| `services/pg.py` *(yeni)* | RAG için sync `psycopg` bağlantı havuzu + pgvector kayıt. |
| `services/rag.py` | Chroma yerine pgvector sorgusu; `search()` imzası AYNI kalır (caller'lar değişmez). Parquet fonksiyonları (`get_full_decision`, `list_decisions`) aynen kalır. |
| `services/tenant_rag.py` | `index_document` / `search_tenant` / `delete_*` pgvector'e geçer; imzalar korunur. |
| `pipelines/embed.py` | Google embedding + Postgres `INSERT`/`upsert` (Chroma yazımı kaldırılır). |
| `requirements.txt` | `chromadb`, `sentence-transformers` çıkar; `psycopg[binary]`, `psycopg-pool`, `pgvector` eklenir. |
| `Dockerfile.api` | `seed_data/chroma_db` + parquet kopyalama kaldırılır (parquet hâlâ gerekiyorsa korunur). |
| `cloudbuild.yaml` | `--memory=1Gi`, `--min-instances=0`, `fetch-data` adımı sadeleştirilir. |

**Geriye dönük uyumluluk:** Tüm public fonksiyon imzaları (`search`, `search_tenant`,
`index_document`, `get_collection_stats`, ...) korunur; router/servis caller'ları
değişmez.

---

## 5. Göç adımları (uygulama sırası)

1. **Şema:** Cloud SQL'de `infra/db/19_pgvector.sql` çalıştır.
2. **Env/Secret:** `GOOGLE_API_KEY` zaten var. Yeni env: `EMBEDDING_PROVIDER=google`,
   `EMBEDDING_API_MODEL=text-embedding-004`, `EMBEDDING_DIM=768`,
   `RAG_DATABASE_URL` (yoksa `DATABASE_URL`).
3. **Korpusu yeniden embed et (bir kez):**
   `python -m pipelines.embed --input data/final/chunks.parquet --provider google`
   → vektörler `rag_chunks` tablosuna yazılır. (Tek seferlik maliyet ~$7 mertebesinde.)
4. **Kod:** RAG servisleri pgvector'e geçirilmiş haliyle deploy edilir.
5. **Deploy:** `cloudbuild.yaml` 1Gi / min=0 ile push.
6. **Doğrula:** `/api/health` rag.available=true, örnek arama sonuç döndürüyor.
7. **Temizlik:** Chroma GCS bucket'ı ve seed adımı kaldırılır.

---

## 6. Maliyet ve ölçeklenme

### Sorgu başına embedding maliyeti (Google ~$0.15 / 1M token, ~200 token/sorgu)
| Aylık arama | Maliyet |
|---|---|
| 100.000 | ~$3 |
| 1.000.000 | ~$30 |
| 1.000.000 (uzun sorgu, ~1000 token) | ~$150 |

Ücretsiz emsal arama sunulsa bile, aylık milyonlarca aramaya kadar maliyet
ihmal edilebilir. Gemini'nin ücretsiz kotası başlangıçta muhtemelen yeterli.

### Faz planı (büyümeye hazır)
- **Faz 1 (şimdi):** Google API + pgvector + `min-instances=0`. Boşta ≈ 0 maliyet.
- **Faz 2 (trafik patlayınca):** API maliyeti, kendi modelini barındırmaktan pahalıya
  geldiği noktada (kabaca **aylık ~1M sorgu**; sürekli açık küçük instance ~$30-60/ay)
  `services/embeddings.py` içindeki provider'ı **self-hosted e5'e** çevir. Kod değişmez
  (soyutlama katmanı), tek seferlik yeniden indeksleme gerekir. pgvector her iki fazda
  da depo olarak kalır.

### Sorgu cache'i
Process içi LRU + TTL; tekrar eden aramalarda embedding API çağrısı yapılmaz →
patlama riskini ve gecikmeyi azaltır.

---

## 7. Riskler ve önlemler

- **Embedding kalite farkı (e5 → Google):** Google çok dilli embedding Türkçe'de
  güçlü; genelde eşit/daha iyi. Göç sonrası örnek sorgularla karşılaştırma önerilir.
- **pgvector dim sınırı (≤2000):** 768-dim seçilerek aşıldı.
- **Tenant izolasyonu:** explicit `WHERE tenant_id` + opsiyonel RLS.
- **Tek seferlik re-embed maliyeti/süresi:** küçük; batch + retry ile yapılır.
- **Sağlayıcı bağımlılığı:** soyutlama katmanı sayesinde provider değiştirmek
  config + re-index meselesi; kod kilidi yok.
