# Publisher API v1 — Boşluk Analizi ve Uygulama Planı

**Tarih:** 2026-07-12 · **Kapsam:** Blog paylaşım otomasyonu (Publisher API v1) şartnamesinin mevcut blog altyapısıyla karşılaştırması.

---

## 1. Genel Durum (Özet)

Mevcut sistem **tek dilli (TR), JWT + admin-panel tabanlı bir CMS**. Şartname ise **API-key + e-postayla tek-tık onay/red akışına dayalı, çok siteli ve iki dilli (TR/EN)** bir yayıncı sözleşmesi tanımlıyor. Yani temel yapı taşları (makale tablosu, SEO üretimi, görsel yükleme, SMTP, dinamik sitemap, JSON-LD) **mevcut ve yeniden kullanılabilir** durumda; ancak şartnamenin çekirdeği olan **onay akışı, token güvenliği, önizleme, çok dillilik ve üç siteye ortak sözleşme** henüz yok.

Kabaca: **altyapının ~%40'ı hazır, otomasyona özel katmanın (~%60) yeni yazılması gerekiyor.** İlk sitede ~1.5–2 gün, sonraki iki sitede kopyalama ile ~1 gün/site tahmini.

Bu repo yalnızca **tek siteyi** (`hukukcuyapayzekasi.com`) içeriyor. Şartnamedeki "üç site" için diğer iki sitenin kod tabanı ayrı; aynı sözleşme oralarda da uygulanmalı (bu analiz bu repoyu baz alır).

---

## 2. Mevcut Yapı — Ne Var?

| Bileşen | Dosya | Durum |
|---|---|---|
| Makale tablosu | `infra/db/20_blog_articles.sql` | ✅ id, slug, title, body, meta_*, keywords, faq, seo_score, status(draft/published), author, cover_image, published_at |
| İçerik API'si | `api/routers/icerik.py` | ✅ Public liste/makale + Admin CRUD, SEO üret, yayınla/taslak, görsel yükle |
| Kimlik doğrulama | `api/auth.py` (JWT, role=admin) | ✅ Ama API-key değil |
| Otomatik SEO | `services/seo_uret.py` | ✅ meta_title/description, keywords, FAQ, skor (LLM→heuristik fallback) |
| Görsel yükleme | `services/blog_storage.py` | ✅ GCS public bucket, `blog/` prefix — ama **multipart**, tek tek, base64 değil |
| E-posta | `services/email.py` | ✅ `send_email` + `_wrap` şablon + CTA buton — onay maili için ideal taban |
| Sitemap | `web/app/sitemap.ts` | ✅ Yayınlananları dinamik çeker — ama hreflang alternatifi yok |
| JSON-LD | `web/lib/seo.ts` | ✅ Article + FAQPage + Breadcrumb — ama `inLanguage: tr-TR` sabit |
| Frontend blog | `web/app/blog/**` | ✅ Liste + `[slug]` + markdown+görsel render (`![alt](url){pos}`) |

---

## 3. Boşluklar — Ne Eksik?

Şartname maddesi bazında karşılaştırma:

| # | Şartname gereği | Mevcut durum | Boşluk |
|---|---|---|---|
| A | `POST /api/publisher/drafts` | Yok (`/api/icerik/admin/makale` yakın ama farklı sözleşme) | **YENİ** |
| B | `GET /approve?draft_id&token` (tek-tık yayın) | Yok (admin panelden manuel yayın) | **YENİ** |
| C | `GET /reject?draft_id&token` | Yok | **YENİ** |
| D | `GET /drafts/{id}` (durum sorgu) | Yok | **YENİ** |
| E | `GET /health` | Yok | **YENİ (basit)** |
| F | **Bearer API-key** auth (env, constant-time, 401) | JWT/role=admin | **YENİ auth katmanı** |
| G | Token: ≥32 bayt, **tek kullanımlık**, 7 gün expiry, constant-time | Yok | **YENİ** |
| H | Taslak deposu: `group_id, lang, approve_token, reject_token, expires_at, status(pending/rejected/expired)...` | `status` yalnız draft/published; group_id/lang/token/expiry kolonları yok | **Şema genişletme** |
| I | **base64 görsel** kabulü + markdown `images/...` yolunu GCS URL'ine çevirme | Multipart tek görsel, yol çevirisi yok | **YENİ** |
| J | **Önizleme URL'i** (`noindex,nofollow`, tahmin edilemez yol) | Yok | **YENİ route (FE+BE)** |
| K | Onay maili (Önizleme + ✅ Onayla + ❌ Reddet + expiry) | E-posta altyapısı var, bu şablon yok | **YENİ şablon** |
| L | Onayda: eş dil sürümünü de yayınla (grup yayını) + hreflang eşleştir | Yok (tek dil) | **YENİ** |
| M | **Çok dillilik (tr/en)** + `hreflang_pair_slug` + hreflang etiketleri | Tümüyle TR; `lib/seo.ts` tr-TR sabit; `/en` route yok | **Büyük boşluk** |
| N | Idempotency: aynı `slug+lang` bekleyen taslağı üzerine yaz | Duplicate slug → 409 | **Davranış değişikliği** |
| O | `category` (cluster) + `tags` | Şemada yok | **Şema + FE** |
| P | FAQ formatı `{q,a}` | İç format `{soru,cevap}` | **Eşleme** |
| Q | Rate limit (~30/dk) + 15 MB gövde limiti | Görsel limiti 8 MB; publisher rate limit yok | **Konfig** |
| R | HTTPS zorunlu, key/token loglanmaz | Kısmen (genel) | **Sertleştirme** |
| S | Durum ucu → Claude IndexNow + LinkedIn adımını tetikler | IndexNow endpoint/anahtarı yok; LinkedIn otomasyonu yok | **YENİ (site + Claude tarafı)** |
| T | HTML başarı/hata sayfaları (onay/red/expired) | Yok | **YENİ** |
| U | `cover_image` zorunlu (1200×630) | Opsiyonel | **Doğrulama** |
| V | `requested_publish_at` (zamanlı yayın) | Yok | **Opsiyonel/sonra** |

