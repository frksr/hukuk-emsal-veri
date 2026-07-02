-- ============================================================================
-- Migration 24: Bekleme listesi CRM alanları
-- Admin panelden davet gönderimi ve dönüşüm takibi için:
--   status      : bekliyor | davet_edildi | kayit_oldu
--   invited_at  : davet e-postasının gönderildiği an
--   invite_code : kayıt linkindeki tekil davet kodu (/kayit?davet=<kod>)
--   notes       : admin notu (serbest metin)
-- Davet gönderimi service rolü üzerinden yapılır (api/routers/waitlist.py);
-- kayıt akışı (Next.js, app_user) davet kodunu 'kayit_oldu' olarak işaretler.
-- ============================================================================

ALTER TABLE waitlist
    ADD COLUMN IF NOT EXISTS status      TEXT NOT NULL DEFAULT 'bekliyor',
    ADD COLUMN IF NOT EXISTS invited_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invite_code TEXT,
    ADD COLUMN IF NOT EXISTS notes       TEXT;

-- Geçerli durum değerleri (idempotent — constraint varsa dokunma)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'waitlist_status_chk' AND conrelid = 'waitlist'::regclass
    ) THEN
        ALTER TABLE waitlist
            ADD CONSTRAINT waitlist_status_chk
            CHECK (status IN ('bekliyor', 'davet_edildi', 'kayit_oldu'));
    END IF;
END $$;

-- Davet kodu tekil olmalı (NULL'lar hariç — henüz davet edilmeyenler)
CREATE UNIQUE INDEX IF NOT EXISTS waitlist_invite_code_uniq
    ON waitlist(invite_code) WHERE invite_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS waitlist_status_idx ON waitlist(status);

-- Kayıt akışı (Next.js) davet kodunu işaretleyebilsin diye app_user'a UPDATE;
-- admin CRM işlemleri app_service (BYPASSRLS) üzerinden.
GRANT SELECT, INSERT, UPDATE ON waitlist TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON waitlist TO app_service;
