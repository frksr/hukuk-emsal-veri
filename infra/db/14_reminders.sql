-- ============================================================================
-- Migration 14: Hatırlatıcılar (reminders)
-- Kullanıcı; bir dava/dosya, kendi notları veya sitedeki herhangi bir
-- özellik/veriyle ilgili DİNAMİK hatırlatıcı oluşturur. Şu aşamada e-posta ile
-- gönderilir; channel alanı ileride WhatsApp/Telegram için genişletilebilir.
-- RLS ile kullanıcı izolasyonu (12_user_notes deseni).
-- ============================================================================

CREATE TABLE IF NOT EXISTS reminders (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id    UUID REFERENCES tenants(id) ON DELETE SET NULL,
    baslik       TEXT NOT NULL,
    not_metni    TEXT,                          -- kullanıcının eklediği serbest not
    kaynak_tip   TEXT NOT NULL DEFAULT 'serbest', -- serbest | not | dosya | uretim | arama
    kaynak_id    TEXT,                          -- ilgili kaydın id'si (varsa)
    kaynak_ozet  TEXT,                          -- listede gösterilecek kısa özet
    remind_at    TIMESTAMPTZ NOT NULL,
    channel      TEXT NOT NULL DEFAULT 'email', -- email | whatsapp | telegram (gelecek)
    status       TEXT NOT NULL DEFAULT 'pending', -- pending | sent | failed | canceled
    sent_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Kullanıcı bazlı listeleme (yaklaşan + geçmiş)
CREATE INDEX IF NOT EXISTS reminders_user_idx
    ON reminders(user_id, remind_at);
-- Dispatch (vadesi gelen bekleyenler) için
CREATE INDEX IF NOT EXISTS reminders_dispatch_idx
    ON reminders(status, remind_at);

ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS reminders_own ON reminders;
CREATE POLICY reminders_own ON reminders
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

GRANT SELECT, INSERT, UPDATE, DELETE ON reminders TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON reminders TO app_service;
