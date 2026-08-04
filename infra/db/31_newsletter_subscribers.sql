-- ============================================================================
-- Migration 31: Haftalık bülten aboneleri (blog yayın bildirimi)
--
-- Anonim (hesapsız) e-posta ile abone olunabilir; opsiyonel olarak giriş
-- yapmış bir kullanıcıya bağlanabilir (user_id nullable). Yeni bir blog
-- makalesi yayınlandığında (bkz. api/routers/icerik.py admin_yayinla)
-- status='active' olan tüm aboneler bilgilendirme e-postası alır.
--
-- status:
--   active       → bildirim gönderilir (varsayılan)
--   unsubscribed → kullanıcı kendi isteğiyle (tek-tık link, unsubscribe_token)
--                  veya admin tarafından çıkarıldı
--   blocked      → admin tarafından bildirim gönderimi engellendi (kullanıcı
--                  kendi isteğiyle bu duruma geçemez — yalnızca admin)
--
-- RLS YOK (waitlist/blog_articles ile aynı desen — global, tenant'a bağlı değil).
-- ============================================================================

CREATE TABLE IF NOT EXISTS newsletter_subscribers (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email             CITEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'unsubscribed', 'blocked')),
    user_id           UUID REFERENCES users(id) ON DELETE SET NULL,
    unsubscribe_token TEXT NOT NULL,
    consent_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unsubscribed_at   TIMESTAMPTZ,
    blocked_at        TIMESTAMPTZ,
    blocked_by        UUID REFERENCES users(id) ON DELETE SET NULL,
    blocked_reason    TEXT,
    ip                TEXT,
    last_sent_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS newsletter_subscribers_email_uniq ON newsletter_subscribers(email);
CREATE UNIQUE INDEX IF NOT EXISTS newsletter_subscribers_token_uniq ON newsletter_subscribers(unsubscribe_token);
CREATE INDEX IF NOT EXISTS newsletter_subscribers_status_idx ON newsletter_subscribers(status);
CREATE INDEX IF NOT EXISTS newsletter_subscribers_created_idx ON newsletter_subscribers(created_at DESC);

-- Public abonelik/çıkış akışı ve admin işlemleri service_session (BYPASSRLS)
-- üzerinden yapılır (feedback.py deseni) — app_user'a yine de SELECT/INSERT
-- veriliyor (diğer global tablolarla tutarlılık için), asıl yazım yolu değil.
GRANT SELECT, INSERT ON newsletter_subscribers TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON newsletter_subscribers TO app_service;
