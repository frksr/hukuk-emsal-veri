-- Bekleme listesi tablosu
-- Fiyatlandırma sayfasından katılan kullanıcıların kayıtları.

CREATE TABLE IF NOT EXISTS waitlist (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    plan       TEXT,                        -- pro_solo | pro_solo_uyap | team | NULL
    ip         TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Aynı e-posta tekrar kayıt olmasın
CREATE UNIQUE INDEX IF NOT EXISTS waitlist_email_uniq ON waitlist(email);
CREATE INDEX IF NOT EXISTS waitlist_created_idx ON waitlist(created_at DESC);
