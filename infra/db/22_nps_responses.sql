-- ============================================================================
-- Migration 22: NPS yanıtları (mini anket)
-- "Hukuk Emsal'i bir meslektaşınıza tavsiye etme olasılığınız?" (0-10).
-- Kullanıcı başına bir yanıt; kayıttan >= 7 gün sonra gösterilir.
-- Yazım feedback deseninde service rolü üzerinden yapılır (api/routers/feedback.py).
-- ============================================================================

CREATE TABLE IF NOT EXISTS nps_responses (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    score       INT NOT NULL CHECK (score >= 0 AND score <= 10),
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Kullanıcı başına tek yanıt (eligible kontrolü + veri bütünlüğü)
CREATE UNIQUE INDEX IF NOT EXISTS nps_responses_user_uniq ON nps_responses(user_id);
CREATE INDEX IF NOT EXISTS nps_responses_created_idx ON nps_responses(created_at DESC);

GRANT SELECT, INSERT ON nps_responses TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON nps_responses TO app_service;
