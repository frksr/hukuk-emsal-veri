-- ============================================================================
-- 08 — LOCAL DEV rol parolaları (SADECE local Docker için)
-- ============================================================================
-- 07_rls_hardening.sql app_user (NOBYPASSRLS) ve app_service (BYPASSRLS)
-- rollerini oluşturur + GRANT'leri verir. Bu dosya local geliştirme için
-- bunlara parola atar; böylece DATABASE_URL=app_user ile RLS'i gerçekten test
-- edebiliriz.
--
-- ⚠️ PRODUCTION'DA BU DOSYAYI KULLANMAYIN. Parolaları orada
--    `ALTER ROLE ... PASSWORD` / IAM auth ile güvenli şekilde verin.
-- ============================================================================
ALTER ROLE app_user    PASSWORD 'app_user_pw';
ALTER ROLE app_service PASSWORD 'app_service_pw';

-- Emin olmak için: app_user owner OLMAMALI (RLS'e tabi kalsın).
-- Tablolar 'hukuk' (POSTGRES_USER) tarafından oluşturulduğu için owner odur;
-- app_user yalnızca DML yetkisine sahiptir → FORCE RLS app_user'a uygulanır.
