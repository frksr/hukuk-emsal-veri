-- =============================================================================
-- 32_rag_hybrid_search — CANLI (Cloud SQL) İÇİN ADIM ADIM SÜRÜM  [v2]
--
-- v1'DEN FARKI — ÖNEMLİ
-- ---------------------
-- v1'de `document_tsv` adlı bir GENERATED STORED kolon ekleniyordu. O komut
-- tabloyu BAŞTAN YAZAR, dakikalarca ACCESS EXCLUSIVE kilit tutar ve Cloud SQL
-- Studio gibi kısa ömürlü istemcilerde bağlantı koptuğu için şu hatayı verir:
--
--     "Invalid request: The database is currently unavailable."
--
-- Bu hata Postgres'ten DEĞİL, editörden gelir. v2'de o kolona hiç ihtiyaç yok:
-- aynı işi `to_tsvector('simple', document)` İFADESİ üzerine kurulan bir GIN
-- indeksi görüyor. Kolon eklenmiyor, tablo yeniden yazılmıyor, kilit yok.
--
-- Bu dosyadaki HİÇBİR komut tabloyu yeniden yazmaz veya yazma kilidi tutmaz.
--
-- =============================================================================
-- NEREDE ÇALIŞTIRMALI  ←←← BUNU ATLAMAYIN
-- =============================================================================
-- Cloud SQL Studio (Console'daki sorgu editörü) UZUN KOMUTLAR İÇİN UYGUN
-- DEĞİLDİR: bağlantıyı birkaç dakikada düşürür ve `CREATE INDEX CONCURRENTLY`
-- istemci koptuğunda İPTAL OLUR, geriye "invalid" bir indeks bırakır.
--
-- Bunun yerine Cloud Shell kullanın (ücretsiz, tarayıcıda açılır, oturumu
-- kopmaz):
--
--   1. Cloud Console sağ üstte terminal simgesi → Cloud Shell
--   2. gcloud sql connect <INSTANCE_ID> --user=postgres --database=<DB_ADI>
--        (veya Auth Proxy ile:  psql "$DATABASE_URL")
--   3. Uzun komutlarda oturum düşmesin diye:
--        \timing on
--   4. Aşağıdaki adımları TEK TEK yapıştırın.
--
-- Cloud Shell 1 saat işlemsiz kalırsa kapanır; indeks kurulurken ekranda
-- beklediğiniz için sorun olmaz. Yine de sekmeyi kapatmayın.
--
-- ALTERNATİF (bağlantı hiç kopmasın isterseniz): komutu screen/tmux içinde
-- çalıştırın —  `tmux new -s idx`  → psql → komut → Ctrl+B, D ile ayrılın.
-- =============================================================================


-- ###########################################################################
-- ADIM 0 — Ön kontrol (hızlı, salt okunur — Studio'da da güvenle koşar)
-- ###########################################################################
SELECT count(*) AS chunk_sayisi,
       pg_size_pretty(pg_total_relation_size('rag_chunks')) AS toplam_boyut
FROM rag_chunks;

-- v1'i denediyseniz: yarıda kalmış kolon/indeks var mı?
SELECT column_name FROM information_schema.columns
WHERE table_name = 'rag_chunks' AND column_name = 'document_tsv';
--   Boş dönerse: ALTER geri alınmış, hiçbir şey yapmanız gerekmiyor.
--   Satır dönerse: kolon eklenmiş. ZARARSIZDIR, bırakabilirsiniz — yeni tasarım
--   onu kullanmıyor. Yer kaplamasını istemiyorsanız en sonda silebilirsiniz
--   (ADIM 8'e bakınız), ama o DROP da tabloyu yeniden yazar; acelesi yok.

-- Geçersiz (yarıda kalmış) indeks var mı?
SELECT i.relname AS indeks, idx.indisvalid AS gecerli
FROM pg_index idx
JOIN pg_class i ON i.oid = idx.indexrelid
JOIN pg_class t ON t.oid = idx.indrelid
WHERE t.relname IN ('rag_chunks','tenant_rag_chunks') AND NOT idx.indisvalid;
--   Satır dönerse:  DROP INDEX CONCURRENTLY <indeks>;  ile temizleyin.


-- ###########################################################################
-- ADIM 1 — pg_trgm eklentisi  (saniyeler)
-- ###########################################################################
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- ###########################################################################
-- ADIM 2 — Ucuz kolonlar  (saniyeler — tabloyu YENİDEN YAZMAZ)
-- ###########################################################################
-- Varsayılan değeri olmayan nullable kolon eklemek Postgres 11+'ta yalnızca
-- katalog işlemidir; satırlara dokunulmaz.
ALTER TABLE rag_chunks        ADD COLUMN IF NOT EXISTS embedding_model TEXT;
ALTER TABLE tenant_rag_chunks ADD COLUMN IF NOT EXISTS embedding_model TEXT;
ALTER TABLE rag_chunks        ADD COLUMN IF NOT EXISTS gecerlilik      TEXT;

COMMENT ON COLUMN rag_chunks.gecerlilik IS
    'Kararın güncel geçerliliği: NULL=bilinmiyor, gecerli, bozuldu, suphe';


-- ###########################################################################
-- ADIM 3 — Tam metin indeksi  (EN UZUN ADIM — kilit YOK)
-- ###########################################################################
-- CONCURRENTLY transaction bloğu içinde ÇALIŞMAZ; tek başına, BEGIN olmadan
-- çalıştırın. 100K satırda ~5-20 dk sürebilir. Tablo bu sırada okunur/yazılır
-- durumda kalır — site açık kalır.
--
-- Bu ifade services/rag.py'deki sorguyla BİREBİR aynı olmalıdır, yoksa
-- planner indeksi kullanmaz.
CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_tsv_idx
    ON rag_chunks USING GIN (to_tsvector('simple', document));


-- ###########################################################################
-- ADIM 4 — Yardımcı indeksler  (kilit YOK, kısa)
-- ###########################################################################
CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_case_no_trgm_idx
    ON rag_chunks USING GIN (case_no gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_decision_no_trgm_idx
    ON rag_chunks USING GIN (decision_no gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_embedding_model_idx
    ON rag_chunks (embedding_model);


-- ###########################################################################
-- ADIM 5 — HNSW indeksleri  (isteğe bağlı, en pahalı adım)
-- ###########################################################################
-- Mevcut indeksler pgvector varsayılanıyla (m=16, ef_construction=64)
-- kurulmuştu. Veri 100K'ya yaklaşmadıysa BU ADIMI ATLAYABİLİRSİNİZ —
-- hibrit aramanın faydası zaten ADIM 3'ten gelir. Kazanç recall'da birkaç
-- puan; maliyet uzun bir indeks inşası.
--
-- SIRALAMA ÖNEMLİ: önce YENİSİNİ kur, sonra eskisini düşür. Tersini yaparsanız
-- aradaki sürede vektör araması sequential scan'e düşer ve site fiilen durur.

-- 5a) Yeni indeksleri kur (geçici adla, kilitsiz)
CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_embedding_idx_v2
    ON rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);

CREATE INDEX CONCURRENTLY IF NOT EXISTS tenant_rag_chunks_embedding_idx_v2
    ON tenant_rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);

-- 5b) Geçerli olduklarını DOĞRULAYIN — boş dönmeli. Boş DEĞİLSE 5c'yi ÇALIŞTIRMAYIN.
SELECT indexrelid::regclass AS gecersiz_indeks
FROM pg_index WHERE NOT indisvalid;

-- 5c) Eskileri düşür + yenilerini asıl adına taşı (hızlı, katalog işlemi)
DROP INDEX CONCURRENTLY IF EXISTS rag_chunks_embedding_idx;
ALTER INDEX rag_chunks_embedding_idx_v2 RENAME TO rag_chunks_embedding_idx;

