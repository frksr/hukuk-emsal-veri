-- ============================================================================
-- Hukuk Emsal — Cloud SQL (PostgreSQL 16) TAM ŞEMA (tek dosya)
-- ============================================================================
-- Bu dosya 01..18 migration'larının BİRLEŞTİRİLMİŞ ve Cloud SQL'e uyarlanmış
-- halidir. Boş bir Cloud SQL veritabanında BİR KEZ çalıştırılır.
--
-- NASIL ÇALIŞTIRILIR (Cloud SQL Auth Proxy ile, owner 'hukuk' olarak):
--   ./cloud-sql-proxy PROJECT:REGION:INSTANCE &
--   psql "postgresql://hukuk:SIFRE@localhost:5432/hukuk_emsal" -f schema_cloud.sql
--
-- ÖN KOŞUL (gcloud ile zaten oluşturulmuş olmalı):
--   gcloud sql users create hukuk     --instance=... --password=...   (tablo OWNER)
--   gcloud sql users create app_user  --instance=... --password=...   (request scope)
--
-- CLOUD UYARLAMALARI (lokal migration'lardan farklar):
--   * FORCE ROW LEVEL SECURITY UYGULANMAZ → owner 'hukuk' (service/admin DSN'leri)
--     RLS'i bypass eder; 'app_user' (request DSN) ise policy'lere tabidir.
--   * app_service BYPASSRLS ile OLUŞTURULAMAZ (Cloud SQL kısıtı). NOLOGIN olarak
--     yalnızca GRANT'ler geçerli olsun diye eklenir; cloud'da KULLANILMAZ
--     (service/admin = owner 'hukuk').
--   * Dev seed admin'i (03_seed) hariç tutuldu → en altta create_admin.py notu.
--   * ALTER ... ADD COLUMN migration'ları ilgili CREATE TABLE içine gömüldü.
-- ============================================================================

SET client_min_messages = WARNING;

-- ----------------------------------------------------------------------------
-- EKLENTİLER
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "citext";

-- ----------------------------------------------------------------------------
-- ENUM TİPLERİ (idempotent)
-- ----------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE tenant_type AS ENUM ('solo', 'team', 'enterprise');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE plan_tier AS ENUM (
        'free', 'pro_solo', 'pro_solo_uyap', 'team', 'team_uyap', 'enterprise'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE tenant_role AS ENUM ('owner', 'admin', 'lawyer', 'paralegal', 'viewer');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE document_status AS ENUM ('uploaded', 'processing', 'ready', 'error');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ============================================================================
-- TABLOLAR + INDEX'LER  (bağımlılık sırasıyla)
-- ============================================================================

-- USERS (15: history_enabled, 16: billing gömülü) ----------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           CITEXT UNIQUE NOT NULL,
    email_verified  TIMESTAMPTZ,
    name            TEXT,
    image           TEXT,
    password_hash   TEXT,
    role            TEXT NOT NULL DEFAULT 'user',          -- user | admin
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    kvkk_accepted_at  TIMESTAMPTZ,
    marketing_consent BOOLEAN NOT NULL DEFAULT FALSE,
    locale          TEXT NOT NULL DEFAULT 'tr-TR',
    history_enabled BOOLEAN NOT NULL DEFAULT TRUE,          -- migration 15
    billing         JSONB NOT NULL DEFAULT '{}'::jsonb,     -- migration 16
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS users_email_idx ON users(email);
CREATE INDEX IF NOT EXISTS users_created_at_idx ON users(created_at DESC);

-- ACCOUNTS (NextAuth OAuth) --------------------------------------------------
CREATE TABLE IF NOT EXISTS accounts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type                TEXT NOT NULL,
    provider            TEXT NOT NULL,
    provider_account_id TEXT NOT NULL,
    refresh_token       TEXT,
    access_token        TEXT,
    expires_at          BIGINT,
    token_type          TEXT,
    scope               TEXT,
    id_token            TEXT,
    session_state       TEXT,
    UNIQUE(provider, provider_account_id)
);
CREATE INDEX IF NOT EXISTS accounts_user_id_idx ON accounts(user_id);

-- SESSIONS -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_token   TEXT UNIQUE NOT NULL,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires         TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address      INET,
    user_agent      TEXT
);
CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);
CREATE INDEX IF NOT EXISTS sessions_expires_idx ON sessions(expires);

