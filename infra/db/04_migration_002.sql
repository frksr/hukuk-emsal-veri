-- ============================================================================
-- Migration 002 — Library v1 başlangıcı + email/password tablolarını polish
-- ============================================================================

-- user_searches: favori + etiket
ALTER TABLE user_searches
    ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS title TEXT;  -- "Emekli maaşı haczi araştırması" gibi

CREATE INDEX IF NOT EXISTS user_searches_favorite_idx
    ON user_searches(user_id, is_favorite) WHERE is_favorite = TRUE;

-- Email verification tablosuna identifier index'i
CREATE INDEX IF NOT EXISTS verification_tokens_identifier_idx
    ON verification_tokens(identifier);

CREATE INDEX IF NOT EXISTS password_resets_user_idx
    ON password_resets(user_id, used_at);

-- audit_log retention (90 gün'den eski olanları otomatik temizle — Faz 2'de cron)
-- Şimdilik sadece partitioning planı için yorum:
-- TODO: Partition by created_at (monthly partitions for performance)
