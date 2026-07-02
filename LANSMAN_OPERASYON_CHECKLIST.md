# Lansman Operasyon Checklist'i — Sahibin Yapacakları

Bu liste yalnızca **bir insanın yapabileceği** operasyonel adımları içerir
(hesap açma, panel ayarları, secret üretme, elle test). Teknik deploy adımları
için `infra/gcp/DEPLOY_GCP.md`, sorun giderme için `DUZELTME_RUNBOOK.md`,
yedekleme için `DR_RUNBOOK.md`.

> **Doküman notu:** `PRODUCTION_CHECKLIST.md` (2026-06-07) hâlâ geçerli bir üst
> çerçevedir ama bazı maddeleri bayattır: **Chroma referansları eski — RAG artık
> pgvector'da (Cloud SQL içinde)**, "Chroma'yı volume'a bağla" ve "Chroma→Qdrant"
> maddeleri geçersizdir. Bu dosyadaki adımlar günceldir; çelişki varsa bu dosya
> kazanır.

Domain varsayımı: `hukukcuyapayzekasi.com` (site) + `api.hukukcuyapayzekasi.com`
(API). Farklı domain kullanacaksan tüm adımlarda değiştir.

---

## 1. Prod secret'larını üret ve yerine koy

Local'de kullanılan hiçbir secret prod'a taşınmaz — hepsi yeniden üretilir.
Güvenli bir terminalde üret (komut geçmişine değer yazma; `openssl` çıktısını
doğrudan pipe'la):

```bash
# NEXTAUTH_SECRET — 48 byte rastgele:
openssl rand -base64 48 | gcloud secrets create NEXTAUTH_SECRET --data-file=-

# MASTER_ENCRYPTION_KEY — 48 byte rastgele (KAYBI TELAFİSİZ — bkz. DR_RUNBOOK.md Bölüm 1):
openssl rand -base64 48 | gcloud secrets create MASTER_ENCRYPTION_KEY --data-file=-

# DB parolaları (Cloud SQL kullanıcıları için, değeri not edip DSN'lere yaz):
openssl rand -base64 24 | tr -d '/+=' | head -c 32; echo
```

Hangi değer hangi env'e:

| Secret | Backend (hukuk-api) | Frontend (hukuk-web) |
|---|---|---|
| `NEXTAUTH_SECRET` | ✅ (JWT doğrulama) | ✅ **aynı değer** (NextAuth imzalama) |
| `MASTER_ENCRYPTION_KEY` | ✅ | — |
| `DATABASE_URL` (app_user) | ✅ | ✅ (NextAuth kullanıcı sorguları) |
| `SERVICE_DATABASE_URL`, `ADMIN_DATABASE_URL` (hukuk) | ✅ | — |
| `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` | ✅ (prod hesapları — faturayı ayır) | — |
| `IYZICO_*` (Bölüm 4) | ✅ | — |
| `SMTP_*` (Bölüm 2) | ✅ | — |
| `SENTRY_DSN` / `NEXT_PUBLIC_SENTRY_DSN` | ✅ | ✅ |

- [ ] `NEXTAUTH_SECRET` üretildi, iki servise de aynı değer bağlandı
- [ ] `MASTER_ENCRYPTION_KEY` üretildi + **offline yedeği aynı gün alındı**
      (`DR_RUNBOOK.md` 1.2 — kağıt/şifreli USB, 2 nüsha)
- [ ] Anthropic + Google API anahtarları prod hesaplardan alındı, kullanım
      limitleri/bütçe alarmı kuruldu
- [ ] Hiçbir secret repo'da, `.env` dosyasında veya chat geçmişinde değil

## 2. Resend SMTP kurulumu (e-posta gitmiyor = kayıt akışı ölü)

Şu an local Mailpit var; prod'da doğrulama/şifre sıfırlama/hatırlatıcı mailleri
için gerçek SMTP şart. Öneri: **Resend** (basit, TR teslimatı iyi).

1. [ ] resend.com'da hesap aç → **Domains → Add Domain** → `hukukcuyapayzekasi.com`
2. [ ] Resend'in verdiği DNS kayıtlarını domain sağlayıcı paneline ekle:
   - **DKIM:** `resend._domainkey` TXT kaydı (Resend panelinden kopyala)
   - **SPF:** `send` subdomain'i için MX + TXT (`v=spf1 include:amazonses.com ~all` benzeri — panel ne veriyorsa onu)
   - (Önerilir) **DMARC:** `_dmarc` TXT → `v=DMARC1; p=quarantine; rua=mailto:admin@hukukcuyapayzekasi.com`
3. [ ] Panelde domain "Verified" olana kadar bekle (DNS propagation 5 dk–2 saat)
4. [ ] **API Keys** → yeni key üret → SMTP bilgilerini Secret Manager'a yaz:
   ```bash
   printf '%s' 'smtp.resend.com' | gcloud secrets versions add SMTP_HOST --data-file=-
   printf '%s' '587'             | gcloud secrets versions add SMTP_PORT --data-file=-
   printf '%s' 'resend'          | gcloud secrets versions add SMTP_USER --data-file=-
   printf '%s' 're_xxxxxxxx'     | gcloud secrets versions add SMTP_PASS --data-file=-
   printf '%s' 'no-reply@hukukcuyapayzekasi.com' | gcloud secrets versions add SMTP_FROM --data-file=-
   ```
5. [ ] Test: prod'da kayıt ol → doğrulama maili **Gmail + Outlook + Yandex**
   hesaplarına geliyor mu, spam'a düşüyor mu kontrol et
6. [ ] mail-tester.com'a bir doğrulama maili gönder → skor 9+/10

## 3. ALLOWED_ORIGINS ve NEXTAUTH_URL prod değerleri

Varsayılanlar localhost — set edilmezse **frontend API'ye bağlanamaz / login çalışmaz**.

| Değişken | Nerede | Prod değeri |
|---|---|---|
| `ALLOWED_ORIGINS` | hukuk-api env | `https://hukukcuyapayzekasi.com` (www kullanılacaksa virgülle ekle: `https://hukukcuyapayzekasi.com,https://www.hukukcuyapayzekasi.com`) |
| `NEXTAUTH_URL` | hukuk-web env | `https://hukukcuyapayzekasi.com` |
| `NEXT_PUBLIC_SITE_URL` | hukuk-web (build-time!) | `https://hukukcuyapayzekasi.com` |
| `NEXT_PUBLIC_API_URL` | hukuk-web (build-time!) | `https://api.hukukcuyapayzekasi.com` |
| `DEBUG` | hukuk-api env | boş/`0` (hata detayı sızmasın) |

- [ ] `NEXT_PUBLIC_*` değerleri **derleme anında gömülür** — değiştirince web'i
      yeniden build et (cloudbuild `_SITE_URL` / `_API_PUBLIC_URL` substitution'ları)
- [ ] Prod'da login ol + emsal araması yap → console'da CORS hatası yok

## 4. iyzico canlı başvurusu (onay 1-2 hafta — HEMEN başlat)

1. [ ] iyzico.com → üye işyeri başvurusu. Hazır olsun: şirket ünvanı, vergi no,
   MERSİS, imza sirküleri, banka IBAN'ı (şirket hesabı), web sitesi URL'i
2. [ ] Başvuruda site incelenir — **şunlar yayında olmalı:**
   `/mesafeli-satis`, `/iade-politikasi`, `/gizlilik`, `/kullanim-sartlari`,
   fiyatların KDV dahil gösterimi, footer'da şirket bilgisi
3. [ ] `web/app/mesafeli-satis/page.tsx` içindeki `[ŞİRKET ÜNVANI]`, `[ADRES]`,
   `[MERSİS NO]`, `[VERGİ DAİRESİ / VERGİ NO]`, `[TELEFON]` placeholder'larını doldur
4. [ ] Onay gelince panelden **canlı API anahtarlarını** al:
   `IYZICO_API_KEY`, `IYZICO_SECRET_KEY` → Secret Manager; `IYZICO_BASE_URL=https://api.iyzipay.com`
5. [ ] Panelde 4 abonelik ürünü + pricing plan oluştur → referans kodlarını
   `IYZICO_PLAN_PRO_SOLO`, `IYZICO_PLAN_PRO_UYAP`, `IYZICO_PLAN_TEAM`,
   `IYZICO_PLAN_TEAM_UYAP` secret'larına yaz
6. [ ] Webhook URL: `https://api.hukukcuyapayzekasi.com/api/billing/webhook` +
   imza anahtarını `IYZICO_WEBHOOK_SECRET`'a yaz (bkz. `SECURITY_HARDENING.md` §1)
7. [ ] Satış açılışında: gerçek kartla düşük tutarlı uçtan uca test
   (ödeme → webhook → plan aktif → iptal → iade)

## 5. Embedding'i tamamla (187K chunk → pgvector)

Şu an kısmi. Tamamı `rag_chunks` tablosuna (Cloud SQL, `vector(768)`) yazılmalı.
~~Chroma~~ artık kullanılmıyor.

Seçenek A — **Google batch embedding** (basit, GPU gerekmez, önerilen):
```bash
# Cloud SQL Auth Proxy açıkken (localhost:5432):
export RAG_DATABASE_URL='postgresql://hukuk:...@localhost:5432/hukuk_emsal'
export EMBEDDING_PROVIDER=google   # text-embedding-004, GOOGLE_API_KEY gerekli
python -m pipelines.embed --input data/final/chunks.parquet
```

Seçenek B — **geçici GPU VM** (local model, API maliyeti yok):
```bash
# 1) GPU VM aç (spot ucuzdur, iş bitince SİL):
gcloud compute instances create embed-vm --zone=europe-west1-b \
  --machine-type=g2-standard-4 --accelerator=type=nvidia-l4,count=1 \
  --image-family=pytorch-latest-gpu --image-project=deeplearning-platform-release \
  --provisioning-model=SPOT --boot-disk-size=100GB
# 2) VM'de repo + data/final/chunks.parquet + proxy kur, sonra:
export EMBEDDING_PROVIDER=local    # intfloat/multilingual-e5-base
python -m pipelines.embed --input data/final/chunks.parquet
# 3) VM'İ SİLMEYİ UNUTMA:
gcloud compute instances delete embed-vm --zone=europe-west1-b
```

> Dikkat: sağlayıcı seçimi kalıcıdır — sorgu embedding'i de aynı modelle
> yapılmalı. Prod `EMBEDDING_PROVIDER` env'i pipeline'da kullanılanla aynı olsun.

- [ ] `SELECT count(*) FROM rag_chunks;` ≈ 187.000
- [ ] Örnek 20 sorguda sonuç kalitesi göz kontrolü (bilinen kararlar dönüyor mu)

## 6. İzleme: UptimeRobot + Sentry

**UptimeRobot** (ücretsiz plan yeter):
- [ ] uptimerobot.com'da hesap aç
- [ ] Monitor 1: `https://api.hukukcuyapayzekasi.com/api/health` — HTTP, 5 dk aralık
- [ ] Monitor 2: `https://hukukcuyapayzekasi.com` — HTTP, 5 dk aralık
- [ ] Alarm kanalı: e-posta (+ istersen mobil push uygulaması)

**Sentry:**
- [ ] sentry.io'da org + 2 proje aç: `hukuk-api` (Python) ve `hukuk-web` (Next.js)
- [ ] DSN'leri env'e koy: backend `SENTRY_DSN` (kod hazır — `api/main.py`,
      `send_default_pii=False`), frontend `NEXT_PUBLIC_SENTRY_DSN`
- [ ] Alert rule: yeni hata türünde e-posta
- [ ] Test: geçersiz bir istekle bilinçli hata üret → Sentry'de görünüyor mu

## 7. Smoke test senaryosu (prod'da elle, lansman günü)

Sırayla; herhangi bir adım kırmızıysa lansmanı durdur.

1. **Kayıt:** Temiz tarayıcıda `/kayit` → yeni e-posta ile kayıt ol.
   ✅ "Doğrulama maili gönderildi" ekranı geliyor.
2. **Doğrulama:** Gelen kutusunu aç (spam'ı da kontrol et) → maildeki linke tıkla.
   ✅ Hesap doğrulandı, giriş yapılabiliyor. (Mail 2 dk'da gelmediyse: Bölüm 2'ye dön.)
3. **Giriş:** E-posta + şifre ile giriş. ✅ Panel açılıyor, oturum sayfa
   yenilemede düşmüyor.
4. **Arama:** Emsal arama'da "işe iade davası ispat yükü" ara.
   ✅ Anlamlı kararlar listeleniyor (<10 sn), karar detayı açılıyor.
5. **Dilekçe:** Dilekçe oluşturma'da kısa bir olay anlat → üret.
   ✅ Taslak üretiliyor, PII maskeleme uyarısı/akışı çalışıyor, çıktı indirilebiliyor.
6. **Hatırlatıcı:** Yarına bir hatırlatıcı ekle → test için saatini 5 dk sonraya çek.
   ✅ Hatırlatıcı e-postası geliyor.
7. **Yasal sayfalar:** `/mesafeli-satis`, `/iade-politikasi`, `/gizlilik`,
   `/kullanim-sartlari`, `/yasal-uyari` açılıyor; placeholder kalmadı.
8. **Çıkış + limit:** Çıkış yap, tekrar gir; free plan limit göstergesi tutarlı.
9. **Mobil:** Aynı akışın 1-4 adımlarını telefonda tekrarla.

- [ ] 9/9 yeşil → lansman GO

## 8. Son kontrol (özet)

- [ ] Bölüm 1-3 tamam → site bekleme-listesi modunda CANLI olabilir
- [ ] Bölüm 4 başvurusu gönderildi (onay beklenirken satış kapalı kalabilir)
- [ ] Bölüm 5-6 tamam → gerçek kullanıcı alınabilir
- [ ] Bölüm 7 smoke test yeşil
- [ ] `DR_RUNBOOK.md` Bölüm 4'teki ilk restore tatbikatı planlandı
- [ ] `PRODUCTION_CHECKLIST.md`'deki hukuki maddeler (LLM çıktısı + KVKK metni
      hukukçu incelemesi) tamamlandı — bunlar hâlâ geçerli ve devredilemez
