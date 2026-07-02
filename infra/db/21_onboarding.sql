-- ============================================================================
-- Migration 21: Onboarding turu tamamlanma bayrağı
-- Kullanıcı panele ilk girişte 4 adımlık tanıtım turunu görür; "Geç" veya
-- "Başla" ile kapattığında bu bayrak TRUE yapılır ve tur bir daha gösterilmez.
-- ============================================================================

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS onboarding_done BOOLEAN NOT NULL DEFAULT FALSE;
