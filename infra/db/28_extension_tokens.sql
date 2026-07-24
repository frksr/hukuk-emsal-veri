-- ============================================================================
-- Migration 28 — UYAP tarayıcı eklentisi için kişisel erişim anahtarları
-- ============================================================================
-- Eklenti, avukatın NextAuth oturum cookie'sine (httpOnly, farklı origin)
-- erişemez. Bunun yerine avukat panelden bir kerelik bir "erişim anahtarı"
-- üretir, eklentiye yapıştırır; eklenti her istekte bunu Authorization
-- header olarak gönderir. Backend, ham token'ı DEĞİL sha256 hash'ini saklar
-- (bkz. api/auth.py _hash_token / _resolve_extension_token).

CREATE TABLE IF NOT EXISTS extension_tokens (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL DEFAULT 'UYAP Eklentisi',
    token_hash      TEXT NOT NULL UNIQUE,  -- sha256(token) hex — ham token asla saklanmaz
    token_prefix    TEXT NOT NULL,         -- ilk 12 karakter, panelde teşhis için (örn. "uyapext_a1b2")
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS extension_tokens_hash_idx ON extension_tokens(token_hash)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS extension_tokens_tenant_idx ON extension_tokens(tenant_id, user_id);

ALTER TABLE extension_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY extension_tokens_isolation ON extension_tokens
    FOR ALL TO PUBLIC
    USING (tenant_id IN (
        SELECT tenant_id FROM tenant_members
        WHERE user_id = current_setting('app.current_user_id', TRUE)::UUID
    ));
