-- ============================================================================
-- Migration 23: Hatırlatıcı gönderiminde retry/backoff
-- SMTP geçici hatasında kayıt doğrudan 'failed'e düşüyordu — kaçan bir duruşma
-- hatırlatıcısı ciddi güven kaybıdır. Artık:
--   retry_count      : yapılan deneme sayısı
--   next_attempt_at  : bir sonraki deneme zamanı (üstel backoff: 5dk, 30dk)
-- 3. başarısız denemeden sonra status='failed' (kullanıcı panelde görür).
-- ============================================================================

ALTER TABLE reminders
    ADD COLUMN IF NOT EXISTS retry_count     INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ;

-- Gönderim döngüsünün taraması için indeks
CREATE INDEX IF NOT EXISTS reminders_pending_due_idx
    ON reminders (remind_at)
    WHERE status = 'pending';
