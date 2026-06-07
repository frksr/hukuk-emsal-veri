-- ============================================================================
-- Hukuk Emsal — PostgreSQL Schema (Faz 1)
-- ============================================================================
-- Multi-tenant SaaS için tasarlanmış şema.
-- Tier sistemi: anonim, free, pro, pro_uyap, team, team_uyap, enterprise
-- Row-Level Security per tenant (Pro/Team/Enterprise için)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "citext";  -- case-insensitive email

-- ============================================================================
-- USERS & AUTH
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           CITEXT UNIQUE NOT NULL,
    email_verified  TIMESTAMPTZ,
    name            TEXT,
    image           TEXT,
    password_hash   TEXT,  -- bcrypt; NULL if OAuth-only
    role            TEXT NOT NULL DEFAULT 'user',  -- user | admin
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,

    -- KVKK
    kvkk_accepted_at        TIMESTAMPTZ,
    marketing_consent       BOOLEAN NOT NULL DEFAULT FALSE,

    -- Meta
    locale          TEXT NOT NULL DEFAULT 'tr-TR',
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS users_email_idx ON users(email);
CREATE INDEX IF NOT EXISTS users_created_at_idx ON users(created_at DESC);

-- NextAuth Account (OAuth providers)
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

-- NextAuth Sessions
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

-- Email verification tokens
CREATE TABLE IF NOT EXISTS verification_tokens (
    identifier  TEXT NOT NULL,
    token       TEXT UNIQUE NOT NULL,
    expires     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (identifier, token)
);

-- Password reset
CREATE TABLE IF NOT EXISTS password_resets (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================================
-- TENANTS (Solo avukat veya hukuk büro)
-- ============================================================================

CREATE TYPE tenant_type AS ENUM ('solo', 'team', 'enterprise');
CREATE TYPE plan_tier AS ENUM (
    'free',           -- ücretsiz, hesap var
    'pro_solo',       -- ₺499 — bireysel avukat
    'pro_solo_uyap',  -- ₺799 — UYAP eklentili
    'team',           -- ₺1499 — 5 kullanıcı
    'team_uyap',      -- ₺1999 — UYAP eklentili
    'enterprise'      -- özel
);

CREATE TABLE IF NOT EXISTS tenants (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT NOT NULL,  -- "Mehmet Avukatlık" veya "ABC Hukuk Bürosu"
    slug                TEXT UNIQUE NOT NULL,  -- URL-safe
    type                tenant_type NOT NULL DEFAULT 'solo',
    plan_tier           plan_tier NOT NULL DEFAULT 'free',
    plan_started_at     TIMESTAMPTZ,
    plan_expires_at     TIMESTAMPTZ,
    trial_ends_at       TIMESTAMPTZ,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,

    -- Şifreleme (per-tenant key)
    encryption_key_id   TEXT,  -- KMS key reference, NULL for free

    -- Limits (override edilebilir)
    max_users           INT NOT NULL DEFAULT 1,
    max_uyap_documents  INT NOT NULL DEFAULT 0,
    max_monthly_queries INT NOT NULL DEFAULT 0,

    -- Billing
    iyzico_customer_id  TEXT,
    iyzico_subscription_id TEXT,
    billing_email       CITEXT,

    -- KVKK
    kvkk_data_controller TEXT,  -- veri sorumlusu adı (büro için)
    kvkk_verbis_no       TEXT,  -- VERBİS kayıt no

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS tenants_slug_idx ON tenants(slug);
CREATE INDEX IF NOT EXISTS tenants_plan_idx ON tenants(plan_tier) WHERE is_active = TRUE;


-- Tenant membership (bir user birden çok tenant'ta olabilir — sadece team için)
CREATE TYPE tenant_role AS ENUM ('owner', 'admin', 'lawyer', 'paralegal', 'viewer');

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


-- ============================================================================
-- USAGE TRACKING (rate limit + analytics)
-- ============================================================================

CREATE TABLE IF NOT EXISTS usage_events (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,  -- NULL = anonim
    tenant_id       UUID REFERENCES tenants(id) ON DELETE SET NULL,
    event_type      TEXT NOT NULL,  -- arama, dilekce, ozet, faiz, ihtarname, ...
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Daily aggregate for rate limit checks
CREATE INDEX IF NOT EXISTS usage_events_user_day_idx
    ON usage_events(user_id, event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS usage_events_ip_day_idx
    ON usage_events(ip_address, event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS usage_events_tenant_idx
    ON usage_events(tenant_id, event_type, created_at DESC);


-- ============================================================================
-- USER SEARCHES (geçmiş — Free hesap ve üstü)
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_searches (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query       TEXT NOT NULL,
    result_count INT,
    filters     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS user_searches_user_idx
    ON user_searches(user_id, created_at DESC);


-- ============================================================================
-- TENANT DOCUMENTS (UYAP yükle — Pro+)
-- ============================================================================

CREATE TYPE document_status AS ENUM ('uploaded', 'processing', 'ready', 'error');

CREATE TABLE IF NOT EXISTS tenant_documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    uploaded_by     UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Belge meta
    title           TEXT NOT NULL,
    case_no         TEXT,    -- Esas no (örn 2024/1234)
    decision_no     TEXT,    -- Karar no
    court           TEXT,    -- Mahkeme
    document_type   TEXT,    -- dilekce, karar, sozlesme, evrak, ...
    file_name       TEXT,
    file_size       BIGINT,
    file_mime       TEXT,
    storage_key     TEXT,    -- S3 / local path (şifreli)

    -- İçerik
    raw_text        TEXT,    -- Parse edilmiş ham metin (şifreli storage'da da var)
    cleaned_text    TEXT,
    chunk_count     INT DEFAULT 0,

    -- Status
    status          document_status NOT NULL DEFAULT 'uploaded',
    error_message   TEXT,

    -- Şifreleme
    encrypted       BOOLEAN NOT NULL DEFAULT TRUE,
    encryption_iv   BYTEA,

    -- Zaman
    document_date   DATE,   -- Belgenin asıl tarihi
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS tenant_documents_tenant_idx
    ON tenant_documents(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS tenant_documents_case_idx
    ON tenant_documents(tenant_id, case_no);


-- ============================================================================
-- AUDIT LOG (KVKK için kritik)
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,  -- login, logout, document.read, document.create, ...
    resource    TEXT,           -- "document:abc-123"
    ip_address  INET,
    user_agent  TEXT,
    success     BOOLEAN NOT NULL DEFAULT TRUE,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_log_user_idx ON audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_tenant_idx ON audit_log(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_action_idx ON audit_log(action, created_at DESC);


-- ============================================================================
-- HELPERS
-- ============================================================================

-- updated_at otomatik
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_timestamp_users BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
CREATE TRIGGER set_timestamp_tenants BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
CREATE TRIGGER set_timestamp_documents BEFORE UPDATE ON tenant_documents
    FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();
