# Cloud SQL — 32_rag_hybrid_search çalıştırma adımları

Sırayla, kopyala-yapıştır. Her adımın altında ne göreceğiniz yazıyor.

**Cloud SQL Studio'da ÇALIŞTIRMAYIN.** Studio bağlantıyı birkaç dakikada
düşürür; `CREATE INDEX CONCURRENTLY` istemci koptuğunda iptal olur ve geriye
"invalid" bir indeks bırakır. Cloud Shell kullanın.

Ortam: instance `hukuk-emsal`, region `europe-west1` (cloudbuild.yaml'dan).

---

## ADIM 0 — Cloud Shell aç ve bağlan

Cloud Console sağ üstte terminal simgesi → **Cloud Shell**.

```bash
# Veritabanı adını hatırlamıyorsanız:
gcloud sql databases list --instance=hukuk-emsal

# Bağlan (postgres kullanıcısının şifresini soracak)
gcloud sql connect hukuk-emsal --user=postgres --database=<DB_ADI>
```

`gcloud sql connect` önce Cloud Shell IP'nizi geçici olarak yetkili listeye
ekler — "Allowlisting your IP for incoming connection..." satırında **~1 dakika
bekler**, bu normaldir.

### Bağlandıktan sonra oturumu uzun işlere hazırlayın

```sql
\timing on
SET statement_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
```

> **Uzun sürecek adımlarda güvence:** Cloud Shell sekmesi kapanırsa/uykuya
> giderse indeks iptal olur. Bunu istemiyorsanız `psql` yerine önce
> `tmux new -s idx` çalıştırıp psql'i onun içinde açın; `Ctrl+B` sonra `D` ile
> ayrılın, `tmux attach -t idx` ile geri dönün.

---

## ADIM 1 — Durum tespiti (hızlı, salt okunur)

```sql
-- 1a) Yarıda kalan ALTER'dan kolon kaldı mı?
SELECT column_name FROM information_schema.columns
WHERE table_name = 'rag_chunks'
  AND column_name IN ('document_tsv','embedding_model','gecerlilik');
```
> **Boş dönerse:** ALTER geri alınmış, tablo bozulmamış. Beklenen durum.
> **`document_tsv` dönerse:** kolon oluşmuş. **Zararsız, bırakın** — yeni tasarım
> onu kullanmıyor. Silmek de tabloyu yeniden yazar, acelesi yok.

```sql
-- 1b) Sunucuda hâlâ koşan bir şey var mı?
SELECT pid, state, wait_event_type, now() - query_start AS sure, left(query,100) AS sorgu
FROM pg_stat_activity
WHERE datname = current_database() AND pid <> pg_backend_pid() AND state <> 'idle'
ORDER BY query_start;
```
> Dakikalardır çalışan bir `ALTER TABLE` görürseniz:
> `SELECT pg_cancel_backend(<pid>);` — inatçıysa `pg_terminate_backend(<pid>)`.

```sql
-- 1c) Yarıda kalmış (geçersiz) indeks var mı?
SELECT indexrelid::regclass AS gecersiz FROM pg_index WHERE NOT indisvalid;
```
> Satır dönerse: `DROP INDEX CONCURRENTLY <ad>;`

```sql
-- 1d) Tablo boyutu (süre tahmini için)
SELECT count(*) AS chunk_sayisi,
       pg_size_pretty(pg_total_relation_size('rag_chunks')) AS boyut
FROM rag_chunks;
```

---

## ADIM 2 — Eklenti + ucuz kolonlar (saniyeler)

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE rag_chunks        ADD COLUMN IF NOT EXISTS embedding_model TEXT;
ALTER TABLE tenant_rag_chunks ADD COLUMN IF NOT EXISTS embedding_model TEXT;
ALTER TABLE rag_chunks        ADD COLUMN IF NOT EXISTS gecerlilik      TEXT;

COMMENT ON COLUMN rag_chunks.gecerlilik IS
    'Kararın güncel geçerliliği: NULL=bilinmiyor, gecerli, bozuldu, suphe';
```
> Varsayılan değeri olmayan nullable kolon eklemek Postgres 11+'ta sadece
> katalog işlemidir — tablo yeniden yazılmaz, kilit tutulmaz.

---

## ADIM 3 — Tam metin indeksi (EN UZUN ADIM, kilit YOK)

**Tek başına çalıştırın.** `CONCURRENTLY` transaction bloğu içinde çalışmaz.

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_tsv_idx
    ON rag_chunks USING GIN (to_tsvector('simple', document));
```
> 100K satırda ~5–20 dk. Tablo bu sırada okunur/yazılır kalır, site açık kalır.
> İlerlemeyi **ikinci bir Cloud Shell sekmesinden** izleyebilirsiniz:
> ```sql
> SELECT phase, blocks_done, blocks_total,
>        round(100.0*blocks_done/NULLIF(blocks_total,0),1) AS yuzde
> FROM pg_stat_progress_create_index;
> ```

---

## ADIM 4 — Yardımcı indeksler (kısa, kilit YOK)

Yine tek tek:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_case_no_trgm_idx
    ON rag_chunks USING GIN (case_no gin_trgm_ops);
```
```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_decision_no_trgm_idx
    ON rag_chunks USING GIN (decision_no gin_trgm_ops);
```
```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_embedding_model_idx
    ON rag_chunks (embedding_model);
```

---

## ADIM 5 — İstatistikleri tazele

```sql
ANALYZE rag_chunks;
ANALYZE tenant_rag_chunks;
```

---

## ADIM 6 — Doğrulama

```sql
-- 6a) İndeksler yerinde ve geçerli mi? (gecerli sütunu hepsinde 't' olmalı)
SELECT i.relname AS indeks, idx.indisvalid AS gecerli,
       pg_size_pretty(pg_relation_size(i.oid)) AS boyut