DROP INDEX CONCURRENTLY IF EXISTS tenant_rag_chunks_embedding_idx;
ALTER INDEX tenant_rag_chunks_embedding_idx_v2 RENAME TO tenant_rag_chunks_embedding_idx;


-- ###########################################################################
-- ADIM 6 — İstatistikleri tazele  (dakikalar sürebilir, kilit yok)
-- ###########################################################################
ANALYZE rag_chunks;
ANALYZE tenant_rag_chunks;


-- ###########################################################################
-- ADIM 7 — Doğrulama
-- ###########################################################################

-- 7a) İndeksler yerinde ve geçerli mi?
SELECT i.relname AS indeks, idx.indisvalid AS gecerli,
       pg_size_pretty(pg_relation_size(i.oid)) AS boyut
FROM pg_index idx
JOIN pg_class i ON i.oid = idx.indexrelid
JOIN pg_class t ON t.oid = idx.indrelid
WHERE t.relname IN ('rag_chunks', 'tenant_rag_chunks')
ORDER BY t.relname, i.relname;

-- 7b) Tam metin araması sonuç dönüyor mu?
SELECT chunk_id, court_chamber, case_no,
       ts_rank(to_tsvector('simple', document),
               to_tsquery('simple', 'icra | haciz')) AS skor
