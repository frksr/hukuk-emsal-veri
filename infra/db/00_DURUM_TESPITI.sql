-- =============================================================================
-- ÖNCE BUNU ÇALIŞTIRIN — hepsi hızlı, salt okunur, kilitlemez.
-- Cloud SQL Studio'da güvenle koşar.
--
-- Amaç: yarıda kesilen ALTER TABLE'dan geriye ne kaldığını görmek.
-- =============================================================================

-- 1) document_tsv kolonu eklendi mi?
--    Boş dönerse: ALTER tamamlanmamış (Postgres DDL transactional'dır, geri alındı).
--    Satır dönerse: tamamlanmış, kolon duruyor.
SELECT column_name, data_type, is_generated, generation_expression
FROM information_schema.columns
WHERE table_name = 'rag_chunks'
  AND column_name IN ('document_tsv', 'embedding_model', 'gecerlilik');

-- 2) Şu an tabloyu kilitleyen/uzun süren bir sorgu var mı?
--    (Kesilen oturum sunucuda hâlâ çalışıyor olabilir!)
SELECT pid,
       state,
       wait_event_type,
       wait_event,
       now() - query_start AS calisma_suresi,
       left(query, 120)    AS sorgu
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
  AND state <> 'idle'
ORDER BY query_start;

-- 3) Yarıda kalmış (geçersiz) indeks var mı?
SELECT i.relname AS indeks_adi, idx.indisvalid AS gecerli
FROM pg_index idx
JOIN pg_class i ON i.oid = idx.indexrelid
JOIN pg_class t ON t.oid = idx.indrelid
WHERE t.relname IN ('rag_chunks', 'tenant_rag_chunks')
ORDER BY i.relname;

-- 4) Tablo ne kadar büyük? (süre tahminleri için)
SELECT count(*) AS chunk_sayisi,
       pg_size_pretty(pg_total_relation_size('rag_chunks')) AS toplam_boyut,
       pg_size_pretty(pg_relation_size('rag_chunks'))       AS sadece_tablo
FROM rag_chunks;


-- =============================================================================
-- SONUÇLARI NASIL OKUYACAKSINIZ
-- =============================================================================
--
-- (1) BOŞ döndü        → ALTER geri alındı, tablo bozulmadı. En olası durum.
--                        Zaten sorun değil: yeni tasarımda o kolona İHTİYAÇ YOK.
--
-- (1) SATIR döndü      → ALTER tamamlanmış. Kolon zararsız, kalabilir.
--
-- (2) 'ALTER TABLE' içeren, dakikalardır çalışan bir satır görüyorsanız
--     → sunucuda hâlâ koşuyor demektir. Ya bitmesini bekleyin ya iptal edin:
--         SELECT pg_cancel_backend(<pid>);      -- nazik
--         SELECT pg_terminate_backend(<pid>);   -- zorla (nazik işe yaramazsa)
--
-- (3) gecerli = false olan indeks varsa yarıda kalmıştır, silin:
--         DROP INDEX CONCURRENTLY <indeks_adi>;
--
-- Hiçbir durumda veri kaybı YOKTUR — Postgres'te DDL transactional'dır,
-- yarıda kesilen ALTER tamamen geri alınır.
