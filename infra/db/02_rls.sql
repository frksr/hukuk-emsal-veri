-- ============================================================================
-- Row-Level Security Policies
-- ============================================================================
-- Multi-tenant izolasyon için kritik. PostgreSQL bağlantı başına
-- `SET LOCAL app.current_user_id = 'uuid'`
-- `SET LOCAL app.current_tenant_id = 'uuid'`
-- ile context set edilir, sorgular otomatik filtrelenir.
-- ============================================================================

-- tenant_documents: sadece tenant üyeleri görebilir
ALTER TABLE tenant_documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_documents_isolation ON tenant_documents
    FOR ALL
    TO PUBLIC
    USING (
        tenant_id IN (
            SELECT tenant_id FROM tenant_members
            WHERE user_id = current_setting('app.current_user_id', TRUE)::UUID
        )
    );

-- user_searches: sadece kendi
ALTER TABLE user_searches ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_searches_own ON user_searches
    FOR ALL
    TO PUBLIC
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- audit_log: kullanıcı sadece kendi log'unu görebilir (admin hariç)
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_log_own ON audit_log
    FOR SELECT
    TO PUBLIC
    USING (
        user_id = current_setting('app.current_user_id', TRUE)::UUID
        OR EXISTS (
            SELECT 1 FROM users
            WHERE id = current_setting('app.current_user_id', TRUE)::UUID
              AND role = 'admin'
        )
    );

-- tenant_members: sadece kendi üyeliklerini ve aynı tenant'taki diğer üyeleri
ALTER TABLE tenant_members ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_members_visibility ON tenant_members
    FOR SELECT
    TO PUBLIC
    USING (
        user_id = current_setting('app.current_user_id', TRUE)::UUID
        OR tenant_id IN (
            SELECT tenant_id FROM tenant_members
            WHERE user_id = current_setting('app.current_user_id', TRUE)::UUID
        )
    );

-- Service role bypass (admin operations için):
-- ROLE service_role'una BYPASS yetki ver, sadece backend kullanır
-- CREATE ROLE service_role BYPASSRLS;
-- GRANT service_role TO postgres;
