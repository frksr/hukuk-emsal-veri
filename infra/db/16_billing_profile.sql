-- ============================================================================
-- Migration 16: Kullanıcı fatura bilgileri (profil)
-- Kullanıcı, fatura/şirket bilgilerini bir kez kaydeder; ödeme (abonelik + ek
-- paket) sırasında otomatik kullanılır. Esnek olması için JSONB tutulur:
--   { "unvan", "vergi_no", "vergi_dairesi", "adres", "sehir", "posta", "telefon" }
-- ============================================================================

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS billing JSONB NOT NULL DEFAULT '{}'::jsonb;
