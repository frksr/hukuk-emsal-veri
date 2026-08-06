# Hukuk Emsal / Hukukçu Yapay Zekası — Kapsamlı Proje Denetim Raporu

**Tarih:** 6 Ağustos 2026
**Kapsam:** `hukuk-emsal-veri` deposunun tamamı (HEAD = `fa70dc0`, 453 izlenen dosya, ~51.000 satır kaynak kod)
**Yöntem:** Depo anlık görüntüsü alınıp beş bağımsız denetim ekseninde (backend/güvenlik, frontend, veri & RAG, altyapı/DevOps/test, ürün & uyumluluk) dosya dosya okundu. Rapordaki her tespit kodda doğrudan gözlemlendi; kritik iddiaların bir kısmı ayrıca elle teyit edildi (teyit edilenler **[✓]** ile işaretli).

---

## 1. Yönetici Özeti

Proje, adının çağrıştırdığı "scraper kümesi"nin çok ötesine geçmiş; bugün **çok kiracılı (multi-tenant), abonelik tabanlı, RAG destekli bir hukuk teknolojisi SaaS'ı**. Mühendislik kalitesi birçok yerde sektör ortalamasının belirgin üzerinde:

**Güçlü yönler**
- **Tenant izolasyonu**: Postgres RLS + ayrı `app_user` / servis havuzu ayrımı (`api/db.py`), `scripts/verify_rls.py` ile 6 senaryoluk doğrulama betiği.
- **KVKK teknik altyapısı**: Envelope encryption + kriptografik silme (`services/encryption.py`, `services/key_manager.py`), 3 katmanlı PII maskeleme (`services/pii_redaction.py`), PII sızıntısı için uçtan uca test (`tests/test_pii_leak_e2e.py`).
- **Ödeme güvenliği**: iyzico webhook'unda HMAC imza doğrulaması **+ payload'a güvenmeyip iyzico'dan otoritatif re-query**, atomik kredi yükleme (`UPDATE ... WHERE granted=FALSE`).
- **Kota mimarisi**: `api/kota.py`'de advisory-lock ile yarış koşulu korumalı atomik kota tüketimi; plan → kredi → 402 sıralaması doğru.
- **Token güvenliği**: JWT hiçbir zaman tarayıcıya/localStorage'a yazılmıyor; Next.js server-side proxy (`web/app/api/proxy/[...path]`) üzerinden kısa ömürlü token üretiliyor.
- **SEO/içerik motoru**: 24 sayfada JSON-LD, özel sitemap index, blog CMS + LLM ile otomatik SEO üretimi, publisher API.
- **DR dokümantasyonu**: `DR_RUNBOOK.md` RTO/RPO tablosuyla birlikte olgun bir belge.

**Zayıf yönler (özet)**
Sorunlar üç kümede toplanıyor:

1. **Ürün vaadi ile kodun örtüşmemesi** — Team planı satılıyor ama ekip/koltuk yönetimi kodu hiç yok; "e-fatura kesilir" deniyor ama fatura numarası hiçbir yerde yazılmıyor; embed widget'ı pazarlanıyor ama kendi güvenlik başlıkları onu blokluyor.
2. **Doğrulama boşluğu** — 30 API router'ının hiçbiri HTTP seviyesinde test edilmiyor, frontend'de sıfır test var, RAG kalitesi için hiçbir eval seti yok, DR tatbikatı hiç yapılmamış. Bir hukuk ürününde "yanlış emsal" riskini ölçen hiçbir mekanizma yok.
3. **Operasyonel olgunluk** — Staging ortamı yok, CI ile CD birbirinden bağımsız, lint CI'ı kırmıyor, migration ledger'ı yok, yapısal log/correlation ID yok, KVKK kalıcı silme cron'u hiçbir yere bağlı değil.

### Olgunluk Karnesi

| Alan | Not | Kısa gerekçe |
|---|---|---|
| Güvenlik mimarisi (RLS, şifreleme, ödeme) | **A−** | Sağlam tasarım; birkaç kenar durum açığı |
| Backend kod kalitesi | **B** | Doğru çalışıyor ama router'lara gömülü iş mantığı, 1198 satırlık dosyalar |
| Frontend | **B−** | İşlevsel ve özenli; tip güvenliği fiilen kapalı, test yok |
| Veri & RAG kalitesi | **C** | Kapsam dar (yalnız icra hukuku), eval yok, hibrit arama/rerank yok |
| Altyapı & DevOps | **C+** | Deploy çalışıyor; staging yok, CI zayıf, migration aracı yok |
| Test & doğrulama | **D** | API/e2e/frontend/RAG testi sıfır, coverage ölçülmüyor |
| Ürün bütünlüğü | **C** | Satılan bazı özellikler kodda yok |
| Hukuki uyum (metinler) | **C−** | Şirket bilgileri hâlâ placeholder, DPA yok |

---

## 2. Proje Künyesi

| | |
|---|---|
| **Backend** | Python 3.11, FastAPI, asyncpg, 30 router, ~29.000 satır Python |
| **Frontend** | Next.js App Router + TypeScript + Tailwind, ~176 dosya, ~22.000 satır, 70 sayfa |
| **Veri** | Postgres + pgvector (HNSW), eski Chroma kalıntısı, DuckDB/Parquet pipeline |
| **LLM** | Anthropic + Google Gemini (`llm/provider.py`), Google `text-embedding-004` |
| **Ödeme** | iyzico v2 Subscription API + CheckoutForm |
| **Dağıtım** | GCP Cloud Build → Cloud Run (API + web), alternatif Railway/Vercel yapılandırmaları |
| **Yan ürünler** | Chrome eklentisi (`extension/`), eski Streamlit prototipi (`app/`), 4 scraper |
| **Migration** | 33 elle numaralı SQL dosyası (`infra/db/`), araç yok |
| **Test** | 11 pytest dosyası (1.102 satır), CI'da 7'si koşuyor |
| **Dokümantasyon** | 38 markdown dosyası (~6.800 satır) — bazıları bayat |

