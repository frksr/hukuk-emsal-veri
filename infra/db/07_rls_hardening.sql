-- ============================================================================
-- Migration 004b — RLS sertleştirme + per-tenant envelope key tablosu
-- ============================================================================
-- Bu migration üç production-blocker'ı kapatır:
--   1) Tablo OWNER'ı RLS'i bypass eder → FORCE ROW LEVEL SECURITY + ayrı app rolü
--   2) Billing tabloları (subscriptions/payments) RLS dışıydı → policy eklendi
--   3) "Kriptografik silme" için gerçek per-tenant DEK saklama tablosu
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1) FORCE ROW LEVEL SECURITY
-- ----------------------------------------------------------------------------
-- ENABLE ROW LEVEL SECURITY tek başına YETMEZ: tablonun owner'ı (ve BYPASSRLS
-- yetkili roller) politikaları yine de atlar. Backend, owner rolüyle bağlanırsa
-- (ör. `postgres`), tüm RLS sessizce devre dışı kalır. FORCE, owner için de
-- politikaları zorunlu kılar.
ALTER TABLE tenant_documents  FORCE ROW LEVEL SECURITY;
ALTER TABLE user_searches     FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_log         FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_members    FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_queries    FORCE ROW LEVEL SECURITY;
ALTER TABLE document_folders  FORCE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 2) Billing tablolarına RLS (tenant izolasyonu)
-- ----------------------------------------------------------------------------
-- NOT: Webhook handler bu politikaların ETRAFINDAN dolaşmalıdır (cross-tenant
-- güncelleme yapar) — bunun için service rolü (aşağıda) kullanılır. Normal
-- kullanıcı bağlantıları sadece kendi tenant'ının kayıtlarını görür.

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS subscriptions_isolation ON subscriptions;
CREATE POLICY subscriptions_isolation ON subscriptions
    FOR ALL TO PUBLIC
    USING (tenant_id IN (
        SELECT tenant_id FROM tenant_members
        WHERE user_id = current_setting('app.current_user_id', TRUE)::UUID
    ));

ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payments_isolation ON payments;
CREATE POLICY payments_isolation ON payments
    FOR ALL TO PUBLIC
    USING (tenant_id IN (
        SELECT tenant_id FROM tenant_members
        WHERE user_id = current_setting('app.current_user_id', TRUE)::UUID
    ));

-- ----------------------------------------------------------------------------
-- 3) Service rolü (RLS bypass) — webhook + arka plan işleri için
-- ----------------------------------------------------------------------------
-- İki ayrı bağlantı/rol modeli önerilir:
--   * app_user  : RLS'e TABİ. Kullanıcı istekleri (FastAPI request scope) bunu
--                 kullanır → tenant context set_config ile verilir.
--   * app_service: BYPASSRLS. Webhook, cron, admin purge gibi cross-tenant
--                 işler bunu kullanır.
--
-- Bu roller idempotent şekilde oluşturulur; parolaları deployment sırasında
-- `ALTER ROLE ... PASSWORD` ile (veya IAM auth ile) verilmelidir.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_service') THEN
        CREATE ROLE app_service LOGIN BYPASSRLS;
    END IF;
END
$$;

-- app_user'a DML yetkisi (tabloların owner'ı bu rolü GRANT etmeli)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;

GRANT app_user TO app_service;  -- service de aynı tablolara erişir ama BYPASSRLS

-- ----------------------------------------------------------------------------
-- 4) Per-tenant envelope encryption key (gerçek kriptografik silme)
-- ----------------------------------------------------------------------------
-- DEK (Data Encryption Key) RASTGELE üretilir, master key ile sarmalanıp
-- (wrapped) burada saklanır. Tenant verisi DEK ile şifrelenir.
-- Tenant silinince bu satır silinir → wrapped DEK yok olur → master key
-- elde olsa bile veri ÇÖZÜLEMEZ. Bu, KVKK m.7 "silme hakkı" için kriptografik
-- silme (crypto-shredding) garantisini gerçekten sağlar.
--
-- Eski sürüm DEK'i master+tenant_id'den deterministik türetiyordu (HKDF) ve
-- saklamıyordu; o yöntemde master key durdukça tenant silinse de veri geri
-- çözülebiliyordu → KVKK silme garantisi YOKTU.
CREATE TABLE IF NOT EXISTS tenant_encryption_keys (
    tenant_id    UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    wrapped_dek  BYTEA NOT NULL,   -- master key ile AES-GCM şifreli DEK
    dek_iv       BYTEA NOT NULL,   -- wrap işleminin IV'si
    key_version  INT NOT NULL DEFAULT 1,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rotated_at   TIMESTAMPTZ
);

-- Bu tablo sadece backend (service rolü) tarafından okunur/yazılır.
-- Kullanıcı bağlantılarının ASLA erişmemesi için RLS ile tümüyle kapatıyoruz
-- (hiçbir policy yok → app_user için tüm satırlar görünmez; app_service BYPASSRLS
-- ile erişir).
ALTER TABLE tenant_encryption_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_encryption_keys FORCE ROW LEVEL SECURITY;
REVOKE ALL ON tenant_encryption_keys FROM app_user;

-- ----------------------------------------------------------------------------
-- 5) Webhook imza/idempotency için ek alanlar
-- ----------------------------------------------------------------------------
ALTER TABLE webhook_events
    ADD COLUMN IF NOT EXISTS signature_valid BOOLEAN,
    ADD COLUMN IF NOT EXISTS reconciled      BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source_ip       TEXT;
