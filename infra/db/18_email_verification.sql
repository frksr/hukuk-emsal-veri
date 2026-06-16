-- ============================================================================
-- Migration 018 — E-posta doğrulama (6 haneli kod + tek-tık link hibrit)
-- ============================================================================
-- Kod düz metin DEĞİL, sha256 hash'i saklanır (DB sızıntısında kod açığa çıkmasın).
-- Aynı kayıt hem kodu hem one-click link token'ını taşır → tek e-posta, iki yol.
-- Yalnızca service-role erişir (auth bootstrap) — password_resets gibi RLS yok.

CREATE TABLE IF NOT EXISTS email_verifications (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email        TEXT NOT NULL,
    code_hash    TEXT NOT NULL,            -- sha256(6 haneli kod)
    link_token   TEXT UNIQUE NOT NULL,     -- one-click link için uzun token
    expires_at   TIMESTAMPTZ NOT NULL,     -- kısa ömür (10 dk)
    attempts     INT NOT NULL DEFAULT 0,   -- yanlış kod denemesi sayacı
    consumed_at  TIMESTAMPTZ,              -- doğrulandı/kullanıldı
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS email_verifications_user_idx ON email_verifications(user_id);
CREATE INDEX IF NOT EXISTS email_verifications_link_idx ON email_verifications(link_token);
CREATE INDEX IF NOT EXISTS email_verifications_created_idx ON email_verifications(created_at);
