-- 17_app_config.sql
-- Global uygulama ayarları (plan limitleri, ek paket kataloğu) — admin panelden
-- düzenlenebilir. Kod yerine DB'den okunan dinamik konfigürasyon.
--
-- RLS YOK: tenant'a bağlı olmayan GLOBAL ayar. Okuma herkese (app_user) açık,
-- yazma yalnızca servis rolüne (app_service) — admin endpoint'leri service_session
-- üzerinden yazar.

CREATE TABLE IF NOT EXISTS app_config (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

GRANT SELECT ON app_config TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_config TO app_service;
