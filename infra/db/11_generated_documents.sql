-- ============================================================================
-- Migration 11: AI üretim geçmişi (generated_documents)
-- Dilekçe / ihtarname / özet / denetim / karşı argüman / sözleşme analizi gibi
-- AI üretimlerinin kullanıcı bazlı geçmişi. RLS ile tenant/kullanıcı izolasyonu.
-- ============================================================================

CREATE TABLE IF NOT EXISTS generated_documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    tool        TEXT NOT NULL,        -- dilekce | ihtarname | ozet | denetim | karsi_argument | sozlesme
    alt_tur     TEXT,                 -- dilekce_turu / ihtarname türü vb. (opsiyonel)
    baslik      TEXT,                 -- kısa başlık (listeleme için)
    girdi_ozeti TEXT,                 -- kullanıcının girdisinin kısaltılmış özeti
    cikti       TEXT,                 -- üretilen metin/sonuç
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS generated_documents_user_idx
    ON generated_documents(user_id, created_at DESC);

-- RLS: kullanıcı yalnızca kendi üretimlerini görür/yazar (user_searches deseni).
ALTER TABLE generated_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS generated_documents_own ON generated_documents;
CREATE POLICY generated_documents_own ON generated_documents
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- DML yetkileri (07_rls_hardening ile aynı model)
GRANT SELECT, INSERT, DELETE ON generated_documents TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON generated_documents TO app_service;
