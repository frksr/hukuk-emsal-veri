-- ============================================================================
-- Migration 13: Modül bazlı kullanım kredileri (ek paketler)
-- Kullanıcı, üst pakete geçmek yerine istediği modülden ek/kredi paketi satın
-- alabilir. Krediler hesaba (user) tanımlanır, SÜRESİZDİR (ay sonunda sıfırlanmaz).
-- Plan kotası dolunca önce krediden düşülür; o da bitince kullanım kısıtlanır.
-- ============================================================================

-- Modül bazlı güncel kredi bakiyesi (her kullanıcı + modül için tek satır).
CREATE TABLE IF NOT EXISTS usage_credits (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    module      TEXT NOT NULL,                 -- event_type: dilekce, ihtarname, arama, sorgu...
    balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, module)
);

-- Kredi hareketleri (denetim + "kredi geçmişi"): purchase / consume / grant / refund.
CREATE TABLE IF NOT EXISTS credit_transactions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE SET NULL,
    module      TEXT NOT NULL,
    delta       INTEGER NOT NULL,             -- +satın alma / -kullanım
    reason      TEXT NOT NULL,                -- 'purchase' | 'consume' | 'grant' | 'refund'
    ref         TEXT,                         -- sipariş id / olay referansı
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS credit_tx_user_idx
    ON credit_transactions(user_id, created_at DESC);

-- Ek paket siparişleri (tek seferlik ödeme). Ödeme onaylanınca krediler yüklenir.
CREATE TABLE IF NOT EXISTS credit_orders (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id    UUID REFERENCES tenants(id) ON DELETE SET NULL,
    pack_key     TEXT NOT NULL,
    amount_try   NUMERIC(10,2) NOT NULL,
    currency     TEXT NOT NULL DEFAULT 'TRY',
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending | paid | failed
    credits      JSONB NOT NULL,                   -- {module: adet, ...}
    iyzico_token TEXT,
    granted      BOOLEAN NOT NULL DEFAULT FALSE,    -- krediler yüklendi mi (idempotency)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS credit_orders_user_idx
    ON credit_orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS credit_orders_token_idx
    ON credit_orders(iyzico_token);

-- ---------------------------------------------------------------------------
-- RLS: kullanıcı yalnızca kendi kredilerini/işlemlerini/siparişlerini görür.
-- Yazma (düş/yükle) servis tarafında service_session (BYPASSRLS) ile yapılır.
-- ---------------------------------------------------------------------------
ALTER TABLE usage_credits ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS usage_credits_own ON usage_credits;
CREATE POLICY usage_credits_own ON usage_credits
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS credit_tx_own ON credit_transactions;
CREATE POLICY credit_tx_own ON credit_transactions
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

ALTER TABLE credit_orders ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS credit_orders_own ON credit_orders;
CREATE POLICY credit_orders_own ON credit_orders
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::UUID);

GRANT SELECT, INSERT, UPDATE, DELETE ON usage_credits TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON usage_credits TO app_service;
GRANT SELECT, INSERT, UPDATE, DELETE ON credit_transactions TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON credit_transactions TO app_service;
GRANT SELECT, INSERT, UPDATE, DELETE ON credit_orders TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON credit_orders TO app_service;
