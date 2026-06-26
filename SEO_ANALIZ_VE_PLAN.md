# Hukuk Emsal — Detaylı SEO Analizi, Eksikler ve İmplementasyon Planı

**Tarih:** 2026-06-20
**Kapsam:** `web/` (Next.js App Router frontend) — kod seviyesinde teknik denetim
**Üretim domaini:** `hukukcuyapayzekasi.com`
**Önceki belge:** `SEO_STRATEJI.md` (2026-06-09) — bu belge onun teknik denetimini günceller ve genişletir

---

## 0.A Uygulama durumu — 2026-06-26 (Faz 0 + Faz 1 başlangıcı)

Aşağıdaki maddeler bu tarihte koda işlendi. Marka adı, en yüksek hacimli baş
terim referans alınarak **"Hukukçu Yapay Zekası"** (domain uyumlu entity) +
title/etiketlerde **"Emsal Karar Arama"** anahtar kelimesi olarak tekleştirildi.

| Bulgu | Durum | Uygulanan değişiklik |
|---|---|---|
| B2 Domain çatalı | ✅ | `next.config.js` + `next.config.mjs` default'ları ve `serverActions.allowedOrigins` → `hukukcuyapayzekasi.com` |
| B1 Sitemap keşfi | ✅ | Yeni `app/sitemap_index.xml/route.ts` (sitemap index); `robots.ts` artık `/sitemap_index.xml`'i bildiriyor (statik + 10× karar sitemap) |
| B4 Ana sayfa FAQ | ✅ | `app/page.tsx` 8 soruyu `buildFaqJsonLd` ile FAQPage schema'sı olarak basıyor |
| B5 Marka/NAP | ✅ | `lib/seo.ts SITE_NAME`, `layout.tsx` (title/OG/Twitter/authors/LegalService), `page.tsx` (WebSite/Organization) hizalandı; var olmayan `sameAs` linkleri kaldırıldı |
| B8 Title uzunluğu | ✅ | Ana sayfa title ≤60 karaktere indirildi, baş terim title başında |
| B10 Karar metadata | ✅ | Description konu etiketlerinden kuruluyor, sayfaya özel `og:image`, keywords + Twitter card eklendi |
| B9 Sitemap lastmod | ✅ | `sitemap.ts` sabit `CONTENT_LAST_UPDATED` tarihine bağlandı |
| B11 AI crawler | ✅ | `GPTBot`, `OAI-SearchBot`, `CCBot`, `PerplexityBot` public sayfalara açıldı; panel/auth/api disallow |
| B6 Long-tail (Faz 1) | ✅ kısmi | İlk 3 alt sayfa: `/ihtarname/kira-tahliye`, `/ihtarname/alacak`, `/zamanasimi/cek` (her biri özgün H1 + içerik + FAQPage schema + iç link); sitemap'e eklendi |
| B3 Karar özet-öncelikli | ✅ | `app/karar/[id]/page.tsx` özgün, server-render "Karar Özeti" ile başlıyor (kaynak/daire/tarih/konu + cümle-sınırlı lede); tam metin katlanır `<details>` içinde; Article JSON-LD açıklaması özetten. **Paywall korundu**: AI analizi Pro upsell, LLM maliyeti eklenmedi |
| B7 Blog/rehber hub | ✅ | `/blog` index + 2 makale ("emsal karar nedir", "ihtarname nasıl çekilir") Article + FAQPage schema, araç CTA iç linkleri; footer'a "Hukuk Rehberi" linki; sitemap'e eklendi |
| İlgili kararlar (iç linkleme) | ✅ | `services/rag.py → related_decisions()` (aynı daire, yoksa aynı kaynak; parquet/DuckDB, LLM yok); `GET /api/karar/benzer/{id}` (6 saat cache); karar sayfasında "İlgili Kararlar" bloğu — orphan sayfalar bağlandı |
| `/api/karar/liste` (sitemap) | ✅ doğrulandı | Endpoint + `list_decisions()` **zaten mevcut ve kayıtlı** (`api/routers/karar.py`, `main.py` satır 225). Sitemap çalışıyor; önceki "eksik" notu hatalıydı |

