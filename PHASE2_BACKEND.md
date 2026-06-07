# Faz 2 Backend — iyzico Billing + UYAP Yönetimi

## Bu turda eklenen 7 modül

### Billing
1. **`infra/db/05_migration_003.sql`** — `subscriptions`, `payments`, `webhook_events` tabloları + UYAP iyileştirmeler
2. **`services/billing.py`** — iyzico v2 SDK wrapper (HMAC imzalama, subscription checkout, cancel, retrieve)
3. **`api/routers/billing.py`** — 6 endpoint:
   - `GET /api/billing/plans` — Plan listesi
   - `POST /api/billing/checkout` — Subscription checkout başlat → iyzico ödeme URL'i
   - `POST /api/billing/callback` — Ödeme sonrası dönüş, subscription aktive
   - `GET /api/billing/current` — Mevcut subscription
   - `GET /api/billing/invoices` — Geçmiş ödemeler
   - `POST /api/billing/cancel` — İptal (period sonunda)
   - `POST /api/billing/webhook` — iyzico async events

### UYAP / Tenant Documents
4. **`services/encryption.py`** — Envelope encryption (master key + per-tenant HKDF DEK + AES-GCM)
5. **`services/pii_redaction.py`** — TC kimlik, IBAN, telefon, email, plaka maskele/unmask + audit
6. **`services/tenant_storage.py`** — Per-tenant şifreli dosya depo (local FS, S3'e hazır)
7. **`services/tenant_rag.py`** — Per-tenant Chroma collection — kendi dosyalarımda RAG
8. **`services/uyap_parser.py`** — PDF/DOCX/TXT parse + metadata çıkarımı (esas no, karar no, mahkeme, tarih) + doc_type tahmin
9. **`api/routers/uyap.py`** — 7 endpoint:
   - `POST /api/uyap/upload` — Şifreli dosya yükle + parse + index
   - `GET /api/uyap/` — Dosya listesi (filter: folder_id)
   - `GET /api/uyap/{doc_id}` — Tek doküman
   - `DELETE /api/uyap/{doc_id}` — Sil (storage + RAG)
   - `POST /api/uyap/sorgu` — **AI sorgu** (kendi dosyalarımda + opsiyonel emsallerde)
   - `GET /api/uyap/sorgu/gecmis` — Geçmiş sorgular

## KVKK uyum noktaları (kritik)

✅ **Şifreleme:** AES-256-GCM per-tenant key (envelope)
✅ **PII redaction:** LLM'e gönderilen tüm metinler maskelenir
✅ **Audit log:** Her upload/delete/sorgu kayıt altında
✅ **Soft delete (Faz 1):** Hesap silince 30 gün sonra hard delete
✅ **Cryptographic deletion:** Tenant key silindiğinde veri matematiksel olarak çözülemez
✅ **Per-tenant izolasyon:** RLS + ayrı Chroma collection + ayrı storage dizini
✅ **Quota enforcement:** Plan tier'ına göre dosya/sorgu kotası

## ENV variables — yeni

```bash
# iyzico
IYZICO_API_KEY=sandbox-...
IYZICO_SECRET_KEY=sandbox-...
IYZICO_BASE_URL=https://sandbox-api.iyzipay.com   # prod: https://api.iyzipay.com

# iyzico subscription product/plan referansları
# (iyzico panelinde oluştur, referans kodu buraya gir)
IYZICO_PLAN_PRO_SOLO=...
IYZICO_PLAN_PRO_UYAP=...
IYZICO_PLAN_TEAM=...
IYZICO_PLAN_TEAM_UYAP=...

# Encryption
MASTER_ENCRYPTION_KEY=<openssl rand -base64 32>

# Storage
TENANT_STORAGE_ROOT=data/tenant_storage
TENANT_CHROMA_DIR=data/tenant_chroma
```

## iyzico panel kurulumu (sen yapacaksın)

1. <https://merchant.iyzipay.com> hesap (sandbox)
2. Subscription → Products → 4 ürün oluştur:
   - "Pro Solo" (productCode: pro-solo)
   - "Pro + UYAP" (productCode: pro-solo-uyap)
   - "Team" (productCode: team)
   - "Team + UYAP" (productCode: team-uyap)
3. Her ürün için "Pricing Plan" → aylık → fiyat → "RECURRING"
4. Pricing plan referans kodlarını ENV'e yaz

## Test akışı (production gibi)

```bash
# 1. DB migration
psql $DATABASE_URL -f infra/db/05_migration_003.sql

# 2. Backend'i kaldır
uvicorn api.main:app --reload --port 8000

# 3. Health check
curl http://localhost:8000/api/health

# 4. Test user için tenant'ı Pro+UYAP'a yükselt (manuel DB):
psql $DATABASE_URL -c "UPDATE tenants SET plan_tier = 'pro_solo_uyap',
  max_uyap_documents = 50, max_monthly_queries = 200 WHERE slug LIKE 'solo-%';"

# 5. UYAP dosya yükle (Swagger /api/docs üzerinden)
# POST /api/uyap/upload + file + tur=dilekce

# 6. AI sorgu test
curl -X POST http://localhost:8000/api/uyap/sorgu \
  -H "Authorization: Bearer <jwt>" \
  -d '{"query": "Bu dosyamda hangi haciz konusu var?", "k": 5}'
```

## Hâlâ yapılacaklar — Faz 2 son etapları

- [ ] **Frontend `/app/dosyalar`** — Upload UI, dosya listesi, klasör (sonraki tur)
- [ ] **Frontend `/app/dosya/[id]`** — Doküman detay sayfası (sonraki tur)
- [ ] **Frontend `/app/sorgu`** — AI sorgu sayfası (sonraki tur)
- [ ] **Frontend abonelik checkout** — `/app/ayarlar/abonelik` butonunu billing'e bağla (sonraki tur)
- [ ] **iyzico panel kurulumu** — sen yapacaksın
- [ ] **MASTER_ENCRYPTION_KEY** — üret + Railway env'e ekle

## Faz 2 toplam ilerleme

```
Backend:    ████████████████░░░░  %80
Frontend:   ████████░░░░░░░░░░░░  %40
Billing:    ██████████░░░░░░░░░░  %50 (backend tamam, UI eksik)
UYAP:       ██████████░░░░░░░░░░  %50 (backend tamam, UI eksik)
```

Sonraki tur: tüm frontend UI sayfaları.
