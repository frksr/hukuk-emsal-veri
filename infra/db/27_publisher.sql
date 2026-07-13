-- 27_publisher.sql
-- Publisher API v1 — blog otomasyonu için blog_articles tablosunu genişletir.
-- Yaklaşım 1: ayrı taslak tablosu yerine mevcut blog_articles üzerine kolonlar.
-- Tek dilli (TR): lang / group_id / hreflang alanları KASITLI olarak yok.
--
-- Yeni yayın akışı: dış sistem POST /api/publisher/drafts ile status='pending'
-- taslak oluşturur; e-postadaki onay linkiyle status='published' olur.
-- Admin panel akışı (draft/published) bozulmadan korunur.

-- 1) Yeni kolonlar (hepsi opsiyonel/defaultlu — mevcut satırlar etkilenmez).
ALTER TABLE blog_articles
    ADD COLUMN IF NOT EXISTS category         TEXT,                       -- config'deki cluster adı
    ADD COLUMN IF NOT EXISTS tags             TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS target_keyword   TEXT,                       -- hedef anahtar kelime
    ADD COLUMN IF NOT EXISTS source           TEXT,                       -- örn. 'claude-blog-automation'
    ADD COLUMN IF NOT EXISTS approve_token    TEXT,                       -- tek kullanımlık
    ADD COLUMN IF NOT EXISTS reject_token     TEXT,                       -- tek kullanımlık
    ADD COLUMN IF NOT EXISTS token_expires_at TIMESTAMPTZ,                -- now + 7 gün
    ADD COLUMN IF NOT EXISTS preview_id       TEXT,                       -- tahmin edilemez önizleme yolu
    ADD COLUMN IF NOT EXISTS reject_reason    TEXT;

-- 2) status CHECK'ini genişlet: mevcut 'draft'/'published' + otomasyon durumları.
ALTER TABLE blog_articles DROP CONSTRAINT IF EXISTS blog_articles_status_check;
ALTER TABLE blog_articles
    ADD CONSTRAINT blog_articles_status_check
    CHECK (status IN ('draft', 'pending', 'published', 'rejected', 'expired'));

-- 3) Idempotency ve token doğrulama için index'ler.
--    slug zaten UNIQUE (bkz. 20_blog_articles.sql) — slug bazlı idempotency onu kullanır.
CREATE UNIQUE INDEX IF NOT EXISTS idx_blog_articles_preview_id
    ON blog_articles (preview_id) WHERE preview_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_blog_articles_approve_token
    ON blog_articles (approve_token) WHERE approve_token IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_blog_articles_reject_token
    ON blog_articles (reject_token) WHERE reject_token IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_blog_articles_pending
    ON blog_articles (status, token_expires_at)
    WHERE status = 'pending';

-- Not: GRANT'lar 20_blog_articles.sql'de tablo düzeyinde verildiği için yeni
-- kolonlar app_user (SELECT) ve app_service (yazma) tarafından otomatik erişilir.
