-- =============================================================================
-- 33_rag_unaccent.sql — Tam metin aramada Türkçe karakter duyarsızlığı
--
-- SORUN
-- -----
-- 32_rag_hybrid_search.sql'in kurduğu tam metin indeksi 'simple' sözlüğünü
-- kullanıyor. 'simple' hiçbir katlama yapmaz: "itirazın" ile "itirazin" FARKLI
-- token'lardır. Kullanıcı Türkçe klavyesi olmadan (telefondan, aceleyle,
-- yabancı klavyeyle) yazdığında tam metin tarafı hiçbir şey bulamıyordu.
-- Vektör tarafı bunu tolere eder, tam metin tarafı etmez.
--
-- ÇÖZÜM
-- -----
-- unaccent ile ı→i, ş→s, ğ→g, ü→u, ö→o, ç→c katlaması. Hem indekste hem
-- sorguda uygulanır, böylece her iki yazım da eşleşir.
--
-- Bu dosya migration runner'ı (scripts/init_db.py) için tek parça yazılmıştır.
-- CANLIDA elle çalıştırıyorsanız 33_dogrulama_ve_unaccent.sql'in B bölümünü
-- kullanın — orada indeks CONCURRENTLY kurulur (kesintisiz).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS unaccent;

-- ---------------------------------------------------------------------------
-- IMMUTABLE sarmalayıcı
-- ---------------------------------------------------------------------------
-- unaccent() varsayılan olarak STABLE'dır (sözlük dosyasına bağlı olduğu için)
-- ve STABLE fonksiyonlar ifade indeksinde KULLANILAMAZ. Sözlüğü açıkça vererek
-- IMMUTABLE bir sarmalayıcı üretmek Postgres'te standart çözümdür.
--
-- DİKKAT: IMMUTABLE "bu asla değişmez" taahhüdüdür. unaccent sözlüğünü
-- ileride değiştirirseniz bu fonksiyona dayanan indeksleri YENİDEN kurmanız
-- gerekir, yoksa indeks sessizce yanlış sonuç verir.
CREATE OR REPLACE FUNCTION f_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT PARALLEL SAFE
AS $$ SELECT public.unaccent('public.unaccent', $1) $$;

COMMENT ON FUNCTION f_unaccent(text) IS
    'Türkçe karakter katlaması (ı→i, ş→s, ğ→g...). services/rag.py tam metin '
    'aramasında kullanılır — ifade indeksiyle BİREBİR eşleşmelidir.';

-- ---------------------------------------------------------------------------
-- Katlamalı tam metin indeksi
-- ---------------------------------------------------------------------------
-- services/rag.py :: _metin_sql_uret() bu ifadeyi birebir üretir.
CREATE INDEX IF NOT EXISTS rag_chunks_tsv_unaccent_idx
    ON rag_chunks USING GIN (to_tsvector('simple', f_unaccent(document)));

-- ---------------------------------------------------------------------------
-- Eski (katlamasız) indeks
-- ---------------------------------------------------------------------------
-- 32'de kurulan rag_chunks_tsv_idx artık kullanılmıyor. Sıfırdan kurulumda
-- (init_db) hiç gerek yok, düşürülebilir. CANLIDA ise uygulama dağıtılana
-- kadar eski kod hâlâ eski ifadeyi kullanır — orada elle ve SONRA düşürün
-- (bkz. 33_dogrulama_ve_unaccent.sql adım B8).
DROP INDEX IF EXISTS rag_chunks_tsv_idx;

ANALYZE rag_chunks;
