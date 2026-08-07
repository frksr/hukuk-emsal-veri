-- =============================================================================
-- HTML KİRLİLİĞİ TESPİTİ — kaç chunk etkilenmiş?
--
-- Belirti: karar metinlerinde ham HTML kalmış
--   "<html><head><meta http-equiv=... <font face="Verdana" size="2">..."
--
-- Bu yalnızca görüntüyü bozmuyor; metin AYNEN embedding'e ve tam metin
-- indeksine gitmiş durumda. Yani:
--   • embedding vektörleri HTML gürültüsüyle kirlenmiş → benzerlik skorları bozuk
--   • tsvector'de "font", "verdana", "http-equiv" gibi token'lar var
--   • LLM'e bağlam olarak gidince hem token israfı hem kalite kaybı
--
-- Hepsi salt okunur, hızlı çalışır.
-- =============================================================================

-- 1) Ölçek: kaç chunk, kaç karar, toplam içinde payı ne?
SELECT
    count(*) FILTER (WHERE document ILIKE '%<html%'
                        OR document ILIKE '%<font%'
                        OR document ILIKE '%<br>%'
                        OR document ILIKE '%http-equiv%')          AS kirli_chunk,
    count(*)                                                       AS toplam_chunk,
    round(100.0 * count(*) FILTER (WHERE document ILIKE '%<html%'
                        OR document ILIKE '%<font%'
                        OR document ILIKE '%<br>%'
                        OR document ILIKE '%http-equiv%') / NULLIF(count(*),0), 1)
                                                                   AS yuzde
FROM rag_chunks;

-- 2) Hangi kaynaklarda? (danistay mı, hepsinde mi?)
SELECT source,
       count(*) FILTER (WHERE document ILIKE '%<font%'
                           OR document ILIKE '%<html%') AS kirli,
       count(*)                                          AS toplam
FROM rag_chunks
GROUP BY source
ORDER BY kirli DESC;

-- 3) Kaç FARKLI karar etkilenmiş? (yeniden embed maliyeti için)
SELECT count(DISTINCT decision_id) AS etkilenen_karar
FROM rag_chunks
WHERE document ILIKE '%<font%' OR document ILIKE '%<html%';

-- 4) Örnek — gözle görmek için
SELECT chunk_id, source, court_chamber, left(document, 200) AS metin_basi
FROM rag_chunks
WHERE document ILIKE '%<html%'
LIMIT 3;

-- 5) Tam metin indeksine sızan HTML token'ları
--    ("font", "verdana", "http", "equiv", "br" gibi kelimeler çıkarsa doğrulanmış olur
SELECT lexeme, count(*) AS adet
FROM (SELECT document FROM rag_chunks
      WHERE document ILIKE '%<font%' LIMIT 200) s,
     unnest(to_tsvector('simple', s.document)) AS t(lexeme, positions, weights)
WHERE lexeme IN ('font','verdana','html','head','br','equiv','http','charset',
                 'meta','body','align','justify','size','face','ul','align')
GROUP BY lexeme
ORDER BY adet DESC;

-- 6) Tarih sorunu — kaç kararda decision_date boş/bozuk?
--    ("Invalid Date" belirtisinin kaynağı)
SELECT
    count(*) FILTER (WHERE decision_date IS NULL OR decision_date = '')     AS bos,
    count(*) FILTER (WHERE decision_date !~ '^\d{4}-\d{2}-\d{2}$'
                       AND decision_date IS NOT NULL
                       AND decision_date <> '')                              AS bozuk_format,
    count(*)                                                                 AS toplam
FROM rag_chunks;

-- 7) Bozuk tarih örnekleri — hangi biçimde gelmişler?
SELECT DISTINCT decision_date, count(*) AS adet
FROM rag_chunks
WHERE decision_date IS NOT NULL
  AND decision_date <> ''
  AND decision_date !~ '^\d{4}-\d{2}-\d{2}$'
GROUP BY decision_date
ORDER BY adet DESC
LIMIT 20;