---

## 3. KRİTİK EKSİKLER (P0 — satış/lansman öncesi kapatılmalı)

### K1. Askıya alınan kullanıcının Public API anahtarı çalışmaya devam ediyor **[✓]**
`api/routers/v1.py:32-47` — `require_api_key` yalnızca `api_keys.aktif = TRUE` bakıyor, `users` tablosuna JOIN yok, `is_active`/`restricted_at` kontrolü yok. Oysa `api/auth.py`'deki JWT ve eklenti token yolları `is_active`'i kontrol ediyor.

**Etkisi:** Admin panelinden "hesabı askıya al"/"kısıtla" (`admin.py:722`, `:753`) yapılan bir kullanıcı, daha önce ürettiği `he_live_...` anahtarıyla `/api/v1/arama`'yı kullanmaya devam eder. Suistimal/dolandırıcılık nedeniyle kapatılan hesap fiilen kapanmamış olur.

**Çözüm:** Sorguya `JOIN users u ON u.id = ak.user_id AND u.is_active = TRUE AND u.restricted_at IS NULL` ekleyin; ayrıca suspend/restrict işleminde ilgili `api_keys` satırlarını `aktif=FALSE` yapın (cascade revoke).

---

### K2. Team planı satılıyor ama ekip/koltuk yönetimi kodu hiç yok **[✓]**
`tenant_members` tablosuna satır ekleyen **tek** kod yolu `scripts/create_admin.py` — elle çalıştırılan bir betik. `api/routers/` altında kullanıcı davet eden hiçbir endpoint yok. `max_users` kolonu plana göre set ediliyor ama hiçbir yerde kontrol edilmiyor/kullanılmıyor.

**Etkisi:** ₺1.499–1.999/ay bandındaki Team ve Team+UYAP planlarını satın alan bir büro, pratikte tek kullanıcılı bir hesap alır. Bu, en pahalı planların temel vaadinin çalışmaması demektir — ticari ve itibari risk.

**Çözüm:** Satış açılmadan ya (a) davet/rol/koltuk endpoint'lerini yazın, ya (b) Team planlarını geçici olarak satıştan kaldırın.

---

### K3. "E-fatura kesilir" vaadi kodda karşılığı olmayan bir beyan **[✓]**
`payments` tablosunda `invoice_number` ve `invoice_pdf_url` kolonları var, `GET /invoices` bunları okuyor (`api/routers/billing.py:490,504`), panel bunları gösteriyor (`web/app/panel/raporlar/raporlar-panel.tsx:68`) — ama **repoda bu kolonlara değer yazan tek bir INSERT/UPDATE yok**. Buna karşın `web/app/fiyatlandirma/page.tsx:105` açıkça "Tüm planlar aylık faturalıdır ve e-fatura kesilir" diyor.

**Etkisi:** Tüketiciye yanlış beyan + VUK/e-fatura mevzuatı uyumsuzluğu riski. Kurumsal büro müşterisi muhasebe için faturayı zorunlu ister.

**Çözüm:** Ya gerçek e-fatura entegrasyonu (Paraşüt/Logo/Foriba API), ya pazarlama metninden bu cümlenin çıkarılması. İkisinden birini satış açılmadan yapın.

---

### K4. Plan yükseltme/düşürme akışı yok — çift faturalama riski
`api/routers/billing.py:150-233` — `checkout()` kullanıcının mevcut aktif aboneliğini hiç sorgulamıyor ve iptal etmiyor. Pro Solo'dayken Team'e geçmek isteyen kullanıcı için iyzico'da **ikinci bir abonelik** açılır; birincisi otomatik iptal edilmez.

**Etkisi:** Aynı kullanıcıdan aynı ay içinde iki kez tahsilat. Doğrudan gelir + güven kaybı, iade talebi zinciri.

**Çözüm:** `checkout()` başında aktif abonelik kontrolü; varsa "plan değiştir" akışına yönlendirip eski aboneliği iyzico'da iptal edin (proration hesabı ikinci aşamada eklenebilir).

---

### K5. Şirket kimlik bilgileri hukuki metinlerde hâlâ placeholder
`web/app/mesafeli-satis/page.tsx:39-51` içinde `[ŞİRKET ÜNVANI]`, `[ADRES]`, `[MERSİS NO]`, `[VERGİ DAİRESİ/NO]`, `[TELEFON]`; `web/app/gizlilik/page.tsx:33` içinde `[ŞİRKET ÜNVANI]` doldurulmamış.

**Etkisi:** Mesafeli Satış Sözleşmesi ve Aydınlatma Metni eksik/geçersiz sayılabilir; iyzico canlı hesap başvurusu da bu bilgileri arar. Projenin kendi yol haritası bunu zaten P0 işaretlemiş.

---

### K6. RAG'da benzerlik eşiği yok — alakasız kararlar "emsal" olarak sunuluyor **[✓]**
`services/rag.py` içindeki `search()` sorgusu `ORDER BY embedding <=> q LIMIT k` — **minimum benzerlik eşiği yok**, "alakasız ise boş dön" mantığı yok. Her sorgu mutlaka `k` adet sonuç döndürür.

Bu, K7 ile birleştiğinde ciddileşiyor: veri kümesi yalnızca icra/tahsilat/ihtar hukukunu kapsarken, `services/karsi_argument.py:43-53` iş hukuku, ceza, idari gibi dava türlerini kabul ediyor. Kullanıcı iş hukuku sorusu sorduğunda sistem alakasız icra kararlarını "emsal" diye sunar ve bunlar `services/dilekce_emsalli.py` üzerinden dilekçeye girer.

**Çözüm:** Cosine benzerliği için eşik (örn. `similarity < 0.62` → ele) + eşiği geçen sonuç yoksa kullanıcıya açıkça "bu konuda veri tabanımızda yeterli emsal yok" mesajı.