**B3 / AI özeti hakkında karar:** Karar sayfasının özgün içeriği, **LLM'siz
server-render "Karar Özeti"** ile sağlandı (duplicate/thin riskini giderir).
Paid "Yapay Zeka özeti" (`/api/ozet`, `kota("ozet")` — Pro) bilinçli olarak
public HTML'e KONULMADI: (a) paywall'ı zayıflatır, (b) ~10K sayfa için crawl
başına/önden LLM maliyeti doğurur. İstenirse ileride **kalıcı önbelleğe alınmış
kısa AI lede** (Pro tam analizden ayrı) ayrı bir pipeline + backfill ile eklenebilir.

**B6 genişletme:** `/zamanasimi/kira` alt sayfası eklendi (kira alacağı zamanaşımı,
TBK 147; FAQPage + iç link). Toplam long-tail alt sayfa: `/ihtarname/kira-tahliye`,
`/ihtarname/alacak`, `/zamanasimi/cek`, `/zamanasimi/kira`.

**B12:** `SEO_STRATEJI.md` "ARŞİV" notuyla işaretlendi; tek geçerli kaynak bu belge.

### 0.B İçerik Yönetim Sistemi (Blog CMS) + otomatik SEO — 2026-06-26

Admin panelden makale ekleme/düzenleme/yayınlama ve **otomatik SEO** akışı kuruldu:

| Katman | Dosya | İşlev |
|---|---|---|
| DB | `infra/db/20_blog_articles.sql` | `blog_articles` tablosu (slug, başlık, gövde, meta_*, keywords[], faq jsonb, status, seo_score, seo_notes, published_at) — GLOBAL, RLS yok |
| Otomatik SEO | `services/seo_uret.py` | `makale_seo_uret()`: LLM ile meta_title/description/keywords/slug/FAQ üretir; **LLM yoksa heuristik fallback**. `seo_skor_hesapla()`: 0-100 skor + iyileştirme notları. `slugify()` Türkçe-duyarlı |
| Backend | `api/routers/icerik.py` | Public: `/liste`, `/makale/{slug}` (yalnız yayınlananlar). Admin: CRUD + `/seo` (otomatik üret) + `/yayinla` + `/taslak`. `main.py`'ye kayıtlı (`/api/icerik`) |
| Admin UI | `web/app/panel/admin/icerik/` | Liste (durum + SEO skoru), editör (başlık/gövde/meta/SSS), **“SEO Üret”** ve **“Yayınla”** butonları; sidebar'a “İçerik / Blog” linki |
| Public | `web/app/blog/[slug]/page.tsx` | Yayınlanan makaleyi DB'den çeker; hafif Markdown render + Article & FAQPage JSON-LD + `generateMetadata`. Blog index ve `sitemap.ts` yayınlananları otomatik dahil eder (API erişilemezse statik içeriğe **graceful fallback**) |

**Akış:** Admin “Yeni Makale” → başlık+gövde girer → **“SEO Üret”** (meta/keywords/FAQ
+ skor otomatik dolar) → **“Yayınla”** → makale anında `/blog/<slug>` adresinde,
blog index'inde ve sitemap'te görünür. Küratörlü statik makaleler korunur (aynı slug'da
statik öncelikli).

**Kalan (sürekli/ölçek):** karar sitemap'ini kademeli 10K→tam ölçek; ek blog
makaleleri (artık panelden); istenirse karar sayfaları için kalıcı önbellekli kısa AI lede.

> **Not (doğrulama):** Kod düzenlemeleri bu oturumda dosya aracıyla (Read)
> bütünüyle teyit edildi; ancak sandbox'ın OneDrive mount'u düzenlenen mevcut
> dosyaları gecikmeli senkronladığından `npm run build` / `py_compile` bu
> oturumda mount üzerinden çalıştırılamadı. Deploy öncesi kendi ortamında
> `cd web && npm run type-check && npm run build` ve API için
> `python -m py_compile services/rag.py api/routers/karar.py` çalıştırın.

