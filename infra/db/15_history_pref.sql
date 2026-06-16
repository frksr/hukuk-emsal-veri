-- ============================================================================
-- Migration 15: Geçmiş tutma tercihi (history_enabled)
-- Kullanıcı, aramalarının ve ürettiği belgelerin geçmişe kaydedilip
-- kaydedilmeyeceğini seçebilir. Varsayılan TRUE (eski davranışla aynı).
-- Kapalıyken yeni generated_documents / user_searches kaydı yazılmaz;
-- yanıt/üretim normal döner, usage_events (analitik/limit) etkilenmez.
-- users tablosu zaten RLS'e tabi → yeni kolon erişimi otomatik gelir,
-- ekstra GRANT gerekmez.
-- ============================================================================

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS history_enabled BOOLEAN NOT NULL DEFAULT TRUE;