---

### K7. Veri kapsamı ürün vaadinin çok altında
- `scrapers/` altında **UYAP Emsal Karar Bilgi Bankası için scraper yok** — Türkiye'nin en kapsamlı içtihat kaynağı dışarıda. `services/uyap_parser.py` yalnızca kullanıcının *yüklediği* dosyaları ayrıştırıyor.
- `queries/keywords.yaml` ve tüm scraper'lar yalnızca icra hukuku terimleriyle arama yapıyor.
- `scrapers/yargitay.py:47-53` — Yargıtay'ın yalnızca **5 dairesi** hardcoded (12., 8., 13., 19., 3. HD).
- İlk derece ve istinaf (BAM) kararları hiç yok.

**Çözüm:** Ya kapsam genişletilmeli (öncelik: UYAP Emsal + daire/konu genişletme), ya ürün konumlandırması dürüstçe "icra ve tahsilat hukuku odaklı" hale getirilmeli.

---

### K8. LLM'in ürettiği esas/karar numaraları programatik olarak doğrulanmıyor
`services/dilekce_emsalli.py:82-104` ve `services/karsi_argument.py:63-93` prompt'larında "uydurma esas/karar numarası üretme" talimatı var, ancak **çıktı sonrası doğrulama yok**. `karsi_argument.py`'de yalnızca `dayanak_emsal` JSON alanı eşleştiriliyor (satır 201-234); serbest metin dilekçede geçen numaralar hiç kontrol edilmiyor.

**Etkisi:** Avukatın mahkemeye uydurma emsal sunması. Bir hukuk ürününde kabul edilebilir en yüksek risk kalemi.

**Çözüm:** Üretilen metinden `\d{4}/\d+` desenlerini çıkarıp bağlama verilen emsal listesiyle eşleştirin; eşleşmeyenleri ya metinden temizleyin ya kullanıcıya "doğrulanamadı" rozetiyle işaretleyin.

---

### K9. RAG kalitesi için hiçbir eval/altın standart seti yok
Depo genelinde retrieval doğruluğu, chunk isabeti veya LLM çıktı kalitesini ölçen hiçbir test yok. `tests/` altında RAG'a dokunan tek bir dosya yok.

