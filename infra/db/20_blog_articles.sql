-- 20_blog_articles.sql
-- Admin panelden yönetilen blog/rehber makaleleri (içerik + otomatik SEO).
-- Public site yalnızca status='published' kayıtları gösterir.
--
-- RLS YOK: tenant'a bağlı olmayan GLOBAL içerik. Okuma app_user'a açık (yalnız
-- yayınlananlar endpoint katmanında filtrelenir), yazma yalnız app_service
-- (admin endpoint'leri service_session üzerinden yazar).

CREATE TABLE IF NOT EXISTS blog_articles (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug             TEXT UNIQUE NOT NULL,
    title            TEXT NOT NULL,
    excerpt          TEXT,                       -- liste kartı / özet
    body             TEXT NOT NULL DEFAULT '',   -- markdown gövde
    -- Otomatik SEO çıktıları:
    meta_title       TEXT,
    meta_description TEXT,
    keywords         TEXT[] NOT NULL DEFAULT '{}',
    faq              JSONB  NOT NULL DEFAULT '[]'::jsonb,  -- [{soru, cevap}]
    seo_score        INT    NOT NULL DEFAULT 0,
    seo_notes        JSONB  NOT NULL DEFAULT '[]'::jsonb,  -- ["...öneri", ...]
    -- Yayın durumu:
    status           TEXT   NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft', 'published')),
    author           TEXT   NOT NULL DEFAULT 'Hukukçu Yapay Zekası Editör Ekibi',
    cover_image      TEXT,
    published_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blog_articles_status_pub
    ON blog_articles (status, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_blog_articles_slug
    ON blog_articles (slug);

GRANT SELECT ON blog_articles TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON blog_articles TO app_service;
