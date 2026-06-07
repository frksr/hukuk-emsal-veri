-- ============================================================================
-- Migration 09 — RLS sonsuz döngü (infinite recursion) düzeltmesi
-- ============================================================================
-- SORUN: tenant_documents/tenant_queries/... politikaları
--   `tenant_id IN (SELECT tenant_id FROM tenant_members WHERE user_id = ...)`
-- alt-sorgusu kullanıyordu. tenant_members'ın KENDİ politikası da yine
-- tenant_members'a referans verdiğinden, context set edildiğinde PostgreSQL
-- "infinite recursion detected in policy for relation tenant_members" hatası
-- veriyordu. (Uygulama şimdiye kadar süperuser ile bağlandığı için RLS hiç
-- tetiklenmemiş ve bu hata görülmemişti.)
--
-- ÇÖZÜM: Kullanıcının tenant_id'lerini, RLS'i bypass eden bir SECURITY DEFINER
-- fonksiyonla hesapla. Fonksiyon owner (süperuser) olarak çalıştığı için içindeki
-- tenant_members okuması RLS'e takılmaz → recursion biter. Politikalar artık
-- alt-sorgu yerine bu fonksiyonu çağırır.
-- ============================================================================

CREATE OR REPLACE FUNCTION app_current_user_id()
RETURNS uuid
LANGUAGE sql STABLE
AS $$
    SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION app_current_tenant_ids()
RETURNS uuid[]
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
    SELECT COALESCE(array_agg(tenant_id), ARRAY[]::uuid[])
    FROM tenant_members
    WHERE user_id = app_current_user_id()
$$;

-- Fonksiyonu herkes çağırabilsin (RLS politikalarından çağrılır).
GRANT EXECUTE ON FUNCTION app_current_user_id() TO PUBLIC;
GRANT EXECUTE ON FUNCTION app_current_tenant_ids() TO PUBLIC;

-- ----------------------------------------------------------------------------
-- Politikaları fonksiyon tabanlı (recursion'sız) sürüme geçir
-- ----------------------------------------------------------------------------

-- tenant_documents
DROP POLICY IF EXISTS tenant_documents_isolation ON tenant_documents;
CREATE POLICY tenant_documents_isolation ON tenant_documents
    FOR ALL TO PUBLIC
    USING (tenant_id = ANY (app_current_tenant_ids()));

-- tenant_members: kendi üyeliğin VEYA aynı tenant'taki diğer üyeler
DROP POLICY IF EXISTS tenant_members_visibility ON tenant_members;
CREATE POLICY tenant_members_visibility ON tenant_members
    FOR SELECT TO PUBLIC
    USING (
        user_id = app_current_user_id()
        OR tenant_id = ANY (app_current_tenant_ids())
    );

-- tenant_queries
DROP POLICY IF EXISTS tenant_queries_isolation ON tenant_queries;
CREATE POLICY tenant_queries_isolation ON tenant_queries
    FOR ALL TO PUBLIC
    USING (tenant_id = ANY (app_current_tenant_ids()));

-- document_folders
DROP POLICY IF EXISTS document_folders_isolation ON document_folders;
CREATE POLICY document_folders_isolation ON document_folders
    FOR ALL TO PUBLIC
    USING (tenant_id = ANY (app_current_tenant_ids()));

-- subscriptions
DROP POLICY IF EXISTS subscriptions_isolation ON subscriptions;
CREATE POLICY subscriptions_isolation ON subscriptions
    FOR ALL TO PUBLIC
    USING (tenant_id = ANY (app_current_tenant_ids()));

-- payments
DROP POLICY IF EXISTS payments_isolation ON payments;
CREATE POLICY payments_isolation ON payments
    FOR ALL TO PUBLIC
    USING (tenant_id = ANY (app_current_tenant_ids()));

-- user_searches: kendi user_id'n (recursion yok ama fonksiyonla sadeleştir)
DROP POLICY IF EXISTS user_searches_own ON user_searches;
CREATE POLICY user_searches_own ON user_searches
    FOR ALL TO PUBLIC
    USING (user_id = app_current_user_id());