**Deploy sonrası (kod dışı) doğrulama:** lokalde `cd web && npm run type-check`
ve `npm run build`; ardından GSC'ye `/sitemap_index.xml` gönder, Rich Results
Test ile ana sayfa FAQPage + bir alt sayfa FAQPage + bir karar sayfası Article
geçerliliğini doğrula.

---

## 0. Yönetici özeti

Teknik SEO temeli büyük ölçüde sağlam: metadata helper'ı (`lib/seo.ts`), server-render JSON-LD, canonical/OG/Twitter etiketleri, `robots.ts`, statik sitemap, güvenlik header'ları ve PWA asset'leri yerinde. Ancak **stratejinin en büyük getirisi olan 10.000 karar sayfası (programatik long-tail) şu anda Google tarafından keşfedilemiyor** ve **domain konfigürasyonu iki ayrı değere bölünmüş durumda** — bu ikisi P0 (acil) sorun.

En kritik 5 bulgu:

1. **Karar sitemap'leri keşfedilemiyor (P0).** `/karar/sitemap/0..9.xml` üretiliyor ama hiçbir sitemap index onları listelemiyor; `robots.ts` yalnızca `/sitemap.xml`'i bildiriyor. → 10.000 karar URL'i indekslenmez.
2. **Domain konfigürasyonu tutarsız (P0).** `next.config.js` ve `next.config.mjs` `NEXT_PUBLIC_SITE_URL` varsayılanını `hukukemsal.tr`, geri kalan tüm dosyalar `hukukcuyapayzekasi.com` veriyor. Env set edilmezse canonical/OG/sitemap yanlış domaine işaret eder.
3. **Karar sayfaları tam metni gösteriyor (P1).** Strateji "özet yayınla" diyordu; sayfa `cleaned_text`'in tamamını basıyor → resmî kaynaklarla **duplicate content** + telif/TOS riski + AI özeti yalnızca tıklamayla (HTML dışı) geliyor, indekslenmez.
4. **Ana sayfa SSS'inde FAQPage schema yok (P1).** 8 soruluk zengin SSS var ama JSON-LD basılmıyor; oysa `/faiz-hesaplayici`, `/zamanasimi` vb. sayfalarda var. Rich result fırsatı kaçıyor.
5. **Cluster A/C alt sayfaları ve blog (Cluster B) hiç yok (P1).** `/ihtarname/kira-tahliye`, `/zamanasimi/cek` gibi long-tail sayfalar ve `/blog` içerik hub'ı stratejide vardı, kodda yok.

Hızlı kazanımlar (1 günlük işler): domain'i tek değere sabitle, sitemap index ekle, ana sayfaya FAQ schema bas, brand adını ve sosyal linkleri tek tipleştir.

---

## 1. Teknik SEO denetimi — mevcut durum

### 1.1 İyi durumda olan (korunmalı)

| Alan | Durum | Kanıt |
|---|---|---|
| Merkezî metadata helper | ✅ | `lib/seo.ts → buildMetadata()` title/description uzunluk uyarısıyla |
| Canonical + hreflang (tr-TR) | ✅ | `buildMetadata` `alternates.canonical` + `languages` |
| OpenGraph + Twitter card | ✅ | `layout.tsx`, `seo.ts`; `summary_large_image` |
| JSON-LD server-render | ✅ | `layout.tsx` `<head>` içinde `LegalService`; `<JsonLd>` bileşeni |
| robots.txt route | ✅ | `app/robots.ts` — admin/app/auth disallow |
| Statik sitemap | ✅ | `app/sitemap.ts` — 16 public route |
| Karar sitemap üretimi | ⚠️ kısmi | `app/karar/sitemap.ts` `generateSitemaps` (10×1000) — **ama keşfedilemiyor (bkz. 1.2)** |
| Güvenlik header'ları | ✅ | `next.config.mjs headers()` — XFO, nosniff, Referrer-Policy |
| PWA / favicon / OG asset | ✅ | `public/` dolu; `og-default.png`, manifest, tüm favicon boyutları |
| Dinamik OG image route | ✅ | `app/api/og/route.tsx` mevcut |
| Thin/auth sayfaları noindex | ✅ | `robots.ts` disallow + auth sayfaları sitemap dışı |
| ISR / revalidate | ✅ | Karar sayfası `revalidate = 86400` |
| Erişilebilirlik temeli | ✅ | skip-link, `aria-labelledby`, semantik `h1/h2/h3` |
| GSC verification kancası | ✅ | `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION` env |

