-- ============================================================================
-- Migration 26: Embedding API kullanım logu
--
-- Amaç: Google Gemini embedding API'sine (services/embeddings.py) atılan HER
-- gerçek istek (cache hit'ler HARİÇ) burada kalıcı olarak loglanır — admin
-- panelde istek sayısı + tahmini maliyet gösterebilmek için (bkz.
-- api/routers/admin.py /analytics, web/app/panel/admin/analitik).
--
-- Bu tablo, RAG'ın kullandığı SENKRON psycopg havuzundan (services/pg.py)
-- yazılır — asyncpg havuzuyla (api/db.py) aynı veritabanına bağlanır, bu
-- yüzden admin analytics endpoint'i (asyncpg) bu satırları normal şekilde
-- okuyabilir. RLS YOK: kullanıcıya bağlı değil, saf operasyonel/maliyet
-- telemetrisi (kişisel veri içermez — yalnızca sayaç + karakter uzunluğu).
-- ============================================================================

CREATE TABLE IF NOT EXISTS embedding_usage_log (
    id           BIGSERIAL PRIMARY KEY,
    provider     TEXT NOT NULL,               -- 'google' | 'local'
    model        TEXT NOT NULL,                -- örn. 'gemini-embedding-001'
    request_type TEXT NOT NULL,                -- 'retrieval_query' | 'retrieval_document'
    item_count   INT NOT NULL DEFAULT 1,       -- batch'teki metin sayısı
    char_count   INT NOT NULL DEFAULT 0,       -- toplam karakter (maliyet tahmini için)
    ok           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS embedding_usage_log_created_idx ON embedding_usage_log (created_at);
CREATE INDEX IF NOT EXISTS embedding_usage_log_provider_idx ON embedding_usage_log (provider, created_at);

GRANT SELECT, INSERT ON embedding_usage_log TO app_user;
GRANT SELECT, INSERT ON embedding_usage_log TO app_service;
GRANT USAGE, SELECT ON SEQUENCE embedding_usage_log_id_seq TO app_user;
GRANT USAGE, SELECT ON SEQUENCE embedding_usage_log_id_seq TO app_service;
