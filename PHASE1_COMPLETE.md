# Faz 1 Tamamlandı — Auth + Multi-Tenancy Altyapısı

## Yeni eklenenler bu turda

### Backend
- `services/email.py` — Async SMTP wrapper, 3 template (verification, password reset, welcome)
- `api/audit.py` — KVKK için audit_log helper
- `api/routers/auth_actions.py` — `/forgot-password`, `/reset-password`, `/verify-email`, `/resend-verification`, `/change-password`
- `api/routers/me.py` — Genişletildi: profil güncelleme, kullanım istatistikleri (tier+limit dahil), tenant listesi, geçmiş aramalar, favorite toggle, hesap silme (KVKK)
- `api/routers/arama.py` — Tier-based rate limit + giriş yapmışsa geçmişe kaydet
- `api/main.py` — auth_actions router kaydedildi

### Frontend
- `web/app/api/proxy/[...path]/route.ts` — Next.js → FastAPI güvenli proxy (NextAuth JWT inject)
- `web/app/sifre-sifirla/` — Şifre sıfırlama (forgot + reset, tek sayfa)
- `web/app/giris/dogrulama/` — E-posta doğrulama landing
- `web/app/app/ayarlar/` — 4 sekme:
  - **Profil** (ad, e-posta verification status, marketing consent)
  - **Güvenlik** (şifre değiştir)
  - **Abonelik** (6 plan kartı, iyzico checkout için hazır)
  - **KVKK & Veriler** (veri indirme + hesap silme)

### Database
- `infra/db/04_migration_002.sql` — `user_searches`'e is_favorite, tags, title kolonları

## ENV variables — production için

Backend (.env):
```
DATABASE_URL=postgresql://...
NEXTAUTH_SECRET=<openssl rand -base64 32>

# SMTP (Resend veya SendGrid önerilir)
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USER=resend
SMTP_PASS=re_xxxxx
SMTP_FROM=noreply@hukukemsal.tr
SMTP_FROM_NAME=Hukuk Emsal

# Önceki env'ler
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
ALLOWED_ORIGINS=https://hukukemsal.tr,https://www.hukukemsal.tr
```

Frontend (web/.env.local):
```
NEXTAUTH_URL=https://hukukemsal.tr
NEXTAUTH_SECRET=<aynı backend ile>
DATABASE_URL=postgresql://...   # NextAuth Postgres adapter için
NEXT_PUBLIC_API_URL=https://api.hukukemsal.tr
NEXT_PUBLIC_SITE_URL=https://hukukemsal.tr
```

## Migration uygulama

```bash
psql $DATABASE_URL -f infra/db/01_init.sql
psql $DATABASE_URL -f infra/db/02_rls.sql
psql $DATABASE_URL -f infra/db/03_seed.sql
psql $DATABASE_URL -f infra/db/04_migration_002.sql
```

## Test senaryoları

1. **Kayıt + welcome email:**
   - `/kayit` → form doldur → kayıt başarılı → welcome email (dev: konsola yazar)

2. **E-posta doğrulama:**
   - `/app/ayarlar` → "Doğrulama e-postası gönder" → email linkini tıkla → `/giris/dogrulama?token=...` → ok

3. **Şifre sıfırlama:**
   - `/giris` → "Şifremi unuttum" → email → link → `/sifre-sifirla?token=...` → yeni şifre → redirect `/giris`

4. **Şifre değiştir (oturum içi):**
   - `/app/ayarlar/guvenlik` → mevcut + yeni → güncellenir

5. **Veri indirme:**
   - `/app/ayarlar/kvkk` → "Verilerimi İndir" → JSON download

6. **Hesap silme:**
   - `/app/ayarlar/kvkk` → "Hesabı Sil" → onay → pasif + signOut → ana sayfaya yönlen

7. **Rate limit:**
   - Anonim olarak 21. emsal araması → 429 + "Günlük limit doldu" mesajı
   - Hesap aç → limit 40'a çıkar

8. **Geçmiş kaydı:**
   - Giriş yap → arama yap → `/app/gecmis` (henüz sayfa yok ama `/api/me/searches` döner)

## Faz 1 son sayısal özet

- 24 yeni dosya
- 5 ana yeni özellik (email/password/profile/billing-ready/KVKK-rights)
- 11 yeni endpoint
- Tüm KVKK gereklilikleri minimum karşılanıyor: aydınlatma, açık rıza, veri taşınabilirliği (export), silme hakkı (delete), düzeltme hakkı (profile edit), audit log

## Faz 1'de hâlâ eksik (Faz 2'ye taşındı)

- iyzico billing entegrasyonu (checkout + webhook)
- Tenant invite flow (Team plan için)
- UYAP manuel upload modülü
- Per-tenant Qdrant namespace
- PII redaction katmanı
- Geçmiş aramalar UI sayfası (`/app/gecmis`)

## Sonraki adımlar (Faz 2 başlangıç)

1. iyzico developer hesabı + test credentials
2. `services/billing.py` — subscription + checkout intent + webhook handler
3. `api/routers/billing.py` — `/api/billing/checkout`, `/api/billing/webhook`
4. `web/app/app/ayarlar/abonelik/page.tsx` aktive (mevcut sadece UI, checkout entegrasyonu eksik)
5. UYAP upload — Mini Vault başlangıç
