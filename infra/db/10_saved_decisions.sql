-- ============================================================================
-- Migration 10: Kaydedilen kararlar (favoriler) + emsal alarmı
-- ============================================================================

-- Kullanıcının yıldızladığı emsal kararlar (dava dosyası bazlı klasörleme).
CREATE TABLE IF NOT EXISTS user_saved_decisions (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    decision_id  TEXT NOT NULL,
    chunk_id     TEXT,
    klasor       TEXT,                  -- "Dosya 2024/123" gibi serbest etiket
    baslik       TEXT,                  -- "12. HD 2023/1234 E." görünen ad
    ozet         TEXT,                  -- kaydedilen chunk metni (önizleme)
    meta         JSONB,                 -- source, court_chamber, case_no...
    not_metni    TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, decision_id, chunk_id)
);

CREATE INDEX IF NOT EXISTS user_saved_decisions_user_idx
    ON user_saved_decisions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS user_saved_decisions_klasor_idx
    ON user_saved_decisions(user_id, klasor);

ALTER TABLE user_saved_decisions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_saved_decisions_own ON user_saved_decisions;
CREATE POLICY user_saved_decisions_own ON user_saved_decisions
    FOR ALL
    TO PUBLIC
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- Emsal alarmı: kullanıcının takip ettiği sorgular.
CREATE TABLE IF NOT EXISTS saved_search_alerts (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query        TEXT NOT NULL,
    filters      JSONB,
    aktif        BOOLEAN NOT NULL DEFAULT TRUE,
    son_kontrol  TIMESTAMPTZ,           -- eşleştirme job'ının son çalıştığı an
    son_bildirim TIMESTAMPTZ,
    son_sonuclar JSONB,                 -- son bildirilen chunk_id listesi (diff için)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, query)
);

CREATE INDEX IF NOT EXISTS saved_search_alerts_aktif_idx
    ON saved_search_alerts(aktif, son_kontrol);

ALTER TABLE saved_search_alerts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS saved_search_alerts_own ON saved_search_alerts;
CREATE POLICY saved_search_alerts_own ON saved_search_alerts
    FOR ALL
    TO PUBLIC
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

-- API erişimi (enterprise/entegrasyon): anahtarlar + günlük kota sayacı.
CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id    UUID,
    name         TEXT NOT NULL,
    key_prefix   TEXT NOT NULL,         -- "he_live_abc1" (gösterim için)
    key_hash     TEXT NOT NULL UNIQUE,  -- sha256(tam anahtar)
    aktif        BOOLEAN NOT NULL DEFAULT TRUE,
    daily_quota  INT NOT NULL DEFAULT 1000,
    last_used_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_keys_user_idx ON api_keys(user_id);

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS api_keys_own ON api_keys;
CREATE POLICY api_keys_own ON api_keys
    FOR ALL
    TO PUBLIC
    USING (user_id = current_setting('app.current_user_id', TRUE)::UUID);

CREATE TABLE IF NOT EXISTS api_key_usage (
    key_id   UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    gun      DATE NOT NULL,
    adet     INT NOT NULL DEFAULT 0,
    PRIMARY KEY (key_id, gun)
);
