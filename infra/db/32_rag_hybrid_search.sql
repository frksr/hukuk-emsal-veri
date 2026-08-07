-- =============================================================================
-- 32_rag_hybrid_search.sql — Hibrit arama (vektör + tam metin) + indeks ayarı
--
-- NEDEN
-- -----
-- Arama tamamen semantik (kosinüs) idi. Hukuki metinlerde ise sorguların önemli
-- bir kısmı TAM EŞLEŞME ister:
--     "İİK 67/1",  "2023/1234 E.",  "TBK 117",  "ihalenin feshi"
-- Embedding modelleri madde/dosya numarası gibi sayısal token'ları iyi ayırt
-- edemediğinden bu sorgularda alakasız sonuçlar dönüyordu.
--
-- Çözüm: `to_tsvector('simple', document)` İFADESİ üzerine GIN indeksi kurup,
-- uygulama katmanında iki sıralamayı RRF (Reciprocal Rank Fusion) ile
-- birleştirmek (bkz. services/rag.py :: search).
--
-- ÖNEMLİ TASARIM NOTU — neden generated kolon DEĞİL
-- --------------------------------------------------
-- İlk tasarımda `document_tsv` adlı bir GENERATED ALWAYS ... STORED kolon
-- vardı. Onu eklemek tabloyu BAŞTAN YAZAR ve süresince ACCESS EXCLUSIVE kilit
-- tutar: canlıda dakikalarca kesinti, Cloud SQL Studio gibi kısa ömürlü
-- istemcilerde ise "database is currently unavailable" ile kopma demektir.
--
-- İfade indeksi aynı performansı verir, kolon eklemez, tabloyu yeniden yazmaz
-- ve `CONCURRENTLY` ile kesintisiz kurulabilir. Tek şart: services/rag.py'deki
-- sorgu ifadeyi BİREBİR aynı yazmalıdır, yoksa planner indeksi kullanmaz.
--
-- ('simple' sözlüğü bilinçli: 'turkish' bazı kurulumlarda yok, ayrıca kök
--  bulma madde/dosya numaralarını bozar — hukuki metinde tam eşleşme daha
--  değerli. Ayrıca to_tsvector(regconfig, text) IMMUTABLE'dır; tek argümanlı
--  biçim STABLE olduğu için indekslenemez.)
--
-- ÇALIŞTIRMA
-- ----------
-- Bu dosya migration runner'ı (scripts/init_db.py) için tek parça yazılmıştır.
-- CANLI Cloud SQL'de elle çalıştıracaksanız 32_rag_hybrid_search_CLOUD.sql
-- kullanın: orada indeksler CONCURRENTLY kurulur ve adımlara bölünmüştür.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1) Tam metin arama indeksi (ifade tabanlı — kolon EKLENMEZ)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS rag_chunks_tsv_idx
    ON rag_chunks USING GIN (to_tsvector('simple', document));

-- Kısmi/ek eşleşme (trigram) — "İİK 67" gibi kısaltmalar ve dosya numarası
-- parçaları için.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS rag_chunks_case_no_trgm_idx
    ON rag_chunks USING GIN (case_no gin_trgm_ops);
CREATE INDEX IF NOT EXISTS rag_chunks_decision_no_trgm_idx
    ON rag_chunks USING GIN (decision_no gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- 2) Embedding sürüm izleme
-- ---------------------------------------------------------------------------
-- Embedding modeli değiştirilip `--recreate` unutulursa, tabloda FARKLI
-- modellerden üretilmiş vektörler karışık kalıyor (aynı 768 boyut ama farklı
-- semantik uzay) ve benzerlik skorları sessizce anlamsızlaşıyordu. Artık her
-- satır hangi modelle üretildiğini taşır; pipelines/embed.py karışıklığı
-- tespit edip durur.
--
-- Bu ADD COLUMN'lar ucuzdur: varsayılan değeri olmayan nullable kolon eklemek
-- Postgres'te yalnızca katalog işlemidir, tabloyu yeniden yazmaz.
ALTER TABLE rag_chunks
    ADD COLUMN IF NOT EXISTS embedding_model TEXT;
ALTER TABLE tenant_rag_chunks
    ADD COLUMN IF NOT EXISTS embedding_model TEXT;

CREATE INDEX IF NOT EXISTS rag_chunks_embedding_model_idx
    ON rag_chunks (embedding_model);

-- ---------------------------------------------------------------------------
-- 3) Karar geçerliliği (bozma / onama)
-- ---------------------------------------------------------------------------
-- Bir kararın sonradan bozulmuş veya içtihadı birleştirme kararıyla geçersiz
-- kalmış olması hiç izlenmiyordu; RAG geçersiz bir kararı hâlâ yaşayan emsal
-- gibi sunabiliyordu. Alan şimdilik NULL (bilinmiyor) kalır; doldurulduğunda
-- arayüz "bu karar bozulmuştur" rozetini gösterebilir.
ALTER TABLE rag_chunks
    ADD COLUMN IF NOT EXISTS gecerlilik TEXT;  -- NULL | 'gecerli' | 'bozuldu' | 'suphe'

COMMENT ON COLUMN rag_chunks.gecerlilik IS
    'Kararın güncel geçerliliği: NULL=bilinmiyor, gecerli, bozuldu, suphe';

-- ---------------------------------------------------------------------------
-- 4) HNSW indeks parametreleri
-- ---------------------------------------------------------------------------
-- Varsayılan (m=16, ef_construction=64) küçük veri için yeterliydi. Hedef
-- 100K+ chunk olduğundan recall/latency dengesi için yükseltiliyor.
--
-- DİKKAT: burada eski indeks önce düşürülüyor — bu dosya sıfırdan kurulum ve
-- lokal geliştirme içindir. CANLIDA BÖYLE YAPMAYIN: indeks olmayan aralıkta
-- vektör araması sequential scan'e düşer ve site durur. Canlı için
-- 32_rag_hybrid_search_CLOUD.sql (önce yeniyi CONCURRENTLY kur, sonra eskiyi
-- düşür) kullanın.
DROP INDEX IF EXISTS rag_chunks_embedding_idx;
CREATE INDEX rag_chunks_embedding_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);

DROP INDEX IF EXISTS tenant_rag_chunks_embedding_idx;
CREATE INDEX tenant_rag_chunks_embedding_idx
    ON tenant_rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);

-- Planner'ın indeksleri kullanabilmesi için istatistikleri tazele.
ANALYZE rag_chunks;
ANALYZE tenant_rag_chunks;
