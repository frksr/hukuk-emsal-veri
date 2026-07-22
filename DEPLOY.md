# Production Deploy Rehberi

İki ayrı servis: **FastAPI backend** + **Next.js frontend**.

## 1. Backend (FastAPI)

### Lokal test
```bash
cd hukuk-emsal-veri
pip install -r requirements.txt
cp .env.example .env
# .env'i düzenle: ANTHROPIC_API_KEY ve/veya GOOGLE_API_KEY ekle
uvicorn api.main:app --reload --port 8000
```

OpenAPI dokümantasyonu: <http://localhost:8000/api/docs>

### Production
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Önerilen hosting
- **Railway** veya **Fly.io** — Python + Chroma vector DB için ideal
- **Render** — kolay deploy
- **AWS ECS / Fargate** — büyük ölçek için

### Environment Variables
```
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
LLM_DEFAULT_PROVIDER=anthropic
ALLOWED_ORIGINS=https://hukukemsal.tr,https://www.hukukemsal.tr
```

### Data dependency
- `data/final/all_decisions.parquet` ve `data/chroma_db/` deploy ortamında olmalı
- Volume mount veya S3 sync ile sağla
- İlk request RAG modelini cold-start eder (~30sn)

## 2. Frontend (Next.js)

### Lokal test
```bash
cd web
npm install
cp .env.local.example .env.local
npm run dev
```

### Production build
```bash
npm run build
npm start
```

### Vercel deploy (önerilen)
1. GitHub'a push
2. Vercel'de "Import Project"
3. Root directory: `web/`
4. Environment variables:
   - `NEXT_PUBLIC_API_URL` = `https://api.hukukemsal.tr`
   - `NEXT_PUBLIC_SITE_URL` = `https://hukukemsal.tr`
5. Deploy

### Alternatif: Cloudflare Pages, Netlify

## 3. Domain & DNS

- Frontend: `hukukemsal.tr` → Vercel
- API: `api.hukukemsal.tr` → Railway/Fly.io
- SSL otomatik (Vercel, Cloudflare)

## 4. Production Öncesi Checklist

### Yasal
- [ ] Hukuki sorumluluk reddi (her sayfa)
- [ ] KVKK aydınlatma metni (gizlilik politikası)
- [ ] Kullanım şartları
- [ ] Çerez politikası + banner
- [ ] **Avukat incelemesi** (en az 5-10 örnek dilekçe çıktısı için)
- [ ] Yargıtay/Danıştay veri ticari kullanımı için danışmanlık

### Güvenlik
- [ ] Rate limiting (FastAPI içinde basit var; production'da Redis ile)
- [ ] CORS allowed origins kısıtla
- [ ] API key'ler secret manager'da (Vercel Env, AWS Secrets)
- [ ] SQL injection: parametrize SQL kullan (services/trend.py'de var)
- [ ] File upload limit: 10MB (var)
- [ ] PII redaction: anonymize_check her response'da

### Performance
- [ ] Chroma → Qdrant (1M+ chunk için)
- [ ] Redis cache (LLM yanıtları, sık sorgular)
- [ ] CDN (Cloudflare)
- [ ] Image optim (Next.js Image)
- [ ] Lighthouse 90+

### Monitoring
- [ ] Sentry (error tracking)
- [ ] Vercel Analytics
- [ ] Uptime monitoring (UptimeRobot)
- [ ] LLM usage tracking (Anthropic / Google dashboard)

### Cost Optimization
- [ ] LLM provider seçimi: gemini-3.1-flash-lite daha ucuz, Claude Sonnet daha kaliteli
- [ ] LLM response cache (aynı sorgu → cache'den)
- [ ] Streaming responses (uzun çıktılar için)
- [ ] Embedding model: e5-small (384-dim) daha hızlı

## 5. CI/CD

GitHub Actions:
- Lint + type check her PR'da
- Auto-deploy main branch (Vercel)
- Backend Docker image build + push (GHCR)

## 6. Sıralı Açılış Planı

1. **Hafta 1:** Kapalı beta — 5-10 avukat test eder
2. **Hafta 2:** Hukuki feedback'leri uygula, edge case'leri fix
3. **Hafta 3:** Public soft launch — landing page + en kararlı 4 özellik
4. **Hafta 4:** Tam launch, marketing
