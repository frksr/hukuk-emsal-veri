# Hukuk Emsal — Production Hazırlık Checklist

**Oluşturulma:** 2026-06-07
**Mevcut durum:** Beta'ya hazır · Production'a hazır DEĞİL
**Genel ilerleme:** ~%60

Sıralama önceliğe göre: önce **bloker'lar** (bunlar yapılmadan launch olamaz), sonra **lansman öncesi**, sonra **lansman sonrası iyileştirmeler**.

---

## 🔴 P0 — Bloker'lar (bunlar olmadan production olmaz)

### Ödeme
- [ ] iyzico sandbox → **production** key'lerine geç (`.env`: `IYZICO_API_KEY`, `IYZICO_SECRET_KEY`, `IYZICO_BASE_URL`)
- [ ] iyzico panelinde 4 ürün + pricing plan oluştur
- [ ] iyzico webhook URL'i prod'a ayarla: `https://api.hukukemsal.tr/api/billing/webhook`
- [ ] Gerçek test kartıyla uçtan uca ödeme + iptal + yenileme akışını doğrula

### Secret & ortam değişkenleri
- [ ] Production için **ayrı** `NEXTAUTH_SECRET` üret (local'dekini kullanma)
- [ ] Production için **ayrı** `MASTER_ENCRYPTION_KEY` üret + güvenli sakla (kaybı = tüm tenant verisi okunamaz)
- [ ] Tüm prod secret'ları Railway/Vercel env'lerine taşı, repoda tutma
- [ ] `ANTHROPIC_API_KEY` + `GOOGLE_API_KEY` prod hesaplarına geç (rate limit / fatura takibi)

### Config
- [ ] `ALLOWED_ORIGINS` env'ini prod domain'e set et (varsayılan localhost — frontend bağlanamaz)
- [ ] `DEBUG` env'inin prod'da kapalı olduğunu doğrula (hata detayı sızdırmasın)
- [ ] Gerçek SMTP entegre et (Resend / Postmark) — şu an local Mailpit, e-posta gitmiyor

### Hukuki (bir hukuk ürünü için kritik)
- [ ] LLM çıktılarının (dilekçe, ihtarname, özet, sözleşme analizi) hukukçu incelemesi
- [ ] KVKK aydınlatma metni hukukçu onayı
- [ ] Kullanım şartları + yasal uyarı (LLM çıktısı bağlayıcı değildir ibaresi) son kontrol

---

## 🟡 P1 — Lansman öncesi (launch haftası)

### Altyapı & deploy
- [ ] Backend deploy (Railway / Fly.io) — `/api/health` ve `/api/docs` ayakta
- [ ] Frontend deploy (Vercel)
- [ ] Domain + DNS (hukukemsal.tr) + propagation doğrula
- [ ] SSL sertifikası (Let's Encrypt / platform native)
- [ ] DB migration'ı prod Postgres'e uygula, şemayı `psql` ile doğrula

### Veri
- [ ] Tam embedding'i tamamla (187K chunk Chroma'da) — şu an kısmi
- [ ] `data/` klasörünü deploy dışında bırak (2.9GB; `chroma_db` + `final`'ı `.dockerignore`/`.gitignore`'a ekle)
- [ ] Chroma'yı kalıcı volume'a veya managed vektör DB'ye bağla (container restart'ta kaybolmasın)
- [ ] `data/queue - Kopya.db` ve diğer yedek/çöp dosyaları temizle

### Gözlemlenebilirlik
- [ ] Sentry DSN'i prod env'e ekle (backend + frontend)
- [ ] Uptime monitoring (UptimeRobot / Better Stack)
- [ ] Production log toplama

### Güvenlik
- [ ] Rate limit değerlerini prod için ayarla (slowapi)
- [ ] En azından OWASP Top 10 kontrolü (auth, injection, IDOR — özellikle tenant izolasyonu)
- [ ] Tenant izolasyonu testi: bir avukatın diğerinin dosyasına erişemediğini doğrula

### Test
- [ ] Smoke test (`scripts/smoke_test.py`) prod ortamında çalıştır
- [ ] UYAP upload testi (gerçek PDF/DOCX)
- [ ] AI sorgu testi (`include_emsal: true`) — PII redact/unredact doğru çalışıyor mu
- [ ] `TEST_PLAN.md`'deki tüm 🔴 + 🟡 testleri PASS

---

## 🟢 P2 — Lansman sonrası (ilk sprint)

- [ ] Backup stratejisi: `pg_dump` + restore testi
- [ ] Felaket kurtarma (DR) planı
- [ ] Çerez banner (CookieBot vb.)
- [ ] Vercel Analytics / Google Search Console doğrulama
- [ ] Redis cache (LLM yanıtları + sık sorgular)
- [ ] LLM response streaming
- [ ] CDN / static asset cache

---

## 🧪 Test kapsamı borcu (paralel yürüt)

Şu an sadece 3 birim test dosyası var (`normalize`, `anonymize`, `job_queue` — 20 test geçiyor). Kritik akışlar test edilmiyor:

- [ ] API endpoint entegrasyon testleri (auth, billing, uyap, sorgu)
- [ ] `services/encryption.py` + `pii_redaction.py` birim testleri (en hassas kod)
- [ ] `services/billing.py` iyzico akış testi (mock)
- [ ] RAG retrieval doğruluk testi (tenant_rag izolasyonu dahil)

---

## ⚠️ Bilinen sınırlar (launch'ı blokelemiyor ama bilinmeli)

1. **Yargıtay tam arşivi** — captcha sebebiyle sınırlı kayıt. 2captcha entegrasyonu gerekli.
2. **Danıştay search** — keyword başına rate-limit; night loop ile aşamalı toplama.
3. **LLM bağımlılığı** — API key'siz dilekçe/özet/argüman/ihtarname/sözleşme çalışmaz.

---

## Özet karar

| Aşama | Hazır mı? |
|---|---|
| **Beta (2-3 avukat)** | Evet — P0 ödeme + secret + hukuki onay tamamlanınca |
| **Public production** | Hayır — P0 + P1'in tamamı gerekli |

**Tavsiye edilen sıra:** P0 secret/config (1 gün) → P0 hukuki inceleme (paralel, dış bağımlı) → P1 deploy + monitoring → kapalı beta → P0 ödeme prod doğrulama → public launch.
