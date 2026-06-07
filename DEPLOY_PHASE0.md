# Faz 0 — Public Ürünü Canlıya Çıkar

**Hedef:** `hukukemsal.tr` domainine SEO-ready public ürünü yayınla. SEO trafiği başlasın.
**Tahmin süre:** 1-2 gün aktif iş, 2-3 gün DNS propagation.
**Maliyet:** ~₺500-1500/ay başlangıç.

---

## 1. Hesap & Servis Açılışları

Sırayla aç:

### a) Domain
- **Sağlayıcı:** GoDaddy / IsimTescil / Natro
- Önerilen: `hukukemsal.tr` veya `hukukemsal.com.tr` (yedek: `hukukemsalkarar.tr`)
- Maliyet: ~₺200-400/yıl

### b) Vercel (Frontend hosting)
- URL: <https://vercel.com>
- Hobby planı **ücretsiz** başlangıç için yeter
- GitHub hesabınla bağla (sonra repo bağlayacağız)

### c) Railway (Backend hosting)
- URL: <https://railway.app>
- "Hobby" planı $5/ay (~₺170)
- PostgreSQL dahil
- Alternatif: Fly.io (benzer, biraz daha karmaşık)

### d) Cloudflare (CDN + DNS)
- URL: <https://cloudflare.com>
- Ücretsiz plan yeterli
- DNS + DDoS koruma + SSL

### e) Sentry (Error tracking)
- URL: <https://sentry.io>
- Developer planı ücretsiz (5K event/ay)
- Hem frontend hem backend kuracağız

### f) LLM API keys (zaten elinde olmalı)
- Anthropic: <https://console.anthropic.com>
- Google AI Studio: <https://aistudio.google.com>
- ✅ Production için **billing limit** koy (örn $50/ay Anthropic, $30/ay Google)

---

## 2. GitHub Repo

Mevcut projeyi GitHub'a yükle:

```bash
cd C:\Users\mnara\OneDrive\Desktop\project\ai-projects\hukuk-emsal-veri

# Eğer git init yapmadıysan:
git init
git add .
git commit -m "Initial commit"

# GitHub'da yeni private repo aç: hukuk-emsal-veri
# Sonra:
git remote add origin https://github.com/SENIN_KULLANICI/hukuk-emsal-veri.git
git branch -M main
git push -u origin main
```

**ÖNEMLİ:** `.env` dosyası `.gitignore`'da olmalı. Kontrol:

```bash
cat .gitignore | findstr ".env"
```

Yoksa ekle:
```
.env
.env.local
data/raw/
data/chroma_db/
data/queue.db
web/node_modules/
web/.next/
__pycache__/
```

---

## 3. Backend Deploy (Railway)

### a) Railway projesi
1. Railway'de "New Project" → "Deploy from GitHub repo"
2. Repo'yu seç: `hukuk-emsal-veri`
3. Railway otomatik olarak `requirements.txt` görür, Python build yapar

### b) Dockerfile (Railway'i hızlandırır)

Sana hazırlıyorum, root'a `Dockerfile` ekleyeceksin:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code
COPY api/ ./api/
COPY services/ ./services/
COPY llm/ ./llm/
COPY common/ ./common/
COPY data/final/all_decisions.parquet ./data/final/all_decisions.parquet
COPY data/chroma_db ./data/chroma_db

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### c) Environment Variables (Railway dashboard)

Railway → Project → Variables:

```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
LLM_DEFAULT_PROVIDER=anthropic
ALLOWED_ORIGINS=https://hukukemsal.tr,https://www.hukukemsal.tr
DEBUG=false
```

### d) Deploy
- Railway otomatik build başlatır
- ~5-10 dakika
- Logs'tan "Application startup complete" görmeli
- Public URL: örn `https://hukuk-emsal-veri-production.up.railway.app`

### e) Custom domain
- Railway → Settings → Domains → "Generate" veya custom
- `api.hukukemsal.tr` ekle
- CNAME kaydını DNS'e gir (Cloudflare'de)

---

## 4. Frontend Deploy (Vercel)

### a) Vercel projesi
1. Vercel → "New Project" → GitHub repo seç
2. **Root Directory:** `web/`  ← KRİTİK
3. Framework: Next.js (otomatik algılar)
4. Build command: `npm run build` (default)
5. Output: `.next` (default)

### b) Environment Variables (Vercel dashboard)

Vercel → Project → Settings → Environment Variables:

```
NEXT_PUBLIC_API_URL=https://api.hukukemsal.tr
NEXT_PUBLIC_SITE_URL=https://hukukemsal.tr
```

