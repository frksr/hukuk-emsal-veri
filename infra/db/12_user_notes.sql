-- ============================================================================
-- Migration 12: Kullanıcı notları (kişisel çalışma alanı)
-- Kullanıcı kendi notlarını ekler, etiketler (dava/konu). Bağlamsal ipuçları için
-- etiketler + içerik üzerinden eşleştirme yapılır. RLS ile kullanıcı izolasyonu.
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_notes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    baslik      TEXT,
    icerik      TEXT NOT NULL,
    etiketler   TEXT[] NOT NULL DEFAULT '{}',   -- dava/konu etiketleri
    pinned      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS user_notes_user_idx
    ON user_notes(user_id, updated_at DESC);
-- Etiket eşleştirmesi (bağlamsal ipuçları) için GIN index
CREATE INDEX IF NOT EXISTS user_notes_etiket_idx
    ON user_notes USING GIN (etiketler);

ALTER TABLE user_notes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_notes_own ON user_notes;
CREATE POLICY user_notes_own ON user_notes
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

GRANT SELECT, INSERT, UPDATE, DELETE ON user_notes TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_notes TO app_service;
