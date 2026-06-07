# Hukuk Emsal — Project Status

**Son güncelleme:** 2026-05-14

## Sistem mimarisi

```
┌──────────────────────────────────────────────────┐
│  Next.js 14 (App Router) — web/                  │
│  · 10 işlevsel sayfa + 3 yasal sayfa             │
│  · SEO (metadata + JSON-LD + sitemap + robots)   │
│  · TypeScript + Tailwind + shadcn/ui pattern     │
│  · TanStack Query + Recharts                     │
└─────────────────┬────────────────────────────────┘
                  │ HTTP/JSON
                  ▼
┌──────────────────────────────────────────────────┐
│  FastAPI — api/                                  │
│  · 10 router · OpenAPI auto-doc                  │
│  · Rate limit + CORS + gzip + global error       │
│  · Pydantic v2 type-safe I/O                     │
└─────────────────┬────────────────────────────────┘
                  │
   ┌──────────────┼──────────────┐
   ▼              ▼              ▼
┌───────┐  ┌──────────┐  ┌──────────────┐
│ Chroma│  │ DuckDB + │  │ LLM Provider │
│ vector│  │ Parquet  │  │ Anthropic +  │
│       │  │          │  │ Gemini fallbk│
└───────┘  └──────────┘  └──────────────┘
```

## Kod tabanı

| Modül | Dosya sayısı | Hazır |
|---|---|---|
| Scrapers (Yargıtay, Danıştay, HUDOC, AYM) | 5 | ✅ |
| Pipelines (chunk, embed, export) | 3 | ✅ |
| Services (9 iş mantığı) | 9 | ✅ |
| LLM provider abstraction | 1 | ✅ |
| FastAPI backend | 14 (main+schemas+deps+10 router) | ✅ |
| Next.js frontend | 30+ (app + components + lib) | ✅ |
| Streamlit (internal dev) | 10+ | ✅ |
| Test suite | 3 (normalize, anonymize, queue) | ✅ |

## Frontend sayfaları

| Route | Özellik | Durum |
|---|---|---|
| `/` | Anasayfa (HERO + 10 özellik + FAQ) | ✅ |
| `/emsal-arama` | RAG arama + filtreler | ✅ |
| `/dilekce` | Emsal-bağlamlı dilekçe (LLM) | ✅ |
| `/karar-ozet` | Karar özetleyici (LLM) | ✅ |
| `/faiz-hesaplayici` | Faiz + İİK harçları | ✅ |
| `/zamanasimi` | TBK/TTK/AATUHK süre hesabı | ✅ |
| `/ihtarname` | TBK 117 ihtarname üretici (LLM) | ✅ |
| `/trend` | DuckDB + Recharts | ✅ |
| `/karsi-argument` | Karşı argüman (LLM) | ✅ |
| `/kvkk` | KVKK 30+ madde checklist | ✅ |
| `/sozlesme-analizi` | Sözleşme yükle + risk (LLM) | ✅ |
| `/yasal-uyari` | Yasal sayfa | ✅ |
| `/gizlilik` | KVKK aydınlatma | ✅ |
| `/kullanim-sartlari` | TOS | ✅ |
| `/not-found` | 404 | ✅ |

## Dataset

- **10,022 unique karar** Parquet'te
- **187,629 chunk** üretilebilir durumda
- **Chroma DB**: embedding hâlâ devam ediyor (CPU)
- **Disk**: ~220MB ham HTML + Parquet

| Kaynak | Karar sayısı |
|---|---|
| Yargıtay | 4,412 (12. HD ağırlıklı) |
| Danıştay | 3,807 |
| HUDOC (AİHM) | 1,803 |

## SEO Hazırlığı

- ✅ Her sayfada unique `<title>` (40-60 char) + `<meta description>` (150-160 char)
- ✅ JSON-LD: WebSite, Organization, BreadcrumbList, FAQPage
- ✅ `sitemap.xml` (App Router native)
- ✅ `robots.txt` (App Router native)
- ✅ Open Graph + Twitter Card
- ✅ Canonical URL'ler
- ✅ Türkçe locale (`lang="tr"`, `locale: tr_TR`)
- ✅ H tag hiyerarşisi (H1 → H2 → H3)
- ✅ Mobile-first responsive
- ✅ Performance hints (font display swap, image lazy)

## Production Checklist (ileride)

### Yapılması gerekenler
- [ ] API key'leri `.env`'e ekle (kullanıcı yapacak)
- [ ] Tam embedding (187K chunk) çalıştır (gece)
- [ ] Backend deploy (Railway/Fly.io)
- [ ] Frontend deploy (Vercel)
- [ ] Domain + DNS (hukukemsal.tr)
- [ ] **Hukuki inceleme** (örnek dilekçe çıktıları)
- [ ] KVKK aydınlatma metni hukukçu kontrolü
- [ ] Çerez banner (CookieBot vb.)
- [ ] Sentry error tracking
- [ ] Vercel Analytics

### Optimizasyonlar (sonraki sprint)
- [ ] Redis cache (LLM yanıtları + sık sorgular)
- [ ] Chroma → Qdrant (1M+ chunk için)
- [ ] LLM response streaming
- [ ] Image optim (anasayfa OG image)
- [ ] Multi-language (EN, AR — daha sonra)

## Çalıştırma

### Backend
```bash
cd C:\Users\mnara\OneDrive\Desktop\project\ai-projects\hukuk-emsal-veri
pip install -r requirements.txt
copy .env.example .env  # düzenle: API key'leri ekle
uvicorn api.main:app --reload --port 8000
```
OpenAPI: <http://localhost:8000/api/docs>

### Frontend
```bash
cd web
npm install
copy .env.local.example .env.local
npm run dev
```
UI: <http://localhost:3000>

## Bilinen sınırlar

1. **Yargıtay tam arşivi (386K karar)** — captcha sebebiyle 2700 kayıtta sınırlı. Captcha çözüm servisi (2captcha) entegrasyonu gerekli.
2. **Danıştay search** — keyword başına 500-700 kayıttan sonra rate-limit. Night loop ile aşamalı toplama yapılıyor.
3. **Embedding tam değil** — 187K chunk'ın hepsi henüz Chroma'da değil. Gece koşusu devam.
4. **API key bağımlılığı** — LLM özellikleri (dilekçe, özet, karşı argüman, ihtarname, sözleşme) `.env`'de key olmadan çalışmaz.
