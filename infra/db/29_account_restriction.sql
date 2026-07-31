-- ============================================================================
-- Migration 29: Hesap kısıtlama (admin paneli)
-- Admin bir hesabı tamamen askıya almadan (is_active=FALSE, giriş tamamen
-- engellenir) daha hafif bir önlem olarak "kısıtlayabilsin" diye eklendi:
-- kısıtlı kullanıcı giriş yapabilir ve mevcut verilerini görebilir ama Yapay
-- Zeka üretimi / emsal arama gibi kredi tüketen modülleri kullanamaz
-- (bkz. api/kota.py kota() — email doğrulama kapısıyla aynı yerde uygulanır).
-- ============================================================================

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS restricted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS restricted_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_users_restricted_at ON users (restricted_at) WHERE restricted_at IS NOT NULL;

-- Admin panelde "onay bekleyenler" listesini hızlı filtrelemek için.
CREATE INDEX IF NOT EXISTS idx_users_pending_verification ON users (created_at) WHERE email_verified IS NULL;