### 1.2 Bulunan eksikler (kanıtlı)

**B1 — Karar sitemap'leri keşfedilemiyor — KRİTİK**
`app/karar/sitemap.ts` `generateSitemaps()` ile `/karar/sitemap/0.xml … 9.xml` üretir (10.000 URL). Ancak:
- `app/robots.ts` yalnızca `${SITE_URL}/sitemap.xml` satırını içerir.
- `app/sitemap.ts` yalnızca 16 statik route döndürür; karar sitemap'lerine referans yok.
- Bunları birbirine bağlayan bir **sitemap index** yok.

Sonuç: Google karar URL'lerini sitemap üzerinden bulamaz. İç linkleme de zayıf (yalnızca `/emsal-arama`'dan dinamik). Stratejinin en büyük fırsatı (Cluster C) fiilen devre dışı.

**B2 — Domain konfigürasyonu çatallanmış — KRİTİK**
- `next.config.js` ve `next.config.mjs`: `NEXT_PUBLIC_SITE_URL` default = `https://hukukemsal.tr`, `serverActions.allowedOrigins = ["localhost:3000", "hukukemsal.tr"]`.
- `lib/seo.ts`, `app/robots.ts`, `app/sitemap.ts`, `app/page.tsx`, `app/karar/...`: default = `https://hukukcuyapayzekasi.com`.

`NEXT_PUBLIC_SITE_URL` ortamda set edilmezse `metadataBase`, canonical, OG URL ve sitemap **yanlış domaine** işaret eder; set edilse bile `next.config` env bloğu prod build'de değeri ezerek tutarsızlık üretebilir. Tek doğru değere indirgenmeli.

**B3 — Karar sayfaları tam metin yayınlıyor (duplicate + thin) — YÜKSEK**
`app/karar/[id]/page.tsx` `cleaned_text`'in tamamını basar. Sorunlar:
- Resmî kaynaklar (karararama.yargitay.gov.tr, emsal.uyap.gov.tr) ve ücretli arşivlerle **birebir duplicate content** → düşük sıralama, "indexed but not ranking".
- AI özeti (`AiOzetButton`) yalnızca client'ta tıklamayla gelir → ilk HTML'de yok → indekslenmez → sayfanın özgün katma değeri crawler'a görünmez.
- İlgili/benzer kararlara iç link yok; her sayfa CTA dışında izole.
- Telif/TOS sürtüşmesi (strateji bunu açıkça uyarmıştı).

**B4 — Ana sayfa FAQ schema'sı eksik — YÜKSEK**
`app/page.tsx` 8 soruluk SSS render eder ama yalnızca `websiteJsonLd` + `organizationJsonLd` basar. `buildFaqJsonLd` mevcut ve `/faiz-hesaplayici`, `/zamanasimi`, `/belge-denetim`, `/fiyatlandirma` kullanıyor — ana sayfa kullanmıyor. En çok trafik alan sayfada FAQ rich result fırsatı kayıp.

**B5 — Brand / entity / NAP tutarsızlığı — ORTA**
Tek üründe 4 farklı ad geçiyor: `lib/seo.ts SITE_NAME="Hukuk Emsal"`, `layout.tsx` title "Türk Hukuk Asistanı", `page.tsx` Organization "Türk Hukuk Emsal Asistanı", domain "hukukcuyapayzekasi.com". `organizationJsonLd.sameAs` `twitter.com/hukukemsal` ve `linkedin.com/company/hukuk-emsal`'e işaret ediyor (domain ile uyumsuz, muhtemelen mevcut değil). Entity/marka sinyalleri dağılıyor.

