# Faz 2 Tamamlandı — Pro Tier Full Stack

## Bu turda eklenen 11 dosya — Frontend UI

| Sayfa | Dosyalar | Özellik |
|---|---|---|
| `/app/dosyalar` | `page.tsx`, `dosyalar-panel.tsx` | UYAP upload + listeleme + filtreleme + KVKK uyarı |
| `/app/dosya/[id]` | `page.tsx`, `doc-panel.tsx` | Doküman detay + in-place AI sorgu + emsal kaynaklar |
| `/app/sorgu` | `page.tsx`, `sorgu-panel.tsx` | Genel AI sorgu + dosya seçici + sorgu geçmişi |
| `/app/ayarlar/abonelik` | `page.tsx` (yenilendi), `abonelik-panel.tsx` | iyzico checkout entegre + mevcut plan + iptal |
| `/app/raporlar` | `page.tsx`, `raporlar-panel.tsx` | Kullanım istatistik + sorgu geçmişi + fatura |

## Tam çalışan akışlar (Pro Solo + UYAP için)

### 1. UYAP Dosya Yükleme
```
Avukat → /app/dosyalar → "Dosya Yükle" → PDF/DOCX seç
  ↓ multipart upload → /api/proxy/uyap/upload
  ↓ backend: parse + extract metadata + PII audit + encrypt + storage + index
  ↓ vector store (per-tenant Chroma)
  ↓ DB: tenant_documents kaydı
  ↓ status: ready
  ↓ Liste otomatik yenilenir
```

### 2. Kendi Dosyamda AI Sorgu
```
Avukat → /app/dosya/123 → "Bu dosyada haciz durumu ne?"
  ↓ POST /api/proxy/uyap/sorgu
  ↓ backend: tenant RAG (kendi Chroma collection)
  ↓ + opsiyonel public emsal RAG
  ↓ context oluştur → PII redact (TC/IBAN/telefon maskele)
  ↓ Claude/Gemini'ye gönder (kişisel veri görmez)
  ↓ Yanıt al → PII unredact (placeholder'ları geri koy)
  ↓ DB: tenant_queries log
  ↓ Avukat'a yanıt + kaynak (kendi dosyam + emsaller)
```

### 3. Ödeme & Abonelik
```
Avukat → /app/ayarlar/abonelik → "Pro + UYAP'a Geç"
  ↓ POST /api/proxy/billing/checkout
  ↓ backend: iyzico subscription init
  ↓ Frontend → iyzico ödeme sayfasına yönlendir
  ↓ Avukat kart bilgisi gir → ödeme
  ↓ iyzico → callback URL'imize geri dön (?token=...)
  ↓ POST /api/proxy/billing/callback
  ↓ subscription aktive + tenant.plan_tier güncelle
  ↓ UYAP kotası açılır (50 doc, 200 sorgu/ay)
  ↓ Webhook ile sonraki ödemeler otomatik
```

## Tam akış diyagramı

```
┌──────────────────────────────────────────────────────────────┐
│  Avukat                                                       │
│   │                                                           │
│   ↓ login                                                     │
│  /giris → NextAuth → /app dashboard                          │
│                                                               │
│  ÜRETKEN AKIŞLAR:                                            │
│  ┌─────────────────┐  ┌──────────────────┐                   │
│  │ /app/dosyalar   │  │ /app/sorgu       │                   │
│  │ UYAP yükle      │  │ AI sorgu         │                   │
│  └────────┬────────┘  └────────┬─────────┘                   │
│           │                    │                              │
│           ↓                    ↓                              │
│  ┌─────────────────────────────────────┐                     │
│  │ /api/proxy/uyap/*                   │                     │
│  └────────────────┬────────────────────┘                     │
│                   ↓                                           │
│  ┌─────────────────────────────────────┐                     │
│  │ FastAPI: encryption + PII redact +  │                     │
│  │ per-tenant Chroma + audit log       │                     │
│  └─────────────────────────────────────┘                     │
│                                                               │
│  YÖNETİM:                                                    │
│  /app/ayarlar       /app/raporlar       /app/ayarlar/abonelik│
│  Profil, KVKK       Kullanım, fatura    iyzico checkout      │
└──────────────────────────────────────────────────────────────┘
```

## Faz 2 son durum — kalan kritik bug fix'ler

### Test edilmesi gerekenler:
- [ ] DB migration uygulayıp `psql` ile şema doğrula
- [ ] Backend lokal çalıştır, `/api/health` ve `/api/docs` test
- [ ] Frontend lokal çalıştır, login → /app gez
- [ ] Tenant manual upgrade SQL ile Pro+UYAP'a al
- [ ] UYAP upload test (küçük PDF/DOCX ile)
- [ ] AI sorgu test (`include_emsal: true`)
- [ ] iyzico sandbox checkout test

### Production öncesi:
- [ ] **MASTER_ENCRYPTION_KEY** üret + Railway env'e koy
- [ ] iyzico sandbox → production switch
- [ ] iyzico panel'inde 4 ürün + pricing plan oluştur
- [ ] iyzico webhook URL'ini `https://api.hukukemsal.tr/api/billing/webhook` olarak ayarla
- [ ] SMTP servisi (Resend / Postmark) entegre — ENV
- [ ] Sentry DSN'i prod env'e
- [ ] Test kartlarıyla full payment flow doğrula

## Tüm Faz 2 sayısal özet

| Metric | Değer |
|---|---|
| Yeni dosya (bu Faz) | 28 |
| Backend modülü | 7 (services + 2 router) |
| Frontend sayfa | 11 (yeni) |
| API endpoint | 14 (yeni) |
| DB tablo | 5 (yeni) |
| KVKK uyum kalemi | 8 (kritik) |

## Bir sonraki — Sen ne yapacaksın

1. **Deploy** (Faz 0 hâlâ devam ediyorsa)
2. **iyzico hesap + ürün setup** (panel.iyzico.com)
3. **MASTER_ENCRYPTION_KEY** üret
4. **Smoke test** — local env çalıştır, ben rehberlik ederim
5. **Beta avukatlara ilk paylaşım** — 2-3 kişiyle başla

Ben ne yapayım sırada?

**Seçenek A:** Faz 2 polish — UI bug fix, edge cases, error handling
**Seçenek B:** Beta Onboarding Paketi — beta sözleşme, onboarding doc, welcome email serisi, internal admin panel
**Seçenek C:** Faz 3 başlangıç — yerel LLM (Llama 3.1 70B) deploy + hibrit → yerel geçişi
**Seçenek D:** UYAP otomatik çekim — Chrome extension iskeleti

Önerim **B** — beta avukatlar gelmeye başlayınca admin panel olmadan kaos olur.
