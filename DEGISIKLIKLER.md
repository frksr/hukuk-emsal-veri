# Denetim Düzeltmeleri — Değişiklik Özeti

**Tarih:** 6 Ağustos 2026 · **Temel:** `78903be` ("new features and bugfix")
**Kapsam:** 81 dosya · +3.487 / −474 satır
**Test:** 92 → **204** geçen test · `tsc --noEmit`: 41 hata → **0**

Uygulama: `git apply denetim-duzeltmeleri.patch`

---

## Öne çıkan: testin yakaladığı gerçek bug

`tests/test_billing_security.py` CI'da hiç koşmuyordu ve **kırmızıydı**.
`_valid_tckn("11111111111")` `True` dönüyordu — TC Kimlik No checksum'ı hiç
uygulanmıyordu, yalnızca "11 hane + ilk hane 0 değil" kontrol ediliyordu. Sahte
varsayılan değerler fatura profiline yazılabiliyordu.

Resmi NVİ algoritması (2 kurallı checksum) eklendi. iyzico'nun dokümantasyondaki
örnek numarası (`74300864791` — gerçek checksum'ı sağlamaz) **yalnızca sandbox**
ortamında kabul ediliyor, prod'da reddediliyor.

---

## 1. Güvenlik

| # | Ne | Dosya |
|---|---|---|
| K1 | **Askıya alınan kullanıcının API anahtarı çalışmaya devam ediyordu.** `require_api_key` `users` tablosuna JOIN yapmıyordu; `is_active` / `restricted_at` kontrolü eklendi. Ayrıca suspend işlemi artık anahtarları da iptal ediyor (cascade revoke). | `api/routers/v1.py`, `api/routers/admin.py` |
| Y1 | **`X-Forwarded-For` doğrulanmadan güveniliyordu.** İstemci header'ı uydurarak IP bazlı anonim kotayı sınırsız aşabiliyor, `audit_log.ip_address`'i sahteleyebiliyordu. Yeni `api/net.py`: zincirin **sağından** `TRUSTED_PROXY_HOPS` kadar sayan çözüm; zincir kısaysa TCP peer adresine düşer. | `api/net.py` (yeni), `rate_limit.py`, `audit.py`, `deps.py`, `newsletter.py`, `waitlist.py`, `billing.py` |
| Y2 | **`/api/health` DB'ye hiç dokunmuyordu** — Postgres düşse bile LB 200 görüyordu. Liveness/readiness ayrıldı: yeni **`GET /api/ready`** `SELECT 1` atar, erişilemezse **503**. Railway + Docker healthcheck'leri buna yönlendirildi. | `api/main.py`, `railway.json`, `Dockerfile*` |
| — | CORS `allow_methods` yalnızca GET/POST/OPTIONS'tı; API PATCH/PUT/DELETE uçları içeriyor. Genişletildi. | `api/main.py` |
| — | `require_admin` dört router'da kopya-yapıştırdı → `api/auth.py`'ye taşındı (+ genel `require_role`). | `api/auth.py` + 4 router |
| — | Webhook idempotency `iyzico_token` NULL geldiğinde çalışmıyordu (`NULL = NULL` asla TRUE değil) → gövde SHA-256 hash'ine düşülüyor. | `api/routers/billing.py` |
| — | `.env.example`'daki gerçek formatlı iyzico sandbox anahtarları `__DOLDUR__` yapıldı. | `.env.example` |
| Y5 | **`/embed/faiz` widget'ı kendi CSP'si tarafından bloklanıyordu** — pazarlanan iframe gömme özelliği hiçbir sitede çalışmıyordu. `/embed/*` için `frame-ancestors` ve `X-Frame-Options` istisnası. | `web/middleware.ts`, `web/next.config.mjs` |

## 2. Faturalama

| # | Ne | Dosya |
|---|---|---|
| K4 | **Çift abonelik / çift tahsilat riski.** `checkout()` mevcut aboneliği hiç sorgulamıyordu. Artık: aynı plana ikinci checkout engelleniyor; plan değişiminde yeni abonelik **aktifleştikten sonra** eskisi iyzico'da iptal ediliyor (sıra bilinçli — tersi olsa başarısız ödemede kullanıcı plansız kalırdı). | `api/routers/billing.py` |
| — | **Plan limitleri dört ayrı yerde kopyalanmıştı** (`CASE WHEN` blokları). Yeni plan eklendiğinde admin paneli ile ödeme webhook'u farklı limitler yazabiliyordu → tek kaynak `PLAN_LIMITS` + `plan_limitleri()`. Regresyon testi kopyaların geri gelmesini engelliyor. | `billing.py`, `admin.py` |

## 3. RAG kalitesi (ürünün en kritik riski)

| # | Ne | Dosya |
|---|---|---|
| K6 | **Benzerlik eşiği yoktu** — her sorgu mutlaka `k` sonuç döndürüyordu, "alakasız" diye bir kavram yoktu. Veri icra ağırlıklı olduğundan iş hukuku sorusuna alakasız icra kararları "emsal" diye dönüyor, dilekçeye giriyordu. `RAG_MIN_SIMILARITY` (liste) ve `RAG_CONTEXT_MIN_SIMILARITY` (LLM'e giden, daha katı) eklendi. | `services/rag.py` |
| Y11 | **Hibrit arama.** Saf vektör araması "İİK 67/1", "2023/1234 E." gibi tam eşleşmelerde başarısızdı. `tsvector` + GIN indeksi eklendi, iki sıralama **RRF** ile birleştiriliyor. | `services/rag.py`, `infra/db/32_*.sql` |
| Y5 | **Çeşitlilik.** Örtüşmeli chunk'lar yüzünden top-5'in tamamı aynı karar olabiliyordu → karar başına en fazla N parça. | `services/rag.py` |
| Y6 | HNSW parametreleri varsayılandı → `m=24, ef_construction=128` + oturum bazlı `ef_search`. | `infra/db/32_*.sql` |
| K8 | **Grounding doğrulaması.** LLM'e "uydurma esas/karar no" talimatı vardı ama programatik kontrol yoktu. Yeni `services/grounding.py` üretilen metindeki tüm atıfları bağlamdaki emsallerle karşılaştırıyor; eşleşmeyenler kullanıcıya uyarı olarak dönüyor (stream'de dahil). Kanun madde atıfları hariç tutuluyor. | `services/grounding.py` (yeni), `dilekce_emsalli.py`, `karsi_argument.py` |
| K9 | **Eval altyapısı.** `scripts/rag_eval.py`: recall@k, precision@k, MRR, boş-yanıt oranı, kategori kırılımı (kapsam boşluğunu gösterir), eşik taraması, CI kapısı (`--min-recall`). `evals/altin_set.jsonl` şablonu + negatif örnekler. | `evals/`, `scripts/rag_eval.py` |
| O4 | **Embedding modeli karışıklığı.** Model değişip `--recreate` unutulursa farklı semantik uzaylardan vektörler karışıyor ve benzerlik sessizce anlamsızlaşıyordu → `embedding_model` kolonu + karışıklık tespitinde durdurma. | `pipelines/embed.py`, `infra/db/32_*.sql` |

## 4. Gözlemlenebilirlik

- **Correlation ID + yapısal log** (`api/logging_setup.py`): her isteğe `request_id`,
  `contextvars` ile tüm log satırlarına otomatik enjeksiyon, `X-Request-Id` yanıt
  header'ı, `LOG_FORMAT=json` ile Cloud Logging'de `jsonPayload.request_id`
  filtrelemesi, Sentry tag'i. 500 yanıtları artık kullanıcıya referans kodu veriyor.
- İstemciden gelen `X-Request-Id` korunuyor (log enjeksiyonuna karşı temizlenerek).

## 5. Altyapı

- **CI** (`.github/workflows/ci.yml`):
  - `pytest tests/` — **tüm** paket koşuyor. Eskiden dosya adları elle listeleniyordu
    ve üçü listede yoktu; biri ödeme güvenliği testiydi.
  - Coverage (`pytest-cov`) + iş akışı özeti.
  - Yeni **Postgres'li entegrasyon job'u** — RLS izolasyonu ve kriptografik silme
    testleri artık her PR'da koşuyor (eskiden yalnızca elle).
  - Kritik ruff kuralları (E9/F63/F7/F82) **bloklayıcı**.
  - Yeni **güvenlik job'u**: pip-audit, npm audit, gitleaks.
  - `.github/dependabot.yml` (pip + npm + actions).
- **Docker**: iki aşamalı build (derleyici final imajda kalmıyor), **root olmayan
  kullanıcı** (uid 10001), `Dockerfile.api`'ye healthcheck, `--proxy-headers`.
- **KVKK cron'u**: `scripts/purge_deleted.py` hiçbir zamanlayıcıya bağlı değildi —
  "30 günde silinir" vaadi fiilen yerine gelmiyordu. Yeni `scripts/cron_daily.py`
  (purge + faiz oranları + emsal alarmları, kritik iş hata verirse admin'e mail)
  ve `setup_gcp.sh cron` fazı (Cloud Run Job + Cloud Scheduler).
- `pytest.ini` eklendi (asyncio_mode, markers, strict-markers).

## 6. Frontend

- **Tip güvenliği fiilen kapalıydı.** `ignoreBuildErrors: true` yüzünden **41 gerçek
  tip hatası** prod build'inde sessizce geçiyordu. En çarpıcısı: `lib/api.ts`'teki
  `EmsalKarar` ile onu tüketen arama formunun **hiçbir ortak alanı yoktu**.
  - `EmsalKarar`, `AramaParams`, `ZamanasimiParams`, `IhtarnameParams`,
    `KarsiArgumentParams`, `KvkkChecklistParams`, `SozlesmeAnalizParams`, `OzetParams`,
    `OzetSonuc` → backend Pydantic şemalarıyla hizalandı.
  - Kalan 30+ hata (`noUncheckedIndexedAccess` kaynaklı gerçek latent null-erişimler)
    17 dosyada düzeltildi.
  - `ignoreBuildErrors: false` — kapı artık gerçek.
- `buildFaqJsonLd` hem `{question, answer}` hem `{q, a}` kabul ediyor.
- `lib/auth/db.ts`: `INSERT ... RETURNING` sonucu sessizce `undefined` ile
  devam etmek yerine açık hata.

## 7. Diğer

- `common/job_queue.py`: **sonsuz retry riski**. Üst sınır yoktu; kalıcı boş dönen
  bir kayıt sonsuza dek `pending ↔ in_progress` arasında dönüyordu →
  `max_attempts` (varsayılan 5); `reset_source` sayacı sıfırlıyor.
- `api/deps.py` rate limiter: LB arkasında tüm kullanıcılar tek kovayı paylaşıyordu
  (yanlış IP çözümü) + `_rate_buckets` hiç temizlenmiyordu (bellek sızıntısı).
  İkisi de düzeltildi, `kota.py` ile farkı dokümante edildi.
- Ruff `--fix`: 52 kullanılmayan import / f-string temizliği.
- **README** tamamen yeniden yazıldı — projeyi hâlâ "scraper kümesi" olarak
  tanıtıyordu, SaaS'tan hiç bahsetmiyordu.

---

## Yeni testler (112 adet)

| Dosya | Neyi kilitliyor |
|---|---|
| `test_client_ip.py` | XFF sahteciliği, proxy hop sayısı, IPv6, geçersiz değer |
| `test_api_key_yetki.py` | K1 — pasif/kısıtlı kullanıcının anahtarı, cascade revoke |
| `test_billing_plan_degisimi.py` | K4 — çift abonelik, devir sırası, webhook idempotency, TCKN |
| `test_plan_limits.py` | Limit tablosunun tekliği + kopyaların geri gelmemesi |
| `test_rag_kalite.py` | Eşik, çeşitlilik, RRF birleştirme, tsquery enjeksiyon güvenliği |
| `test_grounding.py` | Uydurma atıf tespiti, kanun maddesi ayrımı, temizleme politikası |
| `test_job_queue_retry.py` | Sonsuz retry koruması |
| `test_api_smoke.py` | HTTP seviyesinde ilk entegrasyon testleri + **OpenAPI'deki tüm GET uçlarını tokensiz deneyen genel auth kapısı** |

---

## Uygulama sonrası yapılması gerekenler

1. **Migration**: `python -m scripts.init_db` (yeni `32_rag_hybrid_search.sql`).
   HNSW indeksleri yeniden oluşturuluyor — büyük tabloda dakikalar sürer, bakım
   penceresi planlayın.
2. **Env**: `TRUSTED_PROXY_HOPS` (deploy topolojinize göre — yanlış değer kota
   atlatmaya açık kapı bırakır), `LOG_FORMAT=json`, `ADMIN_EMAIL`,
   `RAG_MIN_SIMILARITY`.
3. **Cron**: `./infra/gcp/setup_gcp.sh cron`
4. **Healthcheck**: LB/uptime izlemeyi `/api/ready`'ye çevirin.
5. **Eval seti**: `evals/altin_set.jsonl` şablonlarını gerçek karar kimlikleriyle
   doldurun, sonra `python -m scripts.rag_eval --esik-tara` ile eşiği kalibre edin.
   Şu anki `0.35` değeri **tahmindir**, ölçülmemiştir.
6. **Bilgi**: `next@14.2.18` bilinen bir güvenlik açığı taşıyor (npm uyarısı) —
   yamalı sürüme yükseltme ayrı bir iş olarak planlanmalı.