**B6 — Programatik alt sayfalar yok (Cluster A×C) — YÜKSEK fırsat**
`/ihtarname/kira-tahliye`, `/ihtarname/alacak`, `/zamanasimi/cek`, `/zamanasimi/kira` gibi long-tail sayfalar yok (`app/ihtarname/`, `app/zamanasimi/` yalnızca tek `page.tsx`). En yüksek niyetli, kazanılabilir kümeler boş.

**B7 — Blog / içerik hub'ı yok (Cluster B) — ORTA**
`/blog`, `/rehber` route'u yok. "emsal karar nedir", "ihtarname nasıl çekilir" gibi otorite/E-E-A-T içeriği ve makale→araç→kayıt hunisi mevcut değil.

**B8 — Title uzunluğu SERP'te kesiliyor — DÜŞÜK**
Ana sayfa title'ı "Türk Hukuk Emsal Karar Arama | İcra, Tahsilat, İhtar Yapay Zeka Asistanı" (~70 karakter) > 60. `buildMetadata` dev'de uyarıyor ama prod'da no-op; SERP'te kesilir.

**B9 — Sitemap `lastModified` her build'de `new Date()` — DÜŞÜK**
`app/sitemap.ts` tüm statik route'lara `new Date()` (build anı) verir. Gerçekte değişmeyen sayfalar her deploy'da "değişti" görünür → lastmod sinyalinin güveni düşer.

**B10 — Karar `generateMetadata` zayıf — DÜŞÜK**
`og:image` sayfaya özel değil (default), description ham `cleaned_text`'in ilk 155 karakteri (genelde mahkeme başlığı/usul metni — düşük CTR), keyword yok.

**B11 — AI crawler'ları (GPTBot/CCBot) tamamen engelli — STRATEJİK KARAR**
`robots.ts` `GPTBot` ve `CCBot`'a `disallow: "/"`. ChatGPT/Perplexity gibi AI aramada görünürlük isteniyorsa yeniden değerlendirilmeli (trafik kaynağı olarak büyüyor). İçerik korunması isteniyorsa kalsın — ama bilinçli karar olmalı.

**B12 — `SEO_STRATEJI.md` güncelliğini yitirdi — DÜŞÜK**
Belge hâlâ `hukukemsal.tr` domainini referans alıyor; üretim `hukukcuyapayzekasi.com`. Karışıklığı önlemek için güncellenmeli/işaretlenmeli.

---

## 2. Eksiklerin önceliklendirilmesi

Etki × efor matrisi. P0 = lansman/indeksleme'yi bloke eder, hemen; P1 = yüksek getiri, 2-4 hafta; P2 = orta vade.

| # | Bulgu | Etki | Efor | Öncelik |
|---|---|---|---|---|
| B2 | Domain konfig çatalı | İndeksleme/canonical bütünlüğü | XS (1-2 satır) | **P0** |
| B1 | Karar sitemap keşfedilemiyor | 10K sayfa indekslenmiyor | S (sitemap index) | **P0** |
| B4 | Ana sayfa FAQ schema yok | Rich result kaybı | XS | **P0** |
| B5 | Brand/NAP tutarsızlığı | Entity sinyali | S | **P1** |
| B3 | Karar tam metin (duplicate) | Sıralama + hukuki risk | M (özet + iç link) | **P1** |
| B6 | Cluster A×C alt sayfaları | En yüksek niyetli trafik | M-L | **P1** |
| B10 | Karar metadata zayıf | CTR + indeksleme kalitesi | S | **P1** |
| B7 | Blog/içerik hub | Otorite, E-E-A-T | L (süregelen) | **P2** |
| B8 | Title uzunluğu | CTR/kesilme | XS | **P2** |
| B9 | Sitemap lastmod | Crawl güveni | XS | **P2** |
| B11 | AI crawler engeli | AI arama görünürlüğü | XS (karar) | **P2** |
| B12 | Stale strateji belgesi | İç tutarlılık | XS | **P2** |

---

## 3. İmplementasyon planı (90 gün)

### Faz 0 — Hızlı teknik düzeltmeler (1-2 gün, hepsi P0/P1 kod)

