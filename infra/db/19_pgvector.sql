-- =============================================================================
-- 19_pgvector.sql — Vektör arama deposu (Chroma -> pgvector göçü)
--
-- Önkoşul: Cloud SQL Postgres'te 'vector' eklentisi mevcut olmalı
--          (Cloud SQL flag: cloudsql.enable_pgvector veya yönetilen sürümde hazır).
-- Boyut: 768 (text-embedding-004). pgvector HNSW indeksi <= 2000 boyut destekler.
-- Çalıştır: psql "$DATABASE_URL" -f infra/db/19_pgvector.sql
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Public emsal karar chunk'ları (10K+ ve büyüyecek)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rag_chunks (
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

CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS rag_chunks_source_idx ON rag_chunks (source);
CREATE INDEX IF NOT EXISTS rag_chunks_court_idx ON rag_chunks (court_chamber);
CREATE INDEX IF NOT EXISTS rag_chunks_decision_idx ON rag_chunks (decision_id);

-- ---------------------------------------------------------------------------
-- Tenant (kullanıcı) dosya chunk'ları — izolasyon: explicit tenant_id + (opsiyonel) RLS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_rag_chunks (
    chunk_id    TEXT PRIMARY KEY,
    tenant_id   UUID NOT NULL,
    document_id TEXT NOT NULL,
    chunk_index INT,
    document    TEXT NOT NULL,
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding   vector(768) NOT NULL
);

CREATE INDEX IF NOT EXISTS tenant_rag_chunks_embedding_idx
    ON tenant_rag_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS tenant_rag_chunks_tenant_idx
    ON tenant_rag_chunks (tenant_id);
CREATE INDEX IF NOT EXISTS tenant_rag_chunks_doc_idx
    ON tenant_rag_chunks (tenant_id, document_id);

-- ---------------------------------------------------------------------------
-- (ÖNERİLEN) Row Level Security — uygulama katmanındaki WHERE tenant_id = $1
-- guard'ına ek savunma. Backend, tabloların OWNER'ı OLMAYAN ve NOBYPASSRLS bir
-- rol ile bağlanırsa etkinleşir (bkz. infra/db/07_rls_hardening.sql).
-- Etkinleştirmek için aşağıyı yorumdan çıkar:
-- ---------------------------------------------------------------------------
-- ALTER TABLE tenant_rag_chunks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE tenant_rag_chunks FORCE ROW LEVEL SECURITY;
-- CREATE POLICY tenant_rag_chunks_isolation ON tenant_rag_chunks
--     USING (
--         tenant_id IN (
--             SELECT tenant_id FROM tenant_members
--             WHERE user_id = current_setting('app.current_user_id', TRUE)::UUID
--         )
--     );