**Çözüm:** 50–100 soruluk altın standart set (soru → beklenen karar ID'leri) + `recall@k`, `precision@k` ölçümü; CI'da eşik altına düşerse uyarı.

---

### K10. KVKK 30 günlük kalıcı silme betiği hiçbir zamanlayıcıya bağlı değil
`DELETE /me/account` (`api/routers/me.py:433-460`) yalnızca soft-delete yapıp kullanıcıya "verileriniz 30 gün içinde tamamen silinir" diyor. Bu vaadi yerine getiren `scripts/purge_deleted.py` ne `railway.json`'da, ne `cloudbuild.yaml`'da, ne GitHub Actions'ta zamanlanmış. Projenin kendi analiz dokümanı da bunu itiraf ediyor (`ANALIZ_VE_YOL_HARITASI_2026-07.md:120`).

**Çözüm:** Cloud Scheduler ile günlük tetikleme + başarısızlık alarmı.

---

### K11. CI'da güvenlik testleri hiç çalışmıyor **[✓]**
`.github/workflows/ci.yml` pytest'i **dosya adlarıyla sınırlı** çağırıyor. Listede olmayanlar: `tests/test_billing_security.py` (iyzico webhook imza doğrulaması), `tests/test_job_queue.py`, `tests/test_uyap_parser.py`. Yani **ödeme güvenliği testi hiçbir PR'da koşmuyor**.

**Çözüm:** `pytest tests/ -q --ignore=tests/test_db_integration.py` ile tüm dosyaları koşun.

---

## 4. YÜKSEK ÖNCELİKLİ EKSİKLER (P1)

### Y1. `X-Forwarded-For` doğrulanmadan güveniliyor **[✓]**
`api/rate_limit.py:110-115` ve `api/audit.py:29-37` istemcinin gönderdiği XFF header'ının ilk değerini güvenilir-proxy kontrolü olmadan kabul ediyor. `railway.json`'daki uvicorn komutunda `--proxy-headers`/`--forwarded-allow-ips` yok.
**Sonuç:** (a) anonim kullanıcı kotası (günlük 20 arama) her istekte farklı XFF göndererek sınırsız aşılabilir; (b) `audit_log.ip_address` — adli inceleme için tutulan alan — tamamen sahte doldurulabilir.

### Y2. Public `/api/health` veritabanını hiç kontrol etmiyor **[✓]**
`api/main.py:211-222` yalnızca RAG ve LLM durumunu döndürüyor, `SELECT 1` yok. `railway.json`'ın healthcheck yolu bu. Postgres düşerse LB hâlâ 200 OK görür, instance sağlıksız işaretlenmez. (Auth arkasındaki `/admin/health` DB'yi doğru kontrol ediyor — asıl health endpoint'i etmiyor.)

### Y3. Kriptografik silme garantisi çok-worker'lı prodda tam değil
`services/key_manager.py` DEK'leri process-içi cache'te tutuyor; `destroy_tenant_dek()` yalnızca kendi process'inin cache'ini temizliyor. `--workers 4` ile diğer 3 worker, yeniden başlayana kadar ham DEK'i bellekte tutar. `services/encryption.py`'nin "gerçek silme garantisidir" iddiası bu senaryoda tutmuyor.
**Çözüm:** DEK cache'ine TTL + `LISTEN/NOTIFY` ile invalidation, ya da purge akışına rolling restart eklenmesi.

### Y4. Frontend'de tip güvenliği fiilen devre dışı **[✓]**
`web/next.config.mjs`'de `typescript.ignoreBuildErrors: true` ve `eslint.ignoreDuringBuilds: true`. Somut kanıt: `web/lib/api.ts:24-37`'deki `EmsalKarar` tipi (`id, mahkeme, daire, esas_no...`) ile onu tüketen `web/app/emsal-arama/arama-form.tsx` (`r.chunk_id, r.court_chamber, r.case_no, r.similarity...`) **hiçbir ortak alan taşımıyor**. `tsconfig.json` `strict: true` olduğuna göre CI'daki `tsc --noEmit` adımının şu anda kırmızı olması gerekir — ya CI kırmızı ve kimse bakmıyor, ya da bu kontrol atlanıyor. Her iki durumda da prod build `ignoreBuildErrors` sayesinde sessizce geçiyor.

### Y5. `/embed/faiz` widget'ı kendi güvenlik başlıklarıyla bloklanıyor
`web/components/embed-kodu.tsx` kullanıcıya "bu aracı sitenize ekleyin" diye `<iframe>` kodu kopyalatıyor (bilinçli bir backlink stratejisi), ama `web/middleware.ts` global `frame-ancestors 'self'` CSP'si ve `web/next.config.mjs`'deki `X-Frame-Options: SAMEORIGIN` bu yolu istisna tutmuyor. Özellik fiilen çalışmıyor.

### Y6. Giriş/kayıt akışında brute-force koruması yok
`web/lib/auth/config.ts` Credentials provider'ı sadece `bcrypt.compare` yapıyor; rate-limit, CAPTCHA veya hesap kilitleme yok. Backend'deki `api/rate_limit.py` bu akışı kapsamıyor (o, FastAPI tarafındaki AI uçları için).

### Y7. API endpoint testi sıfır **[✓]**
30 router'ın (auth, billing, arama, uyap, admin, publisher dahil) hiçbiri `TestClient`/`httpx` ile test edilmiyor. Frontend'de de hiçbir test dosyası yok (`jest`/`vitest`/`playwright` bağımlılığı bile yok). Coverage ölçülmüyor (`pytest-cov` yok).

### Y8. Staging ortamı yok, CI ile CD birbirinden bağımsız
`cloudbuild.yaml` doğrudan production'a build+deploy ediyor. `.github/workflows/ci.yml` sadece lint/test/build yapıyor ve deploy'u tetiklemiyor — yani CI kırmızıyken bile Cloud Build prod'a çıkabilir. Branch protection/CODEOWNERS dosyası repoda yok. Lint zaten `ruff check ... || true` ile hiçbir zaman CI'ı kırmıyor; Python tarafında mypy/pyright yok.

### Y9. Migration yönetimi kırılgan
Alembic/Flyway yok; 33 numaralı SQL dosyası `scripts/init_db.py` içindeki sabit listeyle uygulanıyor. **Uygulanmış migration'ları izleyen tablo yok** — script her çalıştığında hepsini yeniden dener. `02_rls.sql` ve `09_rls_fix_recursion.sql` içindeki `CREATE POLICY` ifadelerinde koruma yok; `apply_migration` `DuplicateObjectError`'ı yakalayıp "atlandı" diyor, ama dosya tek transaction'da çalıştığı için **dosyanın ortasında bir duplicate hatası çıkarsa o dosyadaki yeni statement'lar da geri alınır ve sessizce "OK" raporlanır**. Downgrade/rollback betiği hiç yok. `11_generated_documents.sql` ile `11_waitlist.sql` numara çakışıyor.

### Y10. DR planı hiç tatbik edilmemiş
`DR_RUNBOOK.md` §4'teki tatbikat tablosu boş: `_(ilk tatbikat — doldurulacak)_`. PITR/restore prosedürlerinin gerçekten çalıştığı hiç doğrulanmamış. Ayrıca `MASTER_ENCRYPTION_KEY` rotasyonu için doküman "re-wrap script'i olmadan yapma" diyor ama **böyle bir script repoda yok** — rotasyon fiilen imkânsız. Haftalık DB export'unun Cloud Scheduler otomasyonu da `setup_gcp.sh` içinde kurulmuyor.

### Y11. Hibrit arama, reranking, chunk→karar toplama yok
`services/rag.py` saf vektör araması yapıyor. `rag_chunks.document` için `tsvector`/GIN full-text indeksi yok. Hukuki metinlerde "İİK 67/1", "2023/1234 E." gibi **tam eşleşme gerektiren** aramalarda saf semantik arama zayıf kalır. Ayrıca aynı karardan gelen birden fazla chunk tekilleştirilmiyor/gruplanmıyor (MMR/çeşitlilik yok) — top-5 sonuç aynı kararın 3 parçası olabilir. HNSW indeksi varsayılan parametrelerle (`m`, `ef_construction` belirtilmemiş), `hnsw.ef_search` hiç ayarlanmıyor.

### Y12. Karar hiyerarşisi (bozma/onama) hiç modellenmemiş
Depoda `bozma`/`onama`/`HGK` gibi terimlerle bir geçerlilik takibi yok. Sonradan bozulmuş veya içtihadı birleştirme kararıyla geçersiz kalmış bir karar hâlâ yaşayan emsal gibi sunulur.

### Y13. NER tabanlı isim maskeleme varsayılan kapalı
`services/pii_redaction.py:80-83` — `PII_NER_MODEL` ortam değişkeni boşsa NER katmanı devre dışı; yalnızca rol-bağlamlı heuristik çalışıyor ("Davacı Ahmet Yılmaz" yakalanır, bağlamsız geçen bir tanık ismi yakalanmaz). Kodun kendi yorumu da "eksiksiz DEĞİLDİR" diyor. Projenin yol haritası bunu P0 olarak işaretlemiş; prodda aktif olup olmadığı repodan doğrulanamıyor.

### Y14. Karar tarihi / esas-karar no ayrıştırma naif
`common/normalize.py:40-55` metindeki **ilk** eşleşmeyi alıyor. Karar metinlerinde başka kararlara atıf çok yaygın olduğundan ("Yargıtay 12. HD'nin 2019/123 E. kararında..."), yanlış esas no/tarih metadata olarak kaydedilebilir. Bu alanlar `pipelines/chunk.py:144-147` üzerinden chunk metadata'sına, oradan LLM'e "somut metadata" olarak veriliyor.

### Y15. Konteynerler root kullanıcıyla çalışıyor
`Dockerfile`, `Dockerfile.api`, `web/Dockerfile` — üçünde de `USER` direktifi yok. `Dockerfile` ve `Dockerfile.api` tek aşamalı (build-essential final imajda kalıyor). `Dockerfile.api` (asıl prod imajı) `HEALTHCHECK` içermiyor.

### Y16. Sonsuz retry riski (scraper kuyruğu)
`common/job_queue.py:67-74` — `mark_failed(retry=True)` `attempts` sayacını artırıyor ama **hiçbir yerde üst sınır kontrol edilmiyor**. `scrapers/danistay.py:358` ve `scrapers/yargitay.py:362`'de "empty"/"rate-limit" durumlarında sürekli pending'e dönülüyor; kalıcı olarak boş dönen bir kayıt sonsuza dek kuyrukta döner.

### Y17. LLM token/maliyet takibi yok
`services/embeddings.py:105-122` embedding kullanımını `embedding_usage_log`'a yazıyor, ama `llm/provider.py`'deki `generate()`/`generate_stream()` yanıttaki `usage.input_tokens`/`output_tokens` alanlarını hiç okumuyor. Admin panelindeki "AI maliyet tahmini" gerçek token verisine değil, tahmine dayanıyor.

---

## 5. ORTA ÖNCELİKLİ EKSİKLER (P2)

**Backend / mimari**
- **İki ayrı, tutarsız rate limiter.** `api/deps.py`'deki in-memory `rate_limit`, `api/kota.py`'nin yanında paralel çalışıyor; XFF'e bakmıyor (LB arkasında tüm kullanıcılar tek kovayı paylaşır), worker başına ayrı bellek tutuyor (limit fiilen 4 katı), `_rate_buckets` hiç temizlenmiyor (bellek sızıntısı).
- **Yapısal log + correlation ID yok.** `api/main.py:28-32` düz metin log; depoda `request_id`/`X-Request-Id` hiç geçmiyor. Bir hatayı DB sorgusu, LLM çağrısı ve audit kaydıyla ilişkilendirmek mümkün değil.
- **Router'lara gömülü iş mantığı.** `admin.py` 1198, `billing.py` 987, `me.py` 711, `uyap.py` 708 satır. Tenant plan-limit güncelleme bloğu **üç ayrı yerde** tekrarlanıyor (`admin.py:817-842`, `billing.py:34-54`, `billing.py:319-343`) — yeni plan eklendiğinde biri unutulursa admin ve webhook farklı limitler yazar.
- **`require_admin` dört router'da kopya-yapıştır** (`admin.py`, `icerik.py`, `newsletter.py`, `waitlist.py`); `api/auth.py`'de merkezi bir `require_role` yok.
- **CORS `allow_methods` yalnızca GET/POST/OPTIONS** (`api/main.py:179`) ama API PATCH/PUT/DELETE uçları içeriyor. Şu an Next.js proxy deseni bunu maskeliyor.
- **API versiyonlama yok.** Yalnız `v1.py` (public API) versiyonlu; iç API'nin tamamı versiyonsuz — breaking change frontend ile senkron deploy gerektiriyor.
- **Bazı admin uçları ham `dict` body alıyor** (`admin.py:1074`, `:1112`) — OpenAPI şeması "any JSON" gösteriyor, kontrat yok.
- **LLM çağrılarında retry/circuit breaker yok.** iyzico çağrılarında backoff var (iyi örnek), LLM'de yok.
- **Upload idempotency yok.** `api/routers/uyap.py` `/upload` uçlarında istemci retry'ında aynı dosya iki kez işlenip iki kez embedding maliyeti doğabilir.
- **Webhook idempotency `iyzico_token IS NULL` durumunda çalışmıyor** (`billing.py:820-827`) — `NULL = NULL` asla true olmaz.

**Frontend**
- **React Query kurulu ama kullanılmıyor.** `QueryClientProvider` yapılandırılmış ama `useQuery`/`useMutation` hiçbir yerde yok; 54 dosyada ham `fetch` + elle `useState/useEffect` tekrarlanıyor. `web/lib/use-plan.ts` `window.dispatchEvent(new Event("plan:refresh"))` ile elle invalidation kurmuş — react-query'nin bedava verdiği şey.
- **`loading.tsx` hiç yok, `error.tsx` sadece kökte, `global-error.tsx` yok.** `panel/layout.tsx` gibi `await auth()` + DB sorgusu yapan server component'lerde gecikme boş ekran demek.
- **Çift sitemap üretimi.** `next-sitemap` postbuild'i `public/sitemap.xml`'i statik üretiyor ve elle yazılmış `app/sitemap_index.xml/route.ts`'i gölgeleyebiliyor; `next-sitemap.config.js`'deki fallback domain (`hukukemsal.tr`) diğer tüm dosyalardaki (`hukukcuyapayzekasi.com`) ile tutarsız.
- **CSP'de `'unsafe-inline'` + `'unsafe-eval'`** (`web/middleware.ts`) — XSS koruması fiilen çok zayıf. Nonce tabanlı CSP'ye geçilebilir.
- **`next/image` hiç kullanılmıyor.** `next.config.mjs`'deki avif/webp yapılandırması işlevsiz; blog kapak görselleri çıplak `<img>` ile (LCP riski).
- **Kullanılmayan bağımlılıklar:** `zustand`, `@radix-ui/react-select`, `@radix-ui/react-label` hiç import edilmiyor.
- **`recharts` statik import** — `next/dynamic` depoda hiç kullanılmıyor.
- **19 yerde `any`**, `zod` yok — AI yanıtları runtime doğrulamadan geçmiyor.
- **`<select>` elemanlarında erişilebilir isim yok** (`emsal-arama/arama-form.tsx:155,161,172`).
- **Ölü kod:** `lib/auth/config.ts`'teki `authorized()` callback'i hiç çalışmıyor (özel `middleware.ts` kullanılıyor) ve var olmayan `/app` yolunu koruyormuş gibi görünüyor.
- **Kayıt endpoint'inde e-posta format doğrulaması yok** (`app/api/auth/register/route.ts`).
- **Onay modalında focus trap eksik** (`components/confirm-dialog.tsx`).

**Veri / RAG**
- Chunking karakter bazlı (1000/150), token bazlı değil ve "GEREKÇE"/"SONUÇ" gibi hukuki bölüm başlıklarını tanımıyor (`pipelines/chunk.py:30-73`).
- Artımlı güncelleme yok — hiçbir scraper'da "şu tarihten sonrakileri getir" cursor'ı yok.
- Dedup yalnızca birebir ID eşleşmesi (`pipelines/export_final.py:26`); içerik hash'i / near-duplicate tespiti yok.
- `embedding_model` kolonu yok — model değişip `--recreate` unutulursa farklı semantik uzaylardan vektörler karışır ve benzerlik anlamsızlaşır.
- Query expansion yok; eş anlamlı hukuki terim genişletmesi ("haciz" ↔ "icra takibi") yapılmıyor.
- Prompt'lar Python string sabiti olarak gömülü; versiyonlama, A/B, rollback yok.
- `common/anonymize.py` (scraper tarafı) ile `services/pii_redaction.py` (servis tarafı) iki paralel PII sistemi; public karar listesi filtresi yalnızca regex tabanlı olanı kullanıyor — **halka açık karar sayfalarında kişi adı denetimi yapılmıyor**.
- `analytics/coverage.py` yalnızca `data/cleaned/*.jsonl` dosyalarına bakıyor, gerçek `rag_chunks` durumunu/tazeliğini göstermiyor.

**Altyapı / uyum**
- `.env.example:49-50` içinde placeholder değil, **gerçek formatlı sandbox iyzico anahtarları** var. `infra/gcp/create_secrets.py` gitignore'da değil ve içine gerçek anahtar yazılacak şekilde tasarlanmış; secret-scanning/pre-commit hook yok.
- Metrik (Prometheus) ve tracing (OpenTelemetry) yok; Sentry opsiyonel ve prodda aktif olduğu doğrulanamıyor. Harici uptime izleme (`services/uptime_monitor.py` kendi sınırını itiraf ediyor) hâlâ checklist maddesi.
- Yük testi (k6/locust) ve SAST/DAST (bandit, ZAP, Dependabot, CodeQL, Trivy) hiç yok.
- Grace period / dunning yok — `SUBSCRIPTION_PAYMENT_FAILED` gelir gelmez tenant anında `free`'ye düşüyor (`billing.py:921-960`).
- Kart güncelleme self-servis akışı yok; yıllık plan yok; proration yok; otomatik trial yok (180 günlük beta tamamen elle yürütülüyor).
- Cayma hakkı feragati ödeme anında ayrı bir onay kutusuyla alınmıyor (`abonelik-panel.tsx:340-482`) — "iade yapılmaz" politikasının hukuki dayanağını zayıflatabilir.
- Avukat–müvekkil verisi için ayrı **Veri İşleyen Sözleşmesi (DPA)** yok; Avukatlık Kanunu m.36 (meslek sırrı) boyutu metinlerde ele alınmamış.
- Saklama süreleri "makul bir süre" gibi belirsiz ifadelerle yazılmış (Gizlilik Politikası md. 6).
- "Verilerimi indir" (KVKK m.11 taşınabilirlik) self-servis endpoint'i yok.
- Açık rıza "Platform'u kullanarak açık rızanızı vermiş olursunuz" formülasyonuyla alınıyor (`gizlilik/page.tsx:143`) — KVKK'nın aradığı özgür/spesifik opt-in'den farklı; hukukçu görüşü gerekli.
- Chrome eklentisi gerçek UYAP DOM'una göre hiç kalibre edilmemiş (`extension/README.md:11` kendi itirafı).

---

## 6. DÜŞÜK ÖNCELİKLİ / TEKNİK BORÇ

- **README bayat.** Kök `README.md` hâlâ projeyi "scraper kümesi" olarak tanıtıyor; SaaS, ödeme, panel, RAG'dan hiç bahsetmiyor. Yeni bir geliştirici için tamamen yanıltıcı.
- **Streamlit prototipi (`app/`, 9 sayfa) hâlâ kökte** ve `requirements.txt` üzerinden `sentence-transformers` gibi ağır bağımlılıkları taşıyor.
- **Dokümantasyon enflasyonu:** 38 markdown dosyası, çoğu birbirini tekrar eden ve bayat (`PRODUCTION_CHECKLIST.md`'nin bayat olduğu `LANSMAN_OPERASYON_CHECKLIST.md` başında itiraf edilmiş). `PHASE1_*`, `PHASE2_*` dosyaları arşivlenmeli.
- **Depoda 10 commit'lenmemiş değişiklik var** (billing, kota, abonelik, fiyatlandırma dosyaları) — yarım kalmış bir iş var gibi görünüyor.
- `docker-compose.yml`'de kaynak limiti yok.
- `scripts/init_db.py --reset` prodda yanlışlıkla çalışırsa tüm şemayı siler; koruma yalnızca interaktif onay.
- `web/Dockerfile` standalone çıktı yerine tüm `node_modules`'ü kopyalıyor (prod'da `/giris` yönlendirme döngüsü yaşandığı için bilinçli tercih, ama imaj şişkinliği olarak borç).
- Fiyat kartlarında "KDV dahil" ibaresi yok (yalnızca sözleşme metninde geçiyor).
- `queries/keywords.yaml`'daki `secondary` ve `laws` listeleri AYM ve Yargıtay scraper'larında hiç kullanılmıyor — kapsam kaybı.
- `scrapers/base.py` çok minimal; rate-limit/backoff mantığı 3 scraper'da kopyalanmış.

---

## 7. "OLSA İYİ OLUR" ÖZELLİKLER

Etki × Efor (S ≤ 2 gün · M 3–7 gün · L 1–3 hafta · XL 1 ay+)

### 7.1 Ürün / iş modeli

| # | Özellik | Neden | Etki | Efor |
|---|---|---|---|---|
| 1 | **Ekip/koltuk yönetimi** (davet, rol, ortak dosya, ortak şablon kütüphanesi) | Zaten satılan bir vaat; kurumsal satışın kilidi | Yüksek | M–L |
| 2 | **E-fatura entegrasyonu** (Paraşüt / Logo / Foriba) | Vaat ediliyor, çalışmıyor; kurumsal müşteri zorunlu ister | Yüksek | M |
| 3 | **Plan yükseltme/düşürme + proration** | Çift faturalamayı kapatır, doğal upsell hunisi kurar | Yüksek | S–M |
| 4 | **Yıllık plan (%15–20 indirimli)** | Nakit akışı + churn düşüşü; `PLAN_PRICING`'e interval alanı eklemek kadar basit | Orta | S |
| 5 | **Grace period (3–7 gün) + kademeli dunning** | Anında `free`'ye düşürmek yerine kart güncelleme fırsatı — gelir kurtarır | Orta | S |
| 6 | **Kart/ödeme yöntemi güncelleme self-servisi** | Başarısız tahsilat sonrası churn'ü azaltır | Orta | S–M |
| 7 | **Referans/davet programı** ("2 meslektaşını davet et, sıranı öne al") | Hukuk camiası küçük ve ağızdan ağıza güçlü; bekleme listesi modunda bugün bile devreye alınabilir | Orta | S |
| 8 | **Otomatik trial + trial→ücretli geçiş akışı** | 180 günlük beta şu an tamamen elle yürütülüyor, ölçeklenmez | Orta | M |

### 7.2 Ürün derinliği (farklılaştırıcı)

| # | Özellik | Neden | Etki | Efor |
|---|---|---|---|---|
| 9 | **Dava dosyası bazlı çalışma alanı** — emsal + dilekçe + karşı argüman + hatırlatıcı tek ekranda | Araçlar arası geçişi ortadan kaldırır, günlük kullanım alışkanlığı yaratır | Yüksek | M–L |
| 10 | **Duruşma/süre takvimi + e-tebligat entegrasyonu** | Avukatın en büyük günlük riski kaçırılan süre; e-tebligatı otomatik hatırlatıcıya bağlamak "öldürücü özellik" | Yüksek | L |
| 11 | **UYAP otomatik senkron** (dönemsel çekme) | Rakiplerin çoğu manuel yüklemede kalıyor; gerçek farklılaştırıcı — ancak e-imza/KVKK riski nedeniyle hukuki görüş şart | Yüksek | L–XL |
| 12 | **Karar geçerlilik göstergesi** ("bu karar bozuldu / onandı / HGK ile çelişiyor") | Hukuk ürününde en değerli güven sinyali; Westlaw/Lexis'in KeyCite/Shepard's muadili | Yüksek | L |
| 13 | **Atıf ağı** — kararın hangi kararlara atıf yaptığı / hangileri tarafından atıf aldığı | Emsal araştırmasını derinleştirir, SEO için de zengin iç bağlantı üretir | Orta–Yüksek | M–L |
| 14 | **Word eklentisi (Office Add-in)** | Avukat dilekçeyi Word'de yazar; ürünü onun ortamına taşımak kullanım sıklığını katlar | Orta–Yüksek | L |
| 15 | **WhatsApp/Telegram hatırlatıcı kanalı** | E-postadan çok daha yüksek açılma oranı; zaman-kritik duruşma bildiriminde kritik | Orta | M |
| 16 | **PWA + push bildirim** | Mobil kullanım; planlanmış ama yapılmamış | Orta | M |
| 17 | **Toplu veri exportu ("Tüm verilerimi indir")** | KVKK m.11'i otomatikleştirir + kurumsal güvence | Düşük–Orta | S |

### 7.3 Teknik altyapı

| # | Özellik | Neden | Etki | Efor |
|---|---|---|---|---|
| 18 | **RAG eval seti + CI'da kalite eşiği** | Yanlış emsal riskini ölçülebilir hale getirir; hukuk ürününde pazarlık konusu değil | Yüksek | M |
| 19 | **Hibrit arama (pgvector + Postgres FTS) + cross-encoder rerank** | "İİK 67/1", "2023/1234 E." gibi tam eşleşmeleri kurtarır; retrieval kalitesinde en büyük tekil sıçrama | Yüksek | M |
| 20 | **API entegrasyon test paketi** (`TestClient` ile auth/billing/arama/uyap) | 30 router'ın tamamı test edilmemiş durumda | Yüksek | M |
| 21 | **Staging ortamı + CI→CD kapısı + branch protection** | Prod'a doğrudan deploy şu anda tek koruma katmanı olan insan dikkatine bağlı | Yüksek | M |
| 22 | **Yapısal JSON log + correlation ID + Sentry tag** | Prod hata ayıklamasının temel şartı | Orta–Yüksek | S |
| 23 | **Alembic'e (veya en azından migration ledger tablosuna) geçiş** | Şema drift'i ve sessiz atlanan migration riskini kapatır | Orta–Yüksek | M |
| 24 | **LLM token/maliyet loglama** (`llm_usage_log`) | Birim ekonomi görünürlüğü; fiyatlandırma kararlarının temeli | Orta | S |
| 25 | **Playwright ile 5 kritik akış e2e** (giriş, arama, dilekçe, ödeme callback, UYAP yükleme) | Frontend'de sıfır test var | Orta | M |
| 26 | **Prompt kütüphanesi + versiyonlama** (dosya/DB tabanlı, A/B destekli) | Çıktı kalitesini ölçülebilir şekilde iyileştirmenin ön koşulu | Orta | M |
| 27 | **Ürün analitiği (PostHog self-hosted) + huni/kohort** | GA4 sayfa görüntülemenin ötesinde "neden dönüşmüyorlar" sorusunu cevaplar | Orta | M |
| 28 | **Feature flag altyapısı** | `SATIS_ACIK` gibi elle bayrakları merkezileştirir, A/B testin önünü açar | Düşük–Orta | S |
| 29 | **Dependabot + CodeQL + pip-audit/npm audit + gitleaks** | Bedava güvenlik katmanı; şu an hiçbiri yok | Orta | S |

---

## 8. Önerilen Yol Haritası

### Hemen (satış açılmadan — 1–2 hafta)
1. K1 · API anahtarı `is_active` kontrolü (yarım saatlik iş, yetkilendirme deliği)
2. K11 · CI'da tüm testleri koştur (tek satır değişiklik)
3. K5 · Hukuki metinlerdeki şirket bilgisi placeholder'ları + hukukçu incelemesi
4. K3 · E-fatura: ya entegrasyon ya pazarlama metninin düzeltilmesi
5. K2 · Team planı: ya koltuk yönetimi ya planın geçici olarak satıştan kaldırılması
6. K4 · Plan değişiminde çift abonelik kontrolü
7. K10 · `purge_deleted.py` için Cloud Scheduler
8. Y1 · XFF güvenilir proxy doğrulaması · Y2 · `/api/health`'e `SELECT 1`
9. Y13 · NER modelinin prodda aktifleştirilmesinin doğrulanması

### 30 gün
10. K6 · RAG benzerlik eşiği + "yeterli emsal yok" mesajı
11. K8 · Esas/karar no grounding doğrulaması
12. K9 / #18 · Altın standart eval seti (50–100 soru)
13. Y7 / #20 · Auth, billing, arama, uyap için entegrasyon testleri
14. Y4 · Tip sözleşmesi düzeltmesi + `tsc --noEmit`'in gerçekten kapı olması
15. Y8 / #21 · Staging + branch protection + CI→CD kapısı
16. #22 · Yapısal log + correlation ID

### 60–90 gün
17. K7 · Veri kapsamı: UYAP Emsal scraper'ı + daire/konu genişletme (veya konumlandırmanın daraltılması)
18. Y11 / #19 · Hibrit arama + rerank + MMR
19. Y12 / #12 · Karar geçerlilik (bozma/onama) modeli
20. #1 · Ekip/koltuk yönetimi
21. Y9 / #23 · Migration ledger / Alembic
22. Y10 · İlk DR tatbikatı + key re-wrap script'i
23. #9 · Dava dosyası bazlı çalışma alanı

---

## 9. Doğrulama Notları

- **[✓]** işaretli tespitler bu raporun yazımı sırasında ilgili dosyalar açılıp elle teyit edildi: `api/routers/v1.py` (users JOIN yokluğu), `api/main.py` health endpoint'i, `api/rate_limit.py` + `api/audit.py` XFF kullanımı, `.github/workflows/ci.yml` pytest dosya listesi, `services/rag.py` SQL sorgusu (eşik yokluğu), `tenant_members` INSERT arama sonucu, `invoice_number` yazma arama sonucu, `web/next.config.mjs` ignore bayrakları, `web/lib/api.ts` ↔ `web/app/emsal-arama/arama-form.tsx` tip uyuşmazlığı, `web/tsconfig.json` (`strict: true`), `loading.tsx`/test dosyalarının yokluğu.
- Diğer tespitler beş bağımsız denetim ekseninde kod okunarak elde edildi; her biri dosya (ve mümkün olduğunda satır) referansı taşıyor.
- Ölçüm anı: HEAD `fa70dc0`. Depoda **10 commit'lenmemiş değişiklik** vardı (`api/rate_limit.py`, `api/routers/admin.py`, `api/routers/billing.py`, `api/routers/uyap.py`, `iyzico_plans.json`, `services/billing.py`, `web/app/fiyatlandirma/page.tsx`, `web/app/panel/ayarlar/abonelik/abonelik-panel.tsx`, `web/components/onboarding-tur.tsx`, `web/lib/use-plan.ts`) — bu rapor commit'lenmiş HEAD'i baz alır, dolayısıyla bazı bulgular çalışma kopyanızda çoktan giderilmiş olabilir.

---

## 10. Kapanış Değerlendirmesi

Bu proje, tek kişilik/küçük ekip ölçeğinde üretilmiş bir işten beklenenin epey üzerinde bir mühendislik disiplini gösteriyor — özellikle RLS izolasyonu, envelope encryption, kota atomikliği ve ödeme webhook'u güvenliği, birçok olgun SaaS'ta bile bu kadar düşünülmüş değildir.

Asıl risk teknik yeterlilikte değil, **doğrulama ve tutarlılıkta**: satılan bazı özelliklerin kodda karşılığı yok, ürünün en kritik çıktısı (emsal kararın doğruluğu) hiçbir otomatik ölçüme tabi değil ve prod'a giden yolda insan dikkati dışında bir kapı bulunmuyor. Yukarıdaki "Hemen" listesindeki dokuz madde — çoğu birkaç saatlik iş — bu risklerin büyük kısmını kapatır; asıl orta vadeli yatırım ise veri kapsamı ve retrieval kalitesine yapılmalı, çünkü bir hukuk RAG ürününün rekabet ettiği yer nihayetinde orası.