**0.1 Domain'i tek değere sabitle (B2).**
Tek kaynak (single source of truth) belirle: `NEXT_PUBLIC_SITE_URL=https://hukukcuyapayzekasi.com`.
- `next.config.js` ve `next.config.mjs`'te default'ları `hukukcuyapayzekasi.com` yap, `serverActions.allowedOrigins`'i prod domaini içerecek şekilde güncelle.
- Üretim env'inde `NEXT_PUBLIC_SITE_URL`'in set olduğunu doğrula (`.env`/deploy ortamı).
- Doğrulama: build sonrası `/sitemap.xml`, `/robots.txt`, ana sayfa `<link rel=canonical>` ve `og:url` aynı domaini göstermeli.

**0.2 Sitemap index ekle ve karar sitemap'lerini bağla (B1).**
- Bir sitemap index üret: `/sitemap.xml`'in (veya `/sitemap_index.xml`) hem statik hem `/karar/sitemap/0..9.xml`'i listelemesi sağlanmalı. Next.js'te en temiz yol: `app/sitemap.ts`'i index'e çevirip alt sitemap'lere referans vermek ya da elle bir `route.ts` ile XML sitemap index basmak.
- `robots.ts`'e karar sitemap index satırını ekle.
- Doğrulama: GSC > Sitemaps'e index'i gönder, "Discovered URLs" 10K'ya yaklaşmalı.

**0.3 Ana sayfaya FAQPage schema bas (B4).**
- `app/page.tsx`'te mevcut `faqs` dizisini `buildFaqJsonLd(faqs.map(...))` ile `<JsonLd>` olarak ekle.
- Doğrulama: Google Rich Results Test → FAQ valid.

**0.4 Brand adı + sosyal linkleri tek tipleştir (B5).**
- Tek marka adına karar ver (öneri: "Hukukçu Yapay Zekası" — domainle uyumlu) ve `SITE_NAME`, layout title, Organization name, sameAs'i hizala.
- `sameAs`'i gerçekten var olan/oluşturulacak profillere (X, LinkedIn) güncelle; yoksa geçici olarak çıkar.

**0.5 Karar metadata'sını iyileştir (B10).**
- Title'ı "Daire E./K. — Konu — Emsal Karar" kalıbına getir; description'ı ham usul metni yerine (varsa) topic_tags + AI özetinin ilk cümlesinden kur; sayfaya özel `og:image` (daire/konu ile `/api/og`).

### Faz 1 — Karar sayfası kalitesi & long-tail (Hafta 1-4, P1)

**1.1 Karar sayfasını "özet öncelikli" yapıya çevir (B3).**
- AI özetini **server-side** üret/önbellekle ve ilk HTML'de bas (tıklamaya bağlı bırakma). Sayfa yapısı: H1 (başlık) → 150-250 kelime özgün özet → anahtar hukuki kavramlar (topic_tags) → ilgili emsaller (iç link) → "Bu kararla dilekçe oluştur" CTA → (opsiyonel) katlanır tam metin.
- Tam metni indeksten ayrıştırmak için ya özet-öncelikli yap ya da tam metni `<details>` içinde tut; duplicate riskini özgün özet taşır.
- KVKK: `anonymization_check` zorunlu (mevcut kontrol korunmalı).

**1.2 Karar sayfalarına iç linkleme (B3).**
- Her karara "ilgili kararlar" bloğu (aynı daire/konu, vektör benzerliği) ekle → orphan sayfaları bağlar, crawl derinliğini azaltır, topical authority kurar.

**1.3 Aşamalı indeksleme (B1/B3 risk yönetimi).**
- Önce 500 yüksek kaliteli karar sayfasını aç; GSC'de indekslenme + kalite sinyali izle; sonra 5K'ya ölçekle. `SAYFA_SAYISI`'nı kademeli artır.

**1.4 Cluster A×C alt sayfaları — ilk 4 (B6).**
- `/ihtarname/kira-tahliye`, `/ihtarname/alacak`, `/ihtarname/iscilik-alacagi`, `/zamanasimi/cek` oluştur. Her biri: tek H1 (hedef sorgu başta), özgün giriş metni, ön-doldurulmuş araç, sayfa-içi SSS + FAQPage schema, ilgili 3-5 karara iç link.
- Bu route'ları `app/sitemap.ts`'e ekle.