FROM rag_chunks
WHERE to_tsvector('simple', document) @@ to_tsquery('simple', 'icra | haciz')
ORDER BY skor DESC
LIMIT 5;

-- 7c) EN ÖNEMLİ KONTROL — indeks gerçekten kullanılıyor mu?
--     Planda "Bitmap Index Scan on rag_chunks_tsv_idx" GÖRMELİSİNİZ.
--     "Seq Scan" görüyorsanız ifade indeksle birebir eşleşmiyor demektir.
EXPLAIN (ANALYZE, BUFFERS)
SELECT chunk_id FROM rag_chunks
WHERE to_tsvector('simple', document) @@ to_tsquery('simple', 'itirazin & iptali')
LIMIT 10;


-- ###########################################################################
-- ADIM 8 — Mevcut satırları modelle etiketle  (İSTEĞE BAĞLI)
-- ###########################################################################
-- embedding_model mevcut satırlarda NULL'dır; pipelines/embed.py NULL'ları
-- "bilinmiyor" sayar ve uyarı vermez. Şu anki verinin hangi modelle
-- üretildiğini BİLİYORSANIZ etiketleyin ki ileride bir model değişikliği
-- tespit edilebilsin. Biçim pipelines/embed.py ile AYNI olmalı:
--     "<provider>:<model>:<boyut>"
--
-- Google text-embedding-004 ile üretildiyse:
--   UPDATE rag_chunks
--      SET embedding_model = 'google:models/text-embedding-004:768'
--    WHERE embedding_model IS NULL;
--
-- (Büyük tabloda bu UPDATE tüm satırlara dokunur — parça parça yapın:
--    UPDATE rag_chunks SET embedding_model = '...'
--     WHERE chunk_id IN (SELECT chunk_id FROM rag_chunks
--                        WHERE embedding_model IS NULL LIMIT 10000);
--  bitene kadar tekrarlayın.)
--
-- EMİN DEĞİLSENİZ BOŞ BIRAKIN — yanlış etiket, gerçek bir karışıklığı
-- gizlemekten daha kötüdür.


-- ###########################################################################
-- v1 KALINTISI TEMİZLİĞİ  (yalnızca document_tsv kolonu oluştuysa)
-- ###########################################################################
-- ADIM 0'da document_tsv gördüyseniz ve yer kaplamasını istemiyorsanız:
--     ALTER TABLE rag_chunks DROP COLUMN document_tsv;
-- DİKKAT: bu DROP da tabloyu yeniden yazar ve kilitler. Acelesi yok —
-- kolon kullanılmıyor, sadece disk yer kaplıyor. Bakım penceresine bırakın.


-- ###########################################################################
-- GERİ ALMA
-- ###########################################################################
-- Uygulama 32'siz de çalışır (services/rag.py, tam metin sorgusu hata verirse
-- saf vektör aramasına düşer). Tamamen geri almak için:
--
-- DROP INDEX CONCURRENTLY IF EXISTS rag_chunks_tsv_idx;
-- DROP INDEX CONCURRENTLY IF EXISTS rag_chunks_case_no_trgm_idx;
-- DROP INDEX CONCURRENTLY IF EXISTS rag_chunks_decision_no_trgm_idx;
-- DROP INDEX CONCURRENTLY IF EXISTS rag_chunks_embedding_model_idx;
-- ALTER TABLE rag_chunks        DROP COLUMN IF EXISTS gecerlilik;
-- ALTER TABLE rag_chunks        DROP COLUMN IF EXISTS embedding_model;
-- ALTER TABLE tenant_rag_chunks DROP COLUMN IF EXISTS embedding_model;