---

## 4. Mimari Karar: İki Yaklaşım

**Yaklaşım 1 — `blog_articles` tablosunu genişlet (önerilen).**
Mevcut tabloya `group_id, lang, category, tags, approve_token, reject_token, token_expires_at, preview_id, hreflang_pair_slug, source` kolonları ekle; `status` CHECK'ini `pending/published/rejected/expired` içerecek şekilde güncelle. Tek tablo, tek gerçek kaynak; frontend zaten bu tablodan okuyor. Yayınlanınca ek taşımaya gerek kalmaz.

**Yaklaşım 2 — Ayrı `blog_drafts` tablosu.**
Taslaklar ayrı tabloda beklesin, onayda `blog_articles`'a kopyalansın. Daha temiz ayrım ama iki tablo senkronizasyonu ve kopya mantığı gerekir.

**Öneri: Yaklaşım 1.** Daha az kod, mevcut public okuma/sitemap otomatik çalışır.

---

## 5. Uygulama Planı (Fazlı)

### Faz 0 — Hazırlık (0.5 gün)
- Mimari kararı onayla (Yaklaşım 1).
- `PUBLISHER_API_KEY` üret (`openssl rand -hex 32`), env'e ekle (`.env`, Cloud Run secret). Anahtarın Claude config'ine güvenli iletimi.
- İkinci dil (EN) stratejisi netleştir: URL şeması (`/en/blog/<slug>` mi, ayrı domain mi), `lib/seo.ts` çok dilli hale getirme kararı.

### Faz 1 — Veri katmanı (0.5 gün)
- `blog_articles` şema migration'ı: yeni kolonlar + `status` CHECK genişletme + `(slug, lang)` unique + token/expiry index.
- FAQ `{q,a}` ↔ `{soru,cevap}` eşleme yardımcıları.

### Faz 2 — Publisher API (0.75 gün)
- `api/routers/publisher.py`: 5 endpoint, `/api/publisher` prefix.
- Bearer API-key doğrulama (constant-time, `hmac.compare_digest`), 401.
- `POST /drafts`: şema doğrulama (422), base64 görsel çözme + GCS'e yükleme + markdown yol çevirisi, idempotent upsert (slug+lang), token üretimi (`secrets.token_urlsafe(32)`), preview_id, onay maili, 201/200.
- `GET /approve` & `GET /reject`: token doğrula (ait mi/kullanılmış mı/süresi geçti mi), yayınla/reddet, grup eş-dil yayını + hreflang, tokenları geçersiz kıl, HTML sayfa. (Mail ön-tarama riskine karşı araya tek-butonlu onay sayfası — önerilir.)
- `GET /drafts/{id}`: durum + published_url.
- `GET /health`: 200.
- Rate limit + 15 MB gövde limiti + key/token log yasağı.

### Faz 3 — Önizleme + Frontend (0.5 gün)
- `web/app/preview/[id]/page.tsx`: `noindex,nofollow`, tahmin edilemez yol, taslağı gösterir.
- Onay maili HTML şablonu (`services/email.py`'ye `send_publish_approval_email`).
- `web/lib/seo.ts` + `sitemap.ts`: hreflang alternatifleri (tr/en), `inLanguage` dinamik.
- (Opsiyonel) `category`/`tags` gösterimi.

### Faz 4 — Test + Yayın-sonrası (0.5 gün)
- Şartname §8 kabul testleri (uçtan uca): health, POST→201+mail+önizleme(noindex), idempotency, onayla→canlı+sitemap+hreflang+ikinci tık "kullanılmış", reddet, 7 gün expiry simülasyonu, durum ucu.
- IndexNow: site tarafına IndexNow key + ping; Claude durum ucundan yayını görünce IndexNow + LinkedIn adımını tetikler.

### Faz 5 — Diğer iki site (~1 gün/site)
- Aynı sözleşmeyi diğer iki sitede uygula (framework farklıysa uyarlanır, sözleşme birebir aynı).

---

## 6. Riskler / Dikkat Noktaları

- **Çok dillilik en büyük iş.** Mevcut site baştan TR varsayımlı (`lib/seo.ts`, Article `inLanguage`, route yapısı). EN sürümü ciddi frontend işi; şartnamenin geri kalanından bağımsız planlanabilir. Eğer başlangıçta yalnız TR yayınlanacaksa `lang`/`group_id`/hreflang alanları şemaya konur ama EN frontend'i sonraya bırakılabilir.
- **Mail ön-tarama:** Bazı mail istemcileri GET linklerini önden açar → istem dışı yayın. Araya tek-butonlu onay sayfası koymak güçlü önerilir.
- **Güvenlik:** API-key ve tokenlar loglanmamalı; constant-time karşılaştırma; HTTPS zorunlu; preview yolu tahmin edilemez olmalı.
- **Görsel boyutu:** Publisher gövde limiti 15 MB; mevcut 8 MB/görsel limiti base64 çoklu görselde yetmeyebilir — publisher yolu için ayrı limit.
