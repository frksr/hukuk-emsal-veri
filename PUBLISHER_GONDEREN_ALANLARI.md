# Blog Gönderim Alanları — Publisher API v1 (Gönderen Tarafı)

Blog yazısını sisteme göndereceklerin dolduracağı alanlar. Yazı buradan
`POST /api/publisher/drafts` ile gönderilir; **taslak** olarak kaydedilir ve
admin'e onay maili gider. Onaylanınca `/blog/<slug>` adresinde yayınlanır.
**Tek dilli (Türkçe).**

## İstek

```
POST  https://<api-adresi>/api/publisher/drafts
Authorization: Bearer <PUBLISHER_API_KEY>
Content-Type: application/json
```

## Alanlar

`*` = zorunlu.

| Alan | Zorunlu | Tip | Açıklama |
|---|---|---|---|
| `title` | ✅ | string | Yazı başlığı (H1). |
| `body_markdown` | ✅ | string | Yazı gövdesi, Markdown. Desteklenen: `## H2`, `### H3`, `- liste`, `**kalın**`, `[metin](url)`, `> vurgu`, `![alt](images/dosya.png)`. |
| `meta_description` | ✅ | string | Arama sonucu açıklaması. **140–160 karakter** önerilir. |
| `cover_image` | ✅ | object | Kapak görseli (aşağıdaki görsel objesi). **1200×630** PNG/WebP. |
| `slug` | — | string | URL: `/blog/<slug>`. Boş bırakılırsa başlıktan otomatik üretilir (yalnız `a-z 0-9 -`). |
| `keyword` | — | string | Hedef anahtar kelime. |
| `excerpt` | — | string | Liste kartındaki 1–2 cümlelik özet. Boşsa meta_description kullanılır. |
| `category` | — | string | İçerik kümesi/cluster adı (örn. `ai-agent`). |
| `tags` | — | string[] | Etiketler, örn. `["ihale","yapay zeka"]`. |
| `faq` | — | array | SSS listesi: her öğe `{ "q": "...", "a": "..." }`. Sayfada + FAQPage schema'da kullanılır. |
| `images` | — | array | Gövde içi görseller (görsel objesi). `body_markdown` içinde `![alt](images/<filename>)` ile referanslanır; sistem yolu gerçek URL'e çevirir. |
| `author` | — | string | Yazar adı. Boşsa "Hukukçu Yapay Zekası Editör Ekibi". |
| `source` | — | string | Kaynak etiketi, örn. `claude-blog-automation`. |
| `sent_at` | — | string | ISO-8601 gönderim zamanı (bilgi amaçlı). |

### Görsel objesi (`cover_image` ve `images[]`)

| Alan | Zorunlu | Açıklama |
|---|---|---|
| `filename` | ✅ | Dosya adı, örn. `kapak.png`. Uzantı türü belirler (png/jpg/webp/gif/svg). |
| `data_base64` | ✅ | Dosyanın base64'ü. `data:image/png;base64,...` öneki olabilir de olmayabilir de. |
| `alt` | — | Erişilebilirlik/SEO alt metni. |

> **Boyut:** Tüm görsellerin toplamı **15 MB**'ı geçmemeli (aşarsa `413`).

## Örnek gövde

```json
{
  "title": "İhale Şartnamesi Analizi: Yapay Zeka ile Hızlı İnceleme",
  "slug": "ihale-sartnamesi-analizi-yapay-zeka",
  "meta_description": "İhale şartnamesini yapay zeka ile nasıl hızlı ve hatasız analiz edersiniz? Adım adım rehber, dikkat edilecek maddeler ve pratik ipuçları.",
  "keyword": "ihale şartnamesi analizi",
  "excerpt": "İhale şartnamelerini yapay zeka ile dakikalar içinde analiz etmenin yolu.",
  "category": "ai-agent",
  "tags": ["ihale", "yapay zeka"],
  "body_markdown": "## Giriş\n\nİhale şartnameleri...\n\n![Akış şeması](images/akis.png)\n\n### Adımlar\n\n- Belgeyi yükleyin\n- ...",
  "faq": [
    { "q": "İhale şartnamesi analizi nedir?", "a": "..." },
    { "q": "Ne kadar sürer?", "a": "..." }
  ],
  "cover_image": {
    "filename": "kapak.png",
    "alt": "İhale şartnamesi analizi kapak görseli",
    "data_base64": "<base64>"
  },
  "images": [
    { "filename": "akis.png", "alt": "Analiz akış şeması", "data_base64": "<base64>" }
  ],
  "author": "Hukukçu Yapay Zekası Editör Ekibi",
  "source": "claude-blog-automation",
  "sent_at": "2026-07-12T09:00:00+03:00"
}
```

## Yanıt

```json
// 201 Created (aynı slug'lı bekleyen taslak varsa üzerine yazılır → 200)
{
  "draft_id": "d0f1...uuid",
  "status": "pending",
  "preview_url": "https://site.com/preview/<rastgele>",
  "expires_at": "2026-07-19T09:00:05+00:00"
}
```

Onay maili admin adresine gider; **Önizleme**, **✅ Onayla**, **❌ Reddet**
butonları içerir. Onay linki tıklanınca bir onay sayfası açılır ve oradaki
"Yayınla" butonuyla yazı canlıya alınır (mail ön-taramasına karşı iki adımlı).
Onay/red bağlantıları **7 gün** geçerlidir.

## Hata kodları

`401` yanlış/eksik API anahtarı · `422` eksik zorunlu alan veya bozuk base64 ·
`409` bu slug zaten yayında · `413` görseller 15 MB'ı aştı · `429` çok sık istek.

## Durum sorgu (opsiyonel)

```
GET /api/publisher/drafts/{draft_id}     (Authorization: Bearer ...)
→ { "draft_id": "...", "status": "pending|published|rejected|expired",
    "published_url": "...", "published_at": "..." }
```
