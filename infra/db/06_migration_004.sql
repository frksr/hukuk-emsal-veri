-- ============================================================================
-- Migration 004 — Feedback + Admin yardımcıları
-- ============================================================================

-- Geri bildirim
CREATE TABLE IF NOT EXISTS feedback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    tenant_id       UUID REFERENCES tenants(id) ON DELETE SET NULL,

    feedback_type   TEXT NOT NULL,
        -- bug | feature | praise | complaint | question | other
    severity        TEXT DEFAULT 'normal',  -- low | normal | high | critical
    page_url        TEXT,
    user_agent      TEXT,
    screen_resolution TEXT,

    subject         TEXT,
    message         TEXT NOT NULL,
    contact_email   CITEXT,  -- anonim feedback için iletişim opsiyonel

    status          TEXT NOT NULL DEFAULT 'new',
        -- new | reviewing | in_progress | resolved | wont_fix | duplicate
    assigned_to     UUID REFERENCES users(id) ON DELETE SET NULL,
    admin_note      TEXT,
    resolved_at     TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS feedback_status_idx ON feedback(status, created_at DESC);
CREATE INDEX IF NOT EXISTS feedback_user_idx ON feedback(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS feedback_type_idx ON feedback(feedback_type, severity);

CREATE TRIGGER set_timestamp_feedback BEFORE UPDATE ON feedback
    FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- Scheduled emails (welcome serisi vb.)
CREATE TABLE IF NOT EXISTS scheduled_emails (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_type      TEXT NOT NULL,
        -- welcome_day_0 | welcome_day_1 | welcome_day_3 | welcome_day_7 | ...
    scheduled_for   TIMESTAMPTZ NOT NULL,
    sent_at         TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'pending',
        -- pending | sent | failed | skipped (user unsubscribed)
    error_message   TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, email_type)
);

CREATE INDEX IF NOT EXISTS scheduled_emails_pending_idx
    ON scheduled_emails(status, scheduled_for) WHERE status = 'pending';

-- Admin notes (kullanıcı/tenant'a iliştirilen iç notlar)
CREATE TABLE IF NOT EXISTS admin_notes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_type     TEXT NOT NULL,  -- 'user' | 'tenant'
    target_id       UUID NOT NULL,
    admin_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    note            TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS admin_notes_target_idx
    ON admin_notes(target_type, target_id, created_at DESC);

-- Beta program tag
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS beta_program BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS beta_invited_by TEXT,
    ADD COLUMN IF NOT EXISTS beta_signed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS tenants_beta_idx ON tenants(beta_program) WHERE beta_program = TRUE;

-- "İlk başarı" milestones (feature flag)
CREATE TABLE IF NOT EXISTS user_milestones (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    milestone       TEXT NOT NULL,
        -- first_search | first_dilekce | first_upload | first_query | first_invoice
    reached_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, milestone)
);