### c) Deploy
- Vercel otomatik build
- ~3-5 dakika
- Public URL: `hukuk-emsal-veri.vercel.app`

### d) Custom domain
- Vercel → Settings → Domains
- `hukukemsal.tr` ve `www.hukukemsal.tr` ekle
- DNS kayıtlarını Cloudflare'de gir:
  - A: `hukukemsal.tr` → 76.76.21.21
  - CNAME: `www` → cname.vercel-dns.com

---

## 5. Cloudflare DNS Ayarları

Cloudflare → Domain → DNS:

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | @ | 76.76.21.21 (Vercel) | ✅ Proxied |
| CNAME | www | cname.vercel-dns.com | ✅ Proxied |
| CNAME | api | xxx.up.railway.app | ⚠️ DNS only (Railway için) |

SSL: Cloudflare → SSL/TLS → "Full (strict)"

---

## 6. Sentry Kurulum

### Backend (FastAPI)

```bash
pip install sentry-sdk[fastapi]
```

`api/main.py` başına ekle (henüz yapmadıysan):

```python
import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if dsn := os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("ENV", "production"),
    )
```

Railway env'e ekle: `SENTRY_DSN=https://...@sentry.io/...`

### Frontend (Next.js)

```bash
cd web
npm install --save @sentry/nextjs
npx @sentry/wizard@latest -i nextjs
```

Wizard senin için config dosyalarını yazar. Sonra Vercel env'e:
`NEXT_PUBLIC_SENTRY_DSN=https://...@sentry.io/...`

---

## 7. Deploy Sonrası Test

Şu URL'leri tek tek test et:

- ✅ <https://hukukemsal.tr> → Anasayfa açılıyor mu
- ✅ <https://api.hukukemsal.tr/api/health> → JSON dönüyor mu
- ✅ <https://api.hukukemsal.tr/api/docs> → Swagger açılıyor mu
- ✅ <https://hukukemsal.tr/emsal-arama> → Sorgu yap, sonuç dönüyor mu
- ✅ <https://hukukemsal.tr/dilekce> → Form çalışıyor mu (LLM key gerek)
- ✅ <https://hukukemsal.tr/sitemap.xml> → Sitemap üretiliyor mu
- ✅ <https://hukukemsal.tr/robots.txt> → Robots üretiliyor mu

---

## 8. Google Search Console & Analytics

### Search Console
1. <https://search.google.com/search-console>
2. "URL prefix" olarak `https://hukukemsal.tr` ekle
3. Verification: HTML meta tag → `web/app/layout.tsx`'a ekle
4. Sitemap submit: `/sitemap.xml`

### Analytics (Plausible önerisi, KVKK uyumlu)
- <https://plausible.io> — cookie-less, KVKK uyumlu, ~$9/ay
- Alternatif: Vercel Analytics (Vercel'in kendi)

---

## 9. KVKK Çerez Banner

Cookie consent kütüphane:
```bash
cd web
npm install vanilla-cookieconsent
```

Veya hizmet olarak:
- <https://cookiebot.com> — €15/ay
- <https://termly.io> — $10/ay

İlk sürüm için **Plausible** seçersen analitik cookie yok = banner basit olabilir.

---

## 10. İlk Production Kontrolü

Tüm bunlar bitince:

1. **Performance test:** <https://pagespeed.web.dev>
   - Hedef: Mobile 85+, Desktop 95+
2. **SEO check:** <https://www.seoptimer.com>
   - Hedef: A grade
3. **Security:** <https://securityheaders.com>
   - Hedef: A
4. **SSL:** <https://www.ssllabs.com/ssltest/>
   - Hedef: A+

---

## Sorunlarla Karşılaşırsan

- **Railway build hatası:** Logs'a bak. `requirements.txt`'te eksik paket olabilir.
- **CORS hatası:** Backend env'de `ALLOWED_ORIGINS` doğru mu?
- **API çağrısı 502:** Backend ayakta mı? Railway → Logs.
- **DNS yayılmadı:** 24 saat bekle, `dnschecker.org` ile global durumu gör.
- **Chroma yüklenemiyor:** Dockerfile'da `data/chroma_db` kopyalandı mı?

---

## Sen Bunu Yaparken Ben Ne Yapıyorum

Paralel olarak Faz 1'i geliştiriyorum:
- PostgreSQL schema (users, tenants, sessions, RLS policies)
- NextAuth.js setup + sign-in/sign-up sayfaları
- Backend JWT middleware + tenant context
- Tier bazlı rate limit
- Hesabım dashboard sayfası

**2 gün sonra birleştirip ortak test edeceğiz.**

İlk takıldığın yerde söyle, hızlıca çözeriz.