-- VERIFICATION TOKENS --------------------------------------------------------
CREATE TABLE IF NOT EXISTS verification_tokens (
    identifier  TEXT NOT NULL,
    token       TEXT UNIQUE NOT NULL,
    expires     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (identifier, token)
);
CREATE INDEX IF NOT EXISTS verification_tokens_identifier_idx ON verification_tokens(identifier);

-- PASSWORD RESETS ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS password_resets (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS password_resets_user_idx ON password_resets(user_id, used_at);

-- TENANTS (06: beta_* gömülü) ------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT NOT NULL,
    slug                TEXT UNIQUE NOT NULL,
    type                tenant_type NOT NULL DEFAULT 'solo',
    plan_tier           plan_tier NOT NULL DEFAULT 'free',
    plan_started_at     TIMESTAMPTZ,
    plan_expires_at     TIMESTAMPTZ,
    trial_ends_at       TIMESTAMPTZ,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    encryption_key_id   TEXT,
    max_users           INT NOT NULL DEFAULT 1,
    max_uyap_documents  INT NOT NULL DEFAULT 0,
    max_monthly_queries INT NOT NULL DEFAULT 0,
    iyzico_customer_id  TEXT,
    iyzico_subscription_id TEXT,
    billing_email       CITEXT,
    kvkk_data_controller TEXT,
    kvkk_verbis_no       TEXT,
    beta_program        BOOLEAN NOT NULL DEFAULT FALSE,     -- migration 06
    beta_invited_by     TEXT,                               -- migration 06
    beta_signed_at      TIMESTAMPTZ,                        -- migration 06
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS tenants_slug_idx ON tenants(slug);
CREATE INDEX IF NOT EXISTS tenants_plan_idx ON tenants(plan_tier) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS tenants_beta_idx ON tenants(beta_program) WHERE beta_program = TRUE;

-- TENANT MEMBERS -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_members (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        tenant_role NOT NULL DEFAULT 'lawyer',
    invited_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, user_id)
);
CREATE INDEX IF NOT EXISTS tenant_members_user_id_idx ON tenant_members(user_id);
CREATE INDEX IF NOT EXISTS tenant_members_tenant_id_idx ON tenant_members(tenant_id);

