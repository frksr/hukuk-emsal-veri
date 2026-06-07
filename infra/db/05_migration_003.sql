-- ============================================================================
-- Migration 003 — Billing (iyzico) + UYAP storage refinements
-- ============================================================================

-- iyzico subscription mapping
CREATE TABLE IF NOT EXISTS subscriptions (
    id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id                 UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan_tier                 plan_tier NOT NULL,

    -- iyzico
    iyzico_subscription_ref   TEXT UNIQUE,
    iyzico_customer_ref       TEXT,
    iyzico_pricing_plan_ref   TEXT,

    -- Durum
    status                    TEXT NOT NULL DEFAULT 'pending',
        -- pending | active | upgraded | canceled | expired | failed | trial
    started_at                TIMESTAMPTZ,
    current_period_start      TIMESTAMPTZ,
    current_period_end        TIMESTAMPTZ,
    canceled_at               TIMESTAMPTZ,
    cancel_at_period_end      BOOLEAN NOT NULL DEFAULT FALSE,
    trial_ends_at             TIMESTAMPTZ,

    -- Fiyat snapshot (audit + price change tracking)
    amount_try                NUMERIC(10,2),
    currency                  TEXT NOT NULL DEFAULT 'TRY',

    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata                  JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS subscriptions_tenant_idx ON subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS subscriptions_status_idx ON subscriptions(status);
CREATE INDEX IF NOT EXISTS subscriptions_iyzico_ref_idx ON subscriptions(iyzico_subscription_ref);

-- Bireysel ödemeler / fatura kayıtları
CREATE TABLE IF NOT EXISTS payments (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscription_id   UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    iyzico_payment_id TEXT UNIQUE,
    iyzico_basket_id  TEXT,

    amount_try        NUMERIC(10,2) NOT NULL,
    currency          TEXT NOT NULL DEFAULT 'TRY',
    status            TEXT NOT NULL,
        -- success | failure | refunded | partial_refund
    failure_reason    TEXT,

    paid_at           TIMESTAMPTZ,
    refunded_at       TIMESTAMPTZ,

    -- KVKK + Fatura
    invoice_number    TEXT,
    invoice_pdf_url   TEXT,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS payments_tenant_idx ON payments(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS payments_sub_idx ON payments(subscription_id);

-- iyzico webhook event log (idempotency + debug)
CREATE TABLE IF NOT EXISTS webhook_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider        TEXT NOT NULL,  -- "iyzico"
    event_type      TEXT NOT NULL,
    iyzico_token    TEXT UNIQUE,    -- Unique idempotency key
    payload         JSONB NOT NULL,
    processed       BOOLEAN NOT NULL DEFAULT FALSE,
    process_error   TEXT,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS webhook_events_processed_idx
    ON webhook_events(processed, received_at);


-- ============================================================================
-- UYAP / tenant_documents iyileştirme
-- ============================================================================

-- Klasör/etiket sistemi
CREATE TABLE IF NOT EXISTS document_folders (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    parent_id   UUID REFERENCES document_folders(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,  -- "/dava/2024/icra"
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE(tenant_id, path)
);

CREATE INDEX IF NOT EXISTS document_folders_tenant_idx
    ON document_folders(tenant_id, path);

-- tenant_documents: folder_id + tags + içerik özeti
ALTER TABLE tenant_documents
    ADD COLUMN IF NOT EXISTS folder_id UUID REFERENCES document_folders(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS summary TEXT,         -- AI özeti
    ADD COLUMN IF NOT EXISTS topic_tags JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS pii_audit JSONB,      -- PII detection sonucu
    ADD COLUMN IF NOT EXISTS qdrant_namespace TEXT;-- per-tenant vector ns

CREATE INDEX IF NOT EXISTS tenant_documents_folder_idx
    ON tenant_documents(tenant_id, folder_id);

-- AI sorgu geçmişi (per-tenant)
CREATE TABLE IF NOT EXISTS tenant_queries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    query_text      TEXT NOT NULL,
    answer_text     TEXT,
    document_ids    UUID[],  -- hangi tenant_documents'da çalışıldı
    chunk_count     INT,
    llm_provider    TEXT,
    tokens_used     INT,
    duration_ms     INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS tenant_queries_tenant_idx
    ON tenant_queries(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS tenant_queries_user_idx
    ON tenant_queries(user_id, created_at DESC);

-- RLS for tenant_queries
ALTER TABLE tenant_queries ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_queries_isolation ON tenant_queries
    FOR ALL TO PUBLIC
    USING (tenant_id IN (
        SELECT tenant_id FROM tenant_members
        WHERE user_id = current_setting('app.current_user_id', TRUE)::UUID
    ));

ALTER TABLE document_folders ENABLE ROW LEVEL SECURITY;
CREATE POLICY document_folders_isolation ON document_folders
    FOR ALL TO PUBLIC
    USING (tenant_id IN (
        SELECT tenant_id FROM tenant_members
        WHERE user_id = current_setting('app.current_user_id', TRUE)::UUID
    ));

-- updated_at trigger
CREATE TRIGGER set_timestamp_subscriptions BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
