-- ============================================================================
-- Seed data — development için
-- ============================================================================

-- Admin user (development only)
INSERT INTO users (email, name, password_hash, role, email_verified, kvkk_accepted_at)
VALUES (
    'admin@hukukemsal.tr',
    'Sistem Yöneticisi',
    -- bcrypt hash for 'change-me-in-prod' — production'da ASLA bu hash kullanma
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj3MlcQjP6Ye',
    'admin',
    NOW(),
    NOW()
)
ON CONFLICT (email) DO NOTHING;

-- Default tier limits (uygulama tarafında okunur)
-- Bunlar config'tedir, DB'de sadece referans için.
