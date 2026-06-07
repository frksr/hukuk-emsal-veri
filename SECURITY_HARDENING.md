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

**Deployment — RLS'in ikinci katman olarak gerçekten çalışması için:**
1. `infra/db/07_rls_hardening.sql` migration'ını uygulayın.
2. İki rol/iki DSN ile bağlanın:
   - `DATABASE_URL`        → `app_user`  (NOBYPASSRLS) — kullanıcı istekleri
   - `SERVICE_DATABASE_URL`→ `app_service` (BYPASSRLS) — sistem işleri
3. Tablo owner'ı bu rollere uygun GRANT'leri vermeli (migration örnek GRANT'leri
   içerir). Backend'i tablo owner'ı / superuser ile bağlamayın.

> `SERVICE_DATABASE_URL` set edilmezse iki havuz da `DATABASE_URL`'e düşer; bu
> durumda rol-bazlı ikinci katman devre dışı kalır (uygulama yine çalışır,
> izolasyon explicit `WHERE` + context'li `db_session` ile sağlanır).

## 4. Kriptografik silme (KVKK m.7) — gerçek ✅

- `services/encryption.py` + `services/key_manager.py`: her tenant için **rastgele
  DEK** üretilir, master key ile **sarmalanıp** `tenant_encryption_keys` tablosunda
  saklanır. Veri DEK ile şifrelenir.
- Tenant silinince DEK satırı silinir → master key dursa bile veri **çözülemez**
  (gerçek crypto-shredding). Eski deterministik (HKDF) türetme yalnızca eski
  kayıtları çözmek için fallback olarak korunur.
- `scripts/purge_deleted.py`: 30 günü dolan soft-deleted hesapları kalıcı siler ve
  solo tenant verisini kriptografik olarak yok eder. **Günlük cron olarak çalıştırın.**

## 5. PII redaction — dürüst kapsam ✅

- `services/pii_redaction.py`: regex katmanı yapısal PII'yi (TCKN/IBAN/telefon/
  e-posta/kart/plaka) maskeler. **İsim/adres** için opsiyonel **NER** katmanı
  (`PII_NER_MODEL` env, ör. BERTurk-NER).
- NER kapalıyken `redact()` → `names_redacted=False`; UYAP sorgu yanıtı bunu
  `pii.warning` ile bildirir. `PII_BLOCK_FOREIGN_LLM_WITHOUT_NER=1` ile NER yokken
  yurt dışı LLM çağrısı tamamen engellenebilir.
- Abartılı "LLM hiç kişisel veri görmez" iddiası kod ve beta sözleşmesinde
  düzeltildi.

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
