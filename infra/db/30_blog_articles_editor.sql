-- 21_blog_articles_editor.sql
-- E-E-A-T: hukuki inceleme/editör kimliği ve kaynakça alanları.
-- SEO denetiminde bulgu: hukuki içerikler yazar/editör unvanı, inceleme
-- kaydı ve kaynakça olmadan "Hukukçu Yapay Zekası Editör Ekibi" gibi anonim
-- bir kimlikle yayınlanıyordu — Google E-E-A-T ve okuyucu güveni için
-- gerçek/inceleyen kişi bilgisiyle desteklenmeli (bkz. SEO_ANALIZ_VE_PLAN.md).
--
-- NOT: Bu alanlar isteğe bağlıdır ve BOŞ bırakılabilir; sahte/uydurma bir
-- avukat adı YAZILMAMALIDIR — yalnızca içeriği gerçekten inceleyen kişi
-- girilmelidir. Admin panelde "İçerik / Blog Yönetimi" ekranından doldurulur.

ALTER TABLE blog_articles
    ADD COLUMN IF NOT EXISTS editor_name  TEXT,          -- inceleyen kişi (varsa)
    ADD COLUMN IF NOT EXISTS editor_title TEXT,           -- unvan/baro sicili (örn. "Av., İstanbul Barosu")
    ADD COLUMN IF NOT EXISTS reviewed_at  TIMESTAMPTZ,    -- hukuki inceleme tarihi
    ADD COLUMN IF NOT EXISTS sources      TEXT[] NOT NULL DEFAULT '{}';  -- kaynakça (mevzuat/RG linkleri)