FROM pg_index idx
JOIN pg_class i ON i.oid = idx.indexrelid
JOIN pg_class t ON t.oid = idx.indrelid
WHERE t.relname IN ('rag_chunks','tenant_rag_chunks')
ORDER BY t.relname, i.relname;
```

```sql
-- 6b) Tam metin araması sonuç dönüyor mu?
SELECT chunk_id, court_chamber, case_no,
       ts_rank(to_tsvector('simple', document),
               to_tsquery('simple','icra | haciz')) AS skor
FROM rag_chunks
WHERE to_tsvector('simple', document) @@ to_tsquery('simple','icra | haciz')
ORDER BY skor DESC LIMIT 5;
```

```sql
-- 6c) EN ÖNEMLİ: indeks GERÇEKTEN kullanılıyor mu?
EXPLAIN (ANALYZE, BUFFERS)
SELECT chunk_id FROM rag_chunks
WHERE to_tsvector('simple', document) @@ to_tsquery('simple','itirazin & iptali')
LIMIT 10;
```
> Planda **`Bitmap Index Scan on rag_chunks_tsv_idx`** görmelisiniz.
> **`Seq Scan`** görüyorsanız ifade indeksle birebir eşleşmiyordur — haber verin.

Buraya kadar geldiyseniz **hibrit arama aktif.** Adım 7 isteğe bağlıdır.

---

## ADIM 7 — HNSW yeniden inşa (İSTEĞE BAĞLI, en pahalı)

Mevcut HNSW indeksleri pgvector varsayılanıyla (m=16, ef_construction=64)
kurulmuş. Veri 100K'ya yaklaşmadıysa **atlayın** — kazanç recall'da birkaç puan,
maliyeti uzun bir indeks inşası.

**Sıralama kritik:** önce yeniyi kur, sonra eskiyi düşür. Tersi olursa aradaki
sürede vektör araması sequential scan'e düşer ve site fiilen durur.

```sql
-- 7a) Yeni indeksler (geçici adla, kilitsiz — uzun sürer)
CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_embedding_idx_v2
    ON rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);
```
```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS tenant_rag_chunks_embedding_idx_v2
    ON tenant_rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);
```

```sql
-- 7b) DOĞRULA — boş dönmeli. BOŞ DEĞİLSE 7c'yi ÇALIŞTIRMAYIN.
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
```

```sql
-- 7c) Eskiyi düşür + yeniyi asıl adına taşı (hızlı)
DROP INDEX CONCURRENTLY IF EXISTS rag_chunks_embedding_idx;
ALTER INDEX rag_chunks_embedding_idx_v2 RENAME TO rag_chunks_embedding_idx;
```
```sql
DROP INDEX CONCURRENTLY IF EXISTS tenant_rag_chunks_embedding_idx;
ALTER INDEX tenant_rag_chunks_embedding_idx_v2 RENAME TO tenant_rag_chunks_embedding_idx;
```
```sql
ANALYZE rag_chunks;
ANALYZE tenant_rag_chunks;
```

---

## Sonrası

1. **Uygulamayı yeniden dağıtın** — `services/rag.py` yeni ifadeyi kullanıyor.
   Dağıtmadan indeksin faydası görünmez.
2. `.env` / Secret Manager'a ekleyin:
   ```
   RAG_MIN_SIMILARITY=0.35
   RAG_CONTEXT_MIN_SIMILARITY=0.45
   TRUSTED_PROXY_HOPS=1
   LOG_FORMAT=json
   ```
   Eşik değerleri şu an **tahmindir**; `evals/altin_set.jsonl`'i gerçek karar
   kimlikleriyle doldurup `python -m scripts.rag_eval --esik-tara` ile
   kalibre edin.
3. `scripts/init_db.py` bir daha koşarsa 32'yi tekrar uygular. Kolonlar ve
   tam metin indeksi `IF NOT EXISTS` olduğu için zararsız, ama **HNSW bloğu
   `DROP` + `CREATE` yapar** — canlıda istemezsiniz. Sadece elle yöneteceksiniz
   `MIGRATIONS` listesinden `"32_rag_hybrid_search.sql"` satırını çıkarın.

---

## Sorun çıkarsa

| Belirti | Sebep | Çözüm |
|---|---|---|
| "database is currently unavailable" | Studio/istemci zaman aşımı | Cloud Shell + tmux kullanın |
| `CONCURRENTLY cannot run inside a transaction block` | Birden fazla komut birlikte yapıştırıldı | Tek tek çalıştırın |
| `pg_index`'te `indisvalid = false` | İndeks yarıda kesildi | `DROP INDEX CONCURRENTLY <ad>;` sonra tekrar kurun |
| 6c'de `Seq Scan` | İfade indeksle eşleşmiyor | Haber verin — `services/rag.py`'deki ifadeyi indekse göre hizalarız |
| İndeks kurulurken disk doldu | GIN + HNSW yer ister | Cloud SQL depolamayı büyütün (otomatik büyüme açıksa kendiliğinden olur) |
