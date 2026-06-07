# Güvenlik Sertleştirmeleri — Production Öncesi

Bu doküman, code review'da işaretlenen production-blocker'lar için yapılan
düzeltmeleri ve **deployment'ta yapılması gereken yapılandırmayı** özetler.

## 1. iyzico Webhook — sahtecilik koruması ✅

`api/routers/billing.py::webhook` artık gelen payload'a körü körüne güvenmiyor:

1. **İmza doğrulama** — `IYZICO_WEBHOOK_SECRET` set ise HMAC-SHA256 imzası
   doğrulanır; geçersizse `401`.
2. **Otorite re-query** — durum değiştiren her olayda abonelik durumu doğrudan
   iyzico API'sinden (kendi key/secret'imizle) yeniden sorgulanır; karar gerçek
   duruma göre verilir. Ödeme tutarı payload'tan **değil**, kayıtlı `amount_try`'dan
   yazılır.
3. İmza yoksa **ve** iyzico API'si yapılandırılmamışsa durum değiştirilmez.

**Yapılmalı:** iyzico panelinden webhook imza anahtarını alıp
`IYZICO_WEBHOOK_SECRET` olarak set edin.

## 2 & 3. RLS tenant izolasyonu — gerçekten devrede ✅

- `api/db.py::db_session` artık context'i **transaction içinde** ve **parametreli
  `set_config`** ile ayarlıyor (eski `SET LOCAL` + f-string yöntemi transaction
  dışında etkisizdi ve SQL injection'a açıktı).
- Tüm kullanıcı-kapsamlı sorgular `db_session(user_id, tenant_id)` ile RLS'e tabi.
- Cross-tenant/bootstrap işler (webhook, auth bootstrap, audit, admin, rate-limit,
  key_manager, arka plan) yeni `service_session()` (RLS bypass) kullanır.
- `infra/db/07_rls_hardening.sql`: tüm RLS tablolarında `FORCE ROW LEVEL SECURITY`
  (owner bypass'ı kapatır), billing tablolarına izolasyon policy'leri.

- `infra/db/09_rls_fix_recursion.sql`: **kritik düzeltme.** Orijinal politikalar
  `tenant_members` alt-sorgusu yüzünden context set edildiğinde *infinite
  recursion* veriyordu (uygulama süperuser ile bağlandığı için bu hata şimdiye
  kadar hiç görülmemiş = RLS hiç çalışmamıştı). Politikalar artık RLS'i bypass
  eden `app_current_tenant_ids()` (SECURITY DEFINER) fonksiyonunu kullanır.

**Deployment — RLS'in ikinci katman olarak gerçekten çalışması için:**
1. Migration'ları sırayla uygulayın (`07` → `08` (sadece local) → `09`).
2. İki rol/iki DSN ile bağlanın:
   - `DATABASE_URL`        → `app_user`  (NOBYPASSRLS) — kullanıcı istekleri
   - `SERVICE_DATABASE_URL`→ `app_service` (BYPASSRLS) — sistem işleri
3. Tablo owner'ı bu rollere uygun GRANT'leri vermeli (migration örnek GRANT'leri
   içerir; `tenant_encryption_keys` için app_service'e açık GRANT 07'de var).
   Backend'i tablo owner'ı / superuser ile bağlamayın.

> `SERVICE_DATABASE_URL` set edilmezse iki havuz da `DATABASE_URL`'e düşer; bu
> durumda rol-bazlı ikinci katman devre dışı kalır (uygulama yine çalışır,
> izolasyon explicit `WHERE` + context'li `db_session` ile sağlanır).

**✅ Canlı doğrulandı (local Docker Postgres):** `python -m scripts.verify_rls`
→ 6/6 kontrol geçti: context=A sadece A'yı görür, context=B sadece B'yi,
context yok → 0 satır, cross-tenant INSERT reddedildi, sızıntı yok, service tümünü
görür.

## 4. Kriptografik silme (KVKK m.7) — gerçek ✅

- `services/encryption.py` + `services/key_manager.py`: her tenant için **rastgele
  DEK** üretilir, master key ile **sarmalanıp** `tenant_encryption_keys` tablosunda
  saklanır. Veri DEK ile şifrelenir.
- Tenant silinince DEK satırı silinir → master key dursa bile veri **çözülemez**
  (gerçek crypto-shredding). Eski deterministik (HKDF) türetme yalnızca eski
  kayıtları çözmek için fallback olarak korunur.
- `scripts/purge_deleted.py`: 30 günü dolan soft-deleted hesapları kalıcı siler ve
  solo tenant verisini kriptografik olarak yok eder. **Günlük cron olarak çalıştırın.**

**✅ Canlı doğrulandı:** DEK üret→sakla→yükle→şifrele/çöz, DB-kalıcılık, ve
`destroy_tenant_dek` sonrası eski ciphertext'in yeni DEK ile **çözülememesi**
(crypto-shred) local DB'de test edildi (`tests/test_db_integration.py`).

## 5. PII redaction — isim maskeleme dahil, 3 katman ✅

`services/pii_redaction.py` artık **üç katmanlı**:
1. **Regex** (her zaman): TCKN/IBAN/telefon/e-posta/kart/plaka.
2. **Heuristik** (her zaman, model gerektirmez): rol bağlamlı Türkçe kişi adı
   ("Davacı/Davalı/Vekili/Av./Sayın <Ad Soyad>") + adres kalıpları
   ("X Caddesi/Mahallesi", "No:12", "Daire:5"). → **isim maskeleme varsayılan
   olarak aktiftir.**
3. **NER** (opsiyonel, en geniş): `PII_NER_MODEL` (örn.
   `savasy/bert-base-turkish-ner-cased`) ile serbest metinde PERSON/LOCATION/ORG.

- `name_layer()` aktif en güçlü katmanı ("ner"|"heuristic") bildirir; UYAP sorgu
  yanıtı `pii.name_layer` + `pii.warning` döner. `PII_BLOCK_FOREIGN_LLM_WITHOUT_NER=1`
  ile NER yokken yurt dışı LLM çağrısı engellenebilir (strict KVKK modu).
- Abartılı "LLM hiç kişisel veri görmez" iddiası kod ve beta sözleşmesinde
  düzeltildi.
- **✅ Test edildi:** heuristik gerçek hukuki metinlerde tarafları maskeliyor,
  mahkeme/kurum adlarını yanlışlıkla maskelemiyor (false-positive yok), roundtrip
  birebir; NER ile birlikte tam ad + konum + kurum maskeleniyor.

## 6. Operasyonel tamamlananlar ✅

- **Sentry**: `api/main.py` `SENTRY_DSN` set ise hata/performans izlemeyi başlatır
  (`send_default_pii=False` — KVKK).
- **SMTP**: `services/email.py` env ile yapılandırılır; local `docker-compose`
  içinde **mailpit** (web UI http://localhost:8025).
- **Çerez banner (KVKK)**: `web/components/cookie-consent.tsx`, kök layout'a mount
  edildi (zorunlu/tümü ayrımı, tercih localStorage'da, /gizlilik linki).
- **`.env.example`**: tüm backend env'leri (DB rolleri, master key, PII, iyzico,
  SMTP, Sentry) belgelendi.
- **Local DB**: `docker compose up -d postgres` tüm migration'ları (01–09) + local
  rolleri otomatik uygular.

## Gerekli yeni environment değişkenleri

| Değişken | Amaç | Zorunlu? |
|---|---|---|
| `IYZICO_WEBHOOK_SECRET` | Webhook imza doğrulama | Önerilir (prod) |
| `SERVICE_DATABASE_URL` | RLS-bypass sistem bağlantısı (app_service) | Önerilir (prod) |
| `PII_NER_MODEL` | İsim/adres maskeleme (NER) modeli | KVKK m.9 için önerilir |
| `PII_BLOCK_FOREIGN_LLM_WITHOUT_NER` | NER yokken LLM'i engelle (`1`) | Opsiyonel |
| `MASTER_ENCRYPTION_KEY` | Envelope master key (KMS önerilir) | Zorunlu |

## Testler

`pip install -r requirements-dev.txt` sonrası:

```
pytest tests/test_encryption.py tests/test_pii_redaction.py tests/test_billing_security.py
```

Şifreleme (roundtrip, AAD, tamper, crypto-shred, legacy fallback), PII (redact/
unredact, NER bayrağı), webhook imza + durum eşleme + TCKN/telefon doğrulama
kapsanır.