### Faz 2 — İçerik & otorite (Hafta 5-12, P1/P2)

**2.1 Blog/rehber hub'ı kur (B7).** `/blog` route + Article schema (`buildArticleJsonLd` hazır). İlk 4 makale: "emsal karar nedir", "ihtarname nasıl çekilir", "icra takibi adım adım", "2026 yasal faiz rehberi". Her makale → ilgili araç CTA (makale→araç→kayıt hunisi). Yazar kutusu (hukukçu danışman — E-E-A-T).

**2.2 Cluster A×C'yi genişlet.** Kazanan kümelere göre `/zamanasimi/kira`, `/ihtarname/temerrut`, `/dilekce/itirazin-iptali` vb. ekle. GSC verisine göre kalibre et.

**2.3 Karar sayfalarını 5K'ya ölçekle.** İndekslenme oranı ≥%60 ise devam; düşükse kalite/iç link iyileştir.

**2.4 Backlink/otorite.** Faiz hesaplayıcı `embed` widget'ı (mevcut `/embed/faiz` var) hukuk bloglarına; baro/fakülte araç tanıtımı; dataset citation (10K karar) akademik kullanım; LinkedIn'de haftalık "emsal trend" (`/trend` kaynak).

### Faz 3 — Düşük öncelik & strateji kararı (sürekli, P2)

- **B8**: Ana sayfa title'ını ≤60 karaktere kısalt.
- **B9**: Statik sitemap `lastModified`'ı sabit/anlamlı tarihlere bağla (route başına son içerik değişikliği).
- **B11**: AI crawler kararını ver — büyüme için GPTBot/CCBot'a (en azından public araç/karar sayfalarına) izin değerlendirilmeli.
- **B12**: `SEO_STRATEJI.md`'yi domain + durum güncellemesiyle revize et veya bu belgeyi tek kaynak yap.

---

## 4. Ölçüm ve KPI

Faz 0 sonrası GSC + (tercihen) Ahrefs/SEMrush TR ile kalibre et.

| Metrik | 30 gün | 90 gün |
|---|---|---|
| Sitemap'te keşfedilen URL | 5.000+ | 10.000+ |
| İndekslenen sayfa (GSC) | 500+ | 3.000+ |
| GSC tıklama/ay | 300 | 2.000 |
| Karar sayfası "indexed & ranking" oranı | %40 | %60 |
| Araç sayfası → kayıt dönüşümü | %2 | %3 |

Aylık rutin: GSC Coverage (404/soft-404), karar sayfası indeksleme oranı, top-20 sorgu CTR (düşükse title/description revizyonu), duplicate/canonical uyarıları.

---

## 5. Doğrulama kontrol listesi (Faz 0 sonrası)

- [ ] `/robots.txt` ve `/sitemap.xml` aynı (doğru) domaini gösteriyor.
- [ ] Sitemap index `/karar/sitemap/0..9.xml`'i listeliyor; GSC bunları okuyor.
- [ ] Google Rich Results Test: ana sayfa FAQPage geçerli; karar sayfası Article geçerli.
- [ ] Ana sayfa canonical, `og:url`, JSON-LD `url` üçü de tek domain.
- [ ] Karar sayfası ilk HTML'inde özgün özet metni mevcut (JS kapalı testi).
- [ ] Brand adı ve `sameAs` tüm JSON-LD'lerde tutarlı.

---

## Kaynaklar (kod referansları)

- `web/lib/seo.ts` — metadata, JSON-LD üreticileri
- `web/app/layout.tsx` — global metadata + LegalService JSON-LD
- `web/app/page.tsx` — ana sayfa (FAQ var, schema yok)
- `web/app/robots.ts` — robots + tek sitemap referansı
- `web/app/sitemap.ts` — 16 statik route
- `web/app/karar/sitemap.ts` — karar sitemap (keşfedilemiyor)
- `web/app/karar/[id]/page.tsx` — karar detay (tam metin)
- `web/next.config.js` / `next.config.mjs` — domain çatalı
- `SEO_STRATEJI.md` (2026-06-09) — önceki strateji
