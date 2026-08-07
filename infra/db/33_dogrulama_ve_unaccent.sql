-- =============================================================================
-- A) DOĞRULAMA — indeks çalışıyor ama sonuç dönüyor mu?
-- =============================================================================
-- Hepsi hızlı, salt okunur.

-- A1) Tabloda kaç chunk var? (rows=0'ın sebebi boş tablo olabilir)
SELECT count(*) AS chunk_sayisi FROM rag_chunks;

-- A2) TÜRKÇE KARAKTERLE arayın — 'simple' sözlüğü harf katlaması yapmaz,
--     "itirazin" ile "itirazın" FARKLI token'dır. Önceki testim ASCII'ydi.
SELECT count(*) AS eslesme
FROM rag_chunks
WHERE to_tsvector('simple', document) @@ to_tsquery('simple', 'itirazın');

-- A3) Uygulamanın gerçekte ürettiği biçim: OR'lu sorgu
--     (services/rag.py :: _tsquery_hazirla token'ları " | " ile birleştirir)
SELECT count(*) AS eslesme
FROM rag_chunks
WHERE to_tsvector('simple', document) @@ to_tsquery('simple', 'itirazın | iptali');

-- A4) Kesin çalışan bir kontrol: gerçek bir belgeden kelime alıp geri ara
WITH ornek AS (
  SELECT chunk_id, document FROM rag_chunks WHERE length(document) > 200 LIMIT 1
)
SELECT o.chunk_id,
       (SELECT string_agg(lexeme, ', ' ORDER BY lexeme)
        FROM unnest(to_tsvector('simple', o.document)) AS t(lexeme, positions, weights)
        LIMIT 1) IS NOT NULL AS tokenlar_uretildi,
       left(o.document, 160) AS metin_basi
FROM ornek o;

-- A5) En sık geçen 20 token — veri setinde gerçekte hangi kelimeler var?
--     (Büyük tabloda yavaş olabilir; LIMIT'li örneklemle çalışır.)
SELECT lexeme, count(*) AS adet
FROM (SELECT document FROM rag_chunks LIMIT 500) s,
     unnest(to_tsvector('simple', s.document)) AS t(lexeme, positions, weights)
GROUP BY lexeme
ORDER BY adet DESC
LIMIT 20;


-- =============================================================================
-- B) İSTEĞE BAĞLI İYİLEŞTİRME — Türkçe karakter duyarsız arama (unaccent)
-- =============================================================================
-- SORUN: 'simple' sözlüğü hiçbir katlama yapmaz. Kullanıcı "itirazin iptali"
-- yazarsa (Türkçe klavyesi yoksa veya aceleyle) hiçbir şey bulamaz; "itirazın"
-- yazması gerekir. Vektör tarafı bunu tolere eder ama tam metin tarafı etmez.
--
-- ÇÖZÜM: unaccent ile ı→i, ş→s, ğ→g, ü→u, ö→o, ç→c katlaması yapmak.
--
-- MALİYET: tam metin indeksinin YENİDEN kurulması (yine CONCURRENTLY, kilitsiz,
-- ~ADIM 3 kadar süre). Ayrıca services/rag.py'deki ifadenin de değişmesi
-- gerekir — ikisi BİRLİKTE yapılmazsa indeks kullanılmaz.
--
-- BUNU UYGULAYACAKSANIZ ÖNCE HABER VERİN — rag.py'yi aynı anda güncelleyeyim.
-- =============================================================================

-- B1) Eklenti
CREATE EXTENSION IF NOT EXISTS unaccent;

-- B2) IMMUTABLE sarmalayıcı.
--     unaccent() varsayılan olarak STABLE'dır (sözlük dosyasına bağlı) ve
--     STABLE fonksiyonlar ifade indeksinde KULLANILAMAZ. Sözlüğü açıkça
--     vererek IMMUTABLE bir sarmalayıcı üretmek standart çözümdür.
--     DİKKAT: unaccent sözlüğünü ileride değiştirirseniz indeksi yeniden
--     kurmanız gerekir (IMMUTABLE demek "bu asla değişmez" demektir).
CREATE OR REPLACE FUNCTION f_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT PARALLEL SAFE
AS $$ SELECT public.unaccent('public.unaccent', $1) $$;

-- B3) Doğru katlıyor mu? Beklenen: "itirazin iptali", "ihalenin feshi"
SELECT f_unaccent('itirazın iptali')  AS ornek1,
       f_unaccent('ihalenin feshi')   AS ornek2,
       f_unaccent('İİK 67/1 haczedilemezlik şikâyeti') AS ornek3;

-- B4) Yeni indeks (kilitsiz, uzun sürer — ADIM 3 ile aynı mertebede)
CREATE INDEX CONCURRENTLY IF NOT EXISTS rag_chunks_tsv_unaccent_idx
    ON rag_chunks USING GIN (to_tsvector('simple', f_unaccent(document)));

-- B5) Geçerli mi? (boş dönmeli)
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;

-- B6) Artık ASCII yazım da eşleşiyor mu? İkisi de sonuç DÖNMELİ.
SELECT 'turkce' AS yazim, count(*) FROM rag_chunks
WHERE to_tsvector('simple', f_unaccent(document))
      @@ to_tsquery('simple', f_unaccent('itirazın iptali'))
UNION ALL
SELECT 'ascii', count(*) FROM rag_chunks
WHERE to_tsvector('simple', f_unaccent(document))
      @@ to_tsquery('simple', f_unaccent('itirazin iptali'));

-- B7) Plan indeksi kullanıyor mu? "rag_chunks_tsv_unaccent_idx" görmelisiniz.
EXPLAIN (ANALYZE, BUFFERS)
SELECT chunk_id FROM rag_chunks
WHERE to_tsvector('simple', f_unaccent(document))
      @@ to_tsquery('simple', f_unaccent('itirazin | iptali'))
LIMIT 10;

-- B8) rag.py güncellendikten ve dağıtıldıktan SONRA eski indeksi düşürün.
--     (Önce düşürmeyin — dağıtım arasında eski kod hâlâ eski ifadeyi kullanır.)
-- DROP INDEX CONCURRENTLY IF EXISTS rag_chunks_tsv_idx;