-- USAGE EVENTS ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usage_events (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    tenant_id       UUID REFERENCES tenants(id) ON DELETE SET NULL,
    event_type      TEXT NOT NULL,
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS usage_events_user_day_idx ON usage_events(user_id, event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS usage_events_ip_day_idx ON usage_events(ip_address, event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS usage_events_tenant_idx ON usage_events(tenant_id, event_type, created_at DESC);

-- USER SEARCHES (04: is_favorite/tags/title gömülü) --------------------------
CREATE TABLE IF NOT EXISTS user_searches (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query       TEXT NOT NULL,
    result_count INT,
    filters     JSONB,
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,             -- migration 04
    tags        JSONB DEFAULT '[]'::jsonb,                  -- migration 04
    title       TEXT,                                       -- migration 04
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS user_searches_user_idx ON user_searches(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS user_searches_favorite_idx ON user_searches(user_id, is_favorite) WHERE is_favorite = TRUE;

-- DOCUMENT FOLDERS (tenant_documents.folder_id'den önce) ---------------------
CREATE TABLE IF NOT EXISTS document_folders (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    parent_id   UUID REFERENCES document_folders(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE(tenant_id, path)
);
CREATE INDEX IF NOT EXISTS document_folders_tenant_idx ON document_folders(tenant_id, path);

-- TENANT DOCUMENTS (05: folder_id/tags/summary/... gömülü) -------------------
CREATE TABLE IF NOT EXISTS tenant_documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    uploaded_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    title           TEXT NOT NULL,
    case_no         TEXT,
    decision_no     TEXT,
    court           TEXT,
    document_type   TEXT,
    file_name       TEXT,
    file_size       BIGINT,
    file_mime       TEXT,
    storage_key     TEXT,
    raw_text        TEXT,
    cleaned_text    TEXT,
    chunk_count     INT DEFAULT 0,
    status          document_status NOT NULL DEFAULT 'uploaded',
    error_message   TEXT,
    encrypted       BOOLEAN NOT NULL DEFAULT TRUE,
    encryption_iv   BYTEA,
    document_date   DATE,
    folder_id       UUID REFERENCES document_folders(id) ON DELETE SET NULL,  -- migration 05
    tags            JSONB DEFAULT '[]'::jsonb,                                -- migration 05
    summary         TEXT,                                                     -- migration 05
    topic_tags      JSONB DEFAULT '[]'::jsonb,                                -- migration 05
    pii_audit       JSONB,                                                    -- migration 05
    qdrant_namespace TEXT,                                                    -- migration 05
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS tenant_documents_tenant_idx ON tenant_documents(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS tenant_documents_case_idx ON tenant_documents(tenant_id, case_no);
CREATE INDEX IF NOT EXISTS tenant_documents_folder_idx ON tenant_documents(tenant_id, folder_id);

-- AUDIT LOG ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    resource    TEXT,
    ip_address  INET,
    user_agent  TEXT,
    success     BOOLEAN NOT NULL DEFAULT TRUE,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS audit_log_user_idx ON audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_tenant_idx ON audit_log(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_action_idx ON audit_log(action, created_at DESC);

-- SUBSCRIPTIONS --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subscriptions (
    id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id                 UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan_tier                 plan_tier NOT NULL,
    iyzico_subscription_ref   TEXT UNIQUE,
    iyzico_customer_ref       TEXT,
    iyzico_pricing_plan_ref   TEXT,
    status                    TEXT NOT NULL DEFAULT 'pending',
    started_at                TIMESTAMPTZ,
    current_period_start      TIMESTAMPTZ,
    current_period_end        TIMESTAMPTZ,
    canceled_at               TIMESTAMPTZ,
    cancel_at_period_end      BOOLEAN NOT NULL DEFAULT FALSE,
    trial_ends_at             TIMESTAMPTZ,
    amount_try                NUMERIC(10,2),
    currency                  TEXT NOT NULL DEFAULT 'TRY',
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata                  JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS subscriptions_tenant_idx ON subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS subscriptions_status_idx ON subscriptions(status);
CREATE INDEX IF NOT EXISTS subscriptions_iyzico_ref_idx ON subscriptions(iyzico_subscription_ref);

-- PAYMENTS -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscription_id   UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    iyzico_payment_id TEXT UNIQUE,
    iyzico_basket_id  TEXT,
    amount_try        NUMERIC(10,2) NOT NULL,
    currency          TEXT NOT NULL DEFAULT 'TRY',
    status            TEXT NOT NULL,
    failure_reason    TEXT,
    paid_at           TIMESTAMPTZ,
    refunded_at       TIMESTAMPTZ,
    invoice_number    TEXT,
    invoice_pdf_url   TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS payments_tenant_idx ON payments(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS payments_sub_idx ON payments(subscription_id);

-- WEBHOOK EVENTS (07: signature_valid/reconciled/source_ip gömülü) -----------
CREATE TABLE IF NOT EXISTS webhook_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider        TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    iyzico_token    TEXT UNIQUE,
    payload         JSONB NOT NULL,
    processed       BOOLEAN NOT NULL DEFAULT FALSE,
    process_error   TEXT,
    signature_valid BOOLEAN,                                -- migration 07
    reconciled      BOOLEAN NOT NULL DEFAULT FALSE,         -- migration 07
    source_ip       TEXT,                                   -- migration 07
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS webhook_events_processed_idx ON webhook_events(processed, received_at);

-- TENANT QUERIES -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_queries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    query_text      TEXT NOT NULL,
    answer_text     TEXT,
    document_ids    UUID[],
    chunk_count     INT,
    llm_provider    TEXT,
    tokens_used     INT,
    duration_ms     INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS tenant_queries_tenant_idx ON tenant_queries(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS tenant_queries_user_idx ON tenant_queries(user_id, created_at DESC);

-- TENANT ENCRYPTION KEYS (crypto-shredding) ----------------------------------
CREATE TABLE IF NOT EXISTS tenant_encryption_keys (
    tenant_id    UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    wrapped_dek  BYTEA NOT NULL,
    dek_iv       BYTEA NOT NULL,
    key_version  INT NOT NULL DEFAULT 1,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rotated_at   TIMESTAMPTZ
);

-- FEEDBACK -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    tenant_id       UUID REFERENCES tenants(id) ON DELETE SET NULL,
    feedback_type   TEXT NOT NULL,
    severity        TEXT DEFAULT 'normal',
    page_url        TEXT,
    user_agent      TEXT,
    screen_resolution TEXT,
    subject         TEXT,
    message         TEXT NOT NULL,
    contact_email   CITEXT,
    status          TEXT NOT NULL DEFAULT 'new',
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

-- SCHEDULED EMAILS -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS scheduled_emails (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_type      TEXT NOT NULL,
    scheduled_for   TIMESTAMPTZ NOT NULL,
    sent_at         TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'pending',
    error_message   TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, email_type)
);
CREATE INDEX IF NOT EXISTS scheduled_emails_pending_idx ON scheduled_emails(status, scheduled_for) WHERE status = 'pending';

-- ADMIN NOTES ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_notes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_type     TEXT NOT NULL,
    target_id       UUID NOT NULL,
    admin_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    note            TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS admin_notes_target_idx ON admin_notes(target_type, target_id, created_at DESC);

-- USER MILESTONES ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_milestones (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    milestone       TEXT NOT NULL,
    reached_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, milestone)
);

-- USER SAVED DECISIONS -------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_saved_decisions (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    decision_id  TEXT NOT NULL,
    chunk_id     TEXT,
    klasor       TEXT,
    baslik       TEXT,
    ozet         TEXT,
    meta         JSONB,
    not_metni    TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, decision_id, chunk_id)
);
CREATE INDEX IF NOT EXISTS user_saved_decisions_user_idx ON user_saved_decisions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS user_saved_decisions_klasor_idx ON user_saved_decisions(user_id, klasor);

-- SAVED SEARCH ALERTS --------------------------------------------------------
CREATE TABLE IF NOT EXISTS saved_search_alerts (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query        TEXT NOT NULL,
    filters      JSONB,
    aktif        BOOLEAN NOT NULL DEFAULT TRUE,
    son_kontrol  TIMESTAMPTZ,
    son_bildirim TIMESTAMPTZ,
    son_sonuclar JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, query)
);
CREATE INDEX IF NOT EXISTS saved_search_alerts_aktif_idx ON saved_search_alerts(aktif, son_kontrol);

-- API KEYS + USAGE -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id    UUID,
    name         TEXT NOT NULL,
    key_prefix   TEXT NOT NULL,
    key_hash     TEXT NOT NULL UNIQUE,
    aktif        BOOLEAN NOT NULL DEFAULT TRUE,
    daily_quota  INT NOT NULL DEFAULT 1000,
    last_used_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS api_keys_user_idx ON api_keys(user_id);

CREATE TABLE IF NOT EXISTS api_key_usage (
    key_id   UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    gun      DATE NOT NULL,
    adet     INT NOT NULL DEFAULT 0,
    PRIMARY KEY (key_id, gun)
);

-- GENERATED DOCUMENTS --------------------------------------------------------
CREATE TABLE IF NOT EXISTS generated_documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    tool        TEXT NOT NULL,
    alt_tur     TEXT,
    baslik      TEXT,
    girdi_ozeti TEXT,
    cikti       TEXT,
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS generated_documents_user_idx ON generated_documents(user_id, created_at DESC);

-- USER NOTES -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_notes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    baslik      TEXT,
    icerik      TEXT NOT NULL,
    etiketler   TEXT[] NOT NULL DEFAULT '{}',
    pinned      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS user_notes_user_idx ON user_notes(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS user_notes_etiket_idx ON user_notes USING GIN (etiketler);

-- USAGE CREDITS / TRANSACTIONS / ORDERS --------------------------------------
CREATE TABLE IF NOT EXISTS usage_credits (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    module      TEXT NOT NULL,
    balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, module)
);

CREATE TABLE IF NOT EXISTS credit_transactions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    module      TEXT NOT NULL,
    delta       INTEGER NOT NULL,
    reason      TEXT NOT NULL,
    ref         TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS credit_tx_user_idx ON credit_transactions(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS credit_orders (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id    UUID REFERENCES tenants(id) ON DELETE SET NULL,
    pack_key     TEXT NOT NULL,
    amount_try   NUMERIC(10,2) NOT NULL,
    currency     TEXT NOT NULL DEFAULT 'TRY',
    status       TEXT NOT NULL DEFAULT 'pending',
    credits      JSONB NOT NULL,
    iyzico_token TEXT,
    granted      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS credit_orders_user_idx ON credit_orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS credit_orders_token_idx ON credit_orders(iyzico_token);

-- REMINDERS ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reminders (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id    UUID REFERENCES tenants(id) ON DELETE SET NULL,
    baslik       TEXT NOT NULL,
    not_metni    TEXT,
    kaynak_tip   TEXT NOT NULL DEFAULT 'serbest',
    kaynak_id    TEXT,
    kaynak_ozet  TEXT,
    remind_at    TIMESTAMPTZ NOT NULL,
    channel      TEXT NOT NULL DEFAULT 'email',
    status       TEXT NOT NULL DEFAULT 'pending',
    sent_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS reminders_user_idx ON reminders(user_id, remind_at);
CREATE INDEX IF NOT EXISTS reminders_dispatch_idx ON reminders(status, remind_at);

-- EMAIL VERIFICATIONS --------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_verifications (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email        TEXT NOT NULL,
    code_hash    TEXT NOT NULL,
    link_token   TEXT UNIQUE NOT NULL,
    expires_at   TIMESTAMPTZ NOT NULL,
    attempts     INT NOT NULL DEFAULT 0,
    consumed_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS email_verifications_user_idx ON email_verifications(user_id);
CREATE INDEX IF NOT EXISTS email_verifications_link_idx ON email_verifications(link_token);
CREATE INDEX IF NOT EXISTS email_verifications_created_idx ON email_verifications(created_at);

-- APP CONFIG (global, RLS yok) -----------------------------------------------
CREATE TABLE IF NOT EXISTS app_config (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- YARDIMCI FONKSİYONLAR + updated_at TRIGGER'LARI
-- ============================================================================
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_timestamp_users ON users;
CREATE TRIGGER set_timestamp_users BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
DROP TRIGGER IF EXISTS set_timestamp_tenants ON tenants;
CREATE TRIGGER set_timestamp_tenants BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
DROP TRIGGER IF EXISTS set_timestamp_documents ON tenant_documents;
CREATE TRIGGER set_timestamp_documents BEFORE UPDATE ON tenant_documents
    FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
DROP TRIGGER IF EXISTS set_timestamp_subscriptions ON subscriptions;
CREATE TRIGGER set_timestamp_subscriptions BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
DROP TRIGGER IF EXISTS set_timestamp_feedback ON feedback;
CREATE TRIGGER set_timestamp_feedback BEFORE UPDATE ON feedback
    FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- RLS yardımcı fonksiyonları (09 — recursion'sız) ----------------------------
CREATE OR REPLACE FUNCTION app_current_user_id()
RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION app_current_tenant_ids()
RETURNS uuid[] LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT COALESCE(array_agg(tenant_id), ARRAY[]::uuid[])
    FROM tenant_members
    WHERE user_id = app_current_user_id()
$$;

GRANT EXECUTE ON FUNCTION app_current_user_id() TO PUBLIC;
GRANT EXECUTE ON FUNCTION app_current_tenant_ids() TO PUBLIC;

-- ============================================================================
-- ROLLER (Cloud SQL) + GRANT'LER
-- ============================================================================
-- app_user : LOGIN, NOBYPASSRLS — request scope (DATABASE_URL). RLS'e TABİ.
--            Cloud'da 'gcloud sql users create app_user' ile zaten parolasıyla
--            oluşturulmuş olabilir → varsa atlanır.
-- app_service : Cloud SQL BYPASSRLS oluşturmaya izin vermez. NOLOGIN olarak
--            yalnızca aşağıdaki GRANT'ler geçerli olsun diye eklenir.
--            CLOUD'DA KULLANILMAZ: service/admin = owner 'hukuk' (FORCE RLS yok
--            olduğundan owner policy'leri bypass eder).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_service') THEN
        CREATE ROLE app_service NOLOGIN;
    END IF;
END
$$;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;
GRANT app_user TO app_service;

-- app_config: okuma app_user, yazma yalnızca service (admin endpoint'leri owner ile)
GRANT SELECT ON app_config TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_config TO app_service;

-- ============================================================================
-- ROW LEVEL SECURITY (ENABLE — FORCE YOK; owner 'hukuk' bypass eder)
-- ============================================================================
ALTER TABLE tenant_documents       ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_searches          ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log              ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_members         ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_queries         ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_folders       ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions          ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments               ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_encryption_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_saved_decisions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_search_alerts    ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys               ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_documents    ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_notes             ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_credits          ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_transactions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_orders          ENABLE ROW LEVEL SECURITY;
ALTER TABLE reminders              ENABLE ROW LEVEL SECURITY;

-- Tenant izolasyonu (recursion'sız, fonksiyon tabanlı) ------------------------
DROP POLICY IF EXISTS tenant_documents_isolation ON tenant_documents;
CREATE POLICY tenant_documents_isolation ON tenant_documents
    FOR ALL TO PUBLIC USING (tenant_id = ANY (app_current_tenant_ids()));

DROP POLICY IF EXISTS tenant_queries_isolation ON tenant_queries;
CREATE POLICY tenant_queries_isolation ON tenant_queries
    FOR ALL TO PUBLIC USING (tenant_id = ANY (app_current_tenant_ids()));

DROP POLICY IF EXISTS document_folders_isolation ON document_folders;
CREATE POLICY document_folders_isolation ON document_folders
    FOR ALL TO PUBLIC USING (tenant_id = ANY (app_current_tenant_ids()));

DROP POLICY IF EXISTS subscriptions_isolation ON subscriptions;
CREATE POLICY subscriptions_isolation ON subscriptions
    FOR ALL TO PUBLIC USING (tenant_id = ANY (app_current_tenant_ids()));

DROP POLICY IF EXISTS payments_isolation ON payments;
CREATE POLICY payments_isolation ON payments
    FOR ALL TO PUBLIC USING (tenant_id = ANY (app_current_tenant_ids()));

DROP POLICY IF EXISTS tenant_members_visibility ON tenant_members;
CREATE POLICY tenant_members_visibility ON tenant_members
    FOR SELECT TO PUBLIC
    USING (user_id = app_current_user_id() OR tenant_id = ANY (app_current_tenant_ids()));

-- Kullanıcı bazlı izolasyon ---------------------------------------------------
DROP POLICY IF EXISTS user_searches_own ON user_searches;
CREATE POLICY user_searches_own ON user_searches
    FOR ALL TO PUBLIC USING (user_id = app_current_user_id());

DROP POLICY IF EXISTS audit_log_own ON audit_log;
CREATE POLICY audit_log_own ON audit_log
    FOR SELECT TO PUBLIC
    USING (
        user_id = current_setting('app.current_user_id', TRUE)::UUID
        OR EXISTS (
            SELECT 1 FROM users
            WHERE id = current_setting('app.current_user_id', TRUE)::UUID
              AND role = 'admin'
        )
    );

DROP POLICY IF EXISTS user_saved_decisions_own ON user_saved_decisions;
CREATE POLICY user_saved_decisions_own ON user_saved_decisions
    FOR ALL TO PUBLIC USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

DROP POLICY IF EXISTS saved_search_alerts_own ON saved_search_alerts;
CREATE POLICY saved_search_alerts_own ON saved_search_alerts
    FOR ALL TO PUBLIC USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

DROP POLICY IF EXISTS api_keys_own ON api_keys;
CREATE POLICY api_keys_own ON api_keys
    FOR ALL TO PUBLIC USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

DROP POLICY IF EXISTS generated_documents_own ON generated_documents;
CREATE POLICY generated_documents_own ON generated_documents
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

DROP POLICY IF EXISTS user_notes_own ON user_notes;
CREATE POLICY user_notes_own ON user_notes
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

DROP POLICY IF EXISTS usage_credits_own ON usage_credits;
CREATE POLICY usage_credits_own ON usage_credits
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

DROP POLICY IF EXISTS credit_tx_own ON credit_transactions;
CREATE POLICY credit_tx_own ON credit_transactions
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

DROP POLICY IF EXISTS credit_orders_own ON credit_orders;
CREATE POLICY credit_orders_own ON credit_orders
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

DROP POLICY IF EXISTS reminders_own ON reminders;
CREATE POLICY reminders_own ON reminders
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- tenant_encryption_keys: app_user'a TAMAMEN kapalı (policy yok + REVOKE) -----
REVOKE ALL ON tenant_encryption_keys FROM app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_encryption_keys TO app_service;
-- (Owner 'hukuk' bu tabloya tam erişir; cloud'da DEK okuma/yazma owner ile yapılır.)

-- ============================================================================
-- BİTTİ. Sonraki adım — admin kullanıcı (dev seed admin BİLEREK eklenmedi):
--   ./cloud-sql-proxy PROJECT:REGION:INSTANCE &
--   export ADMIN_DATABASE_URL='postgresql://hukuk:SIFRE@localhost:5432/hukuk_emsal'
--   python scripts/create_admin.py --email admin@hukukcuyapayzekasi.com --password 'GUCLU' --name 'Admin'
-- ============================================================================
