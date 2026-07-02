# Analiz ve Yol Haritası — Temmuz 2026

> Kod tabanı, mevcut plan dokümanları ve altyapının bütünsel analizi.
> Kapsam: lansman öncesi eksikler + uzun vadeli özellik yol haritası.
> Tarih: 2026-07-01 · Durum: Bekleme listesi (lansman) modu aktif (`web/lib/satis-modu.ts`)

---

## ✅ UYGULAMA DURUMU (güncelleme: 2026-07-02)

Kodla yapılabilen işlerin büyük bölümü UYGULANDI:

- **PII (1.9–1.13) TAMAM:** redact-before-embed (`tenant_rag.py` + `redact_for_embedding`),
  NER pencereleme, `unredact_safe`, PLATE/daire-atfı düzeltmesi, CI'da koşan sızıntı
  testi (`tests/test_pii_leak_e2e.py`, 7/7 yeşil — üstelik gerçek bir maskeleme hatası
  yakalayıp düzelttirdi: isim deseni satır sonu aşıyordu). Mevcut belgeler için
  `scripts/reindex_tenant_docs.py` hazır — **prod'da bir kez çalıştırılmalı.**
- **Güvenilirlik TAMAM:** hatırlatıcı retry/backoff (migration 23), atomik kota
  (`atomik_kota_kullan` — advisory lock, TOCTOU kapatıldı), GitHub Actions CI
  (`.github/workflows/ci.yml`), purge'da pgvector chunk + tenant_documents temizliği.
- **Faz 0 TAMAM (kod tarafı):** mesafeli satış + iade politikası sayfaları (footer +
  sitemap dahil; [ŞİRKET ÜNVANI] placeholder'ları DOLDURULMALI), DR_RUNBOOK.md,
  LANSMAN_OPERASYON_CHECKLIST.md.
- **Faz 2 TAMAM:** onboarding turu, kullanım panosu (GET /api/me/kullanim), NPS anketi
  (migration 22), waitlist CRM (migration 24; davet e-postası + ?davet= kayıt
  entegrasyonu + admin panel filtre/çoklu seçim/davet), admin audit UI (zaten vardı).
- **Faz 3 (seçili) TAMAM:** dilekçe şablon kütüphanesi (migration 25, 5 platform
  şablonu + kullanıcı şablonları, /panel/sablonlar), emsal alarmları (mevcut
  saved_search_alerts + job'a UI/router eklendi, /panel/alarmlar), hatırlatıcı .ics
  takvim exportu (tekil + toplu).

**Kalan operasyonel işler (insan gerektirir — bkz. LANSMAN_OPERASYON_CHECKLIST.md):**
prod secrets, Resend SMTP, iyzico canlı başvurusu, embedding tamamlama, Sentry/uptime,
migration'ların (21–25) prod'da koşulması, `reindex_tenant_docs.py`, NER modeli
(`PII_NER_MODEL` + `PII_BLOCK_FOREIGN_LLM_WITHOUT_NER=1`) ve hukukçu incelemeleri.

**Uygulanmayan Faz 3 kalemleri (sonraki turlar):** UYAP oto-senkron, Team işbirliği,
WhatsApp/Telegram kanalları, public API key yönetimi UI, PWA/push, Redis cache,
LLM streaming deploy'u, Yargıtay arşiv genişletme.

---

## 1. Yönetici Özeti

Platform teknik olarak olgun: 14 API router, 58 frontend rotası, RLS ile çok kiracılı
izolasyon, 3 katmanlı PII maskeleme, pgvector'a taşınmış RAG (10.022 karar / 187K chunk),
iyzico entegrasyonu (imza doğrulama + idempotency) ve çalışan bir hatırlatıcı servisi mevcut.

Lansmanı engelleyen konular kod değil, ağırlıklı olarak **operasyon ve hukuk** tarafında:
prod secrets, prod SMTP, mesafeli satış sözleşmesi, LLM çıktılarının hukuki incelemesi ve
embedding'lerin tamamlanması. Kod tarafındaki en önemli riskler ise kota uygulamasının
"yumuşak" olması, hatırlatıcı gönderiminde retry olmaması ve CI/e2e test eksikliği.

**Önerilen strateji:** Bekleme listesi modunda hemen aç (P0-A), 1-2 hafta içinde
güvenilirlik işlerini bitir (P0-B/P1), kullanıcı alışkanlık verisi toplarken satışı aç.

---

## 2. Mevcut Durum — Güçlü Yönler

- **Backend:** FastAPI + asyncpg, Pydantic v2, servis katmanı ayrımı temiz.
- **Güvenlik:** RLS `FORCE` + iki rol (app_user/app_service), recursion fix'i yapılmış,
  parametrized queries, webhook imza doğrulama + iyzico'dan otoritatif re-query,
  tenant başına DEK + crypto-shred (KVKK m.7).
- **PII:** regex + sezgisel + opsiyonel NER; roundtrip testleri geçiyor.
- **Veri:** Yargıtay 4.4K, Danıştay 3.8K, HUDOC 1.8K, AYM; pgvector HNSW indeks.
- **Frontend:** Panel + public ikili araç seti, plan gating (`usePlan`/`ProUpsell`) tutarlı,
  dark mode, SEO (metadata, JSON-LD, sitemap), cookie consent, hata sınırları.
- **Yasal sayfalar:** gizlilik, KVKK, kullanım şartları, yasal uyarı mevcut.
- **Dokümantasyon:** Faz raporları, güvenlik ve deploy rehberleri ayrıntılı.

> Not: PGVECTOR_GOC_PLANI.md ve PRODUCTION_CHECKLIST.md'deki "Chroma" referansları
> bayat — göç tamamlanmış, kodda Chroma kalmamış. Dokümanlar güncellenmeli.

---

## 3. Tespit Edilen Eksikler

### 3.1 P0-A — Bekleme listesi modunda bile lansmanı engelleyenler

| # | Eksik | Neden kritik | Nerede |
|---|-------|--------------|--------|
| 1 | Prod secrets üretimi (NEXTAUTH_SECRET, MASTER_ENCRYPTION_KEY, SERVICE_DATABASE_URL) | Dev anahtarla açılan üretim = tüm oturum ve şifreleme güvenliği riskte. MASTER_KEY kaybı = tüm tenant verisi okunamaz | `infra/gcp/create_secrets.py` (placeholder'lar dolu değil) |
| 2 | Prod SMTP (Resend/Postmark/SES) | E-posta doğrulama, şifre sıfırlama ve hatırlatıcılar Mailpit'te — üretimde hiçbir mail gitmez | `services/email.py`, env SMTP_* |
| 3 | ALLOWED_ORIGINS prod domain | CORS localhost'ta; prod'da API çağrıları kırılır | api config |
| 4 | Embedding tamamlanması (187K chunk, ~%50) | Arama kalitesi eksik veriyle düşük | `scripts/` embed job — GPU'lu geçici makine öneririm |
| 5 | Uptime monitoring + Sentry DSN | Açılış günü sorunları görünmez olur | Sentry env, UptimeRobot/Better Stack |
| 6 | KVKK aydınlatma metninin hukukçu onayı | Yasal zorunluluk | `web/app/kvkk` |

### 3.2 P0-B — Satışı açmadan önce zorunlu

| # | Eksik | Detay |
|---|-------|-------|
| 1 | **Mesafeli satış sözleşmesi + cayma/iade politikası sayfası YOK** | iyzico canlı başvurusu ve 6502 sayılı kanun gereği zorunlu. `grep mesafeli/cayma/iade` → 0 sonuç |
| 2 | iyzico prod anahtarları + canlı başvuru | Sandbox'ta; canlı onay süreci 1-2 hafta sürebilir, **şimdiden başlatılmalı** |
| 3 | LLM çıktılarının (dilekçe, ihtarname, özet, sözleşme analizi) hukuki incelemesi | "Hukuki tavsiye değildir" uyarıları + çıktı kalite kontrolü |
| 4 | Kota uygulamasının sertleştirilmesi | `api/rate_limit.py` kontrolleri advisory; DB seviyesinde güvence yok (bkz. 3.3-#2) |
| 5 | **UYAP embedding PII sızıntısının kapatılması** | Belge chunk'ları ham haliyle Google Embedding API'sine gidiyor (bkz. 3.5-#1). UYAP erişimli beta kullanıcı varsa hemen; yoksa UYAP'ı açmadan önce mutlaka (Faz 1 / 1.9) |

### 3.3 P1 — Yüksek öncelik (ilk 2-3 hafta)

1. **Hatırlatıcı gönderiminde retry/backoff yok** (`services/hatirlatici_gonderim.py`):
   SMTP geçici hatasında kayıt `failed`e düşüyor, bir daha denenmiyor. Tek instance
   içi loop — pod çökerse hatırlatıcılar bekler. Kullanıcı bir duruşma hatırlatıcısını
   kaçırırsa güven kaybı büyük olur.
2. **Kota "soft" enforcement:** kullanım sayacı Python'da; eşzamanlı isteklerde veya
   kontrol atlanırsa aşım mümkün. `usage_events` üzerinde atomik sayaç/constraint yok.
3. **CI pipeline yok:** testler (10 dosya, data/crypto odaklı) elle koşuluyor; API e2e testi hiç yok.
   Bugünkü `soru is not defined` benzeri hatalar build-time'da bile yakalanmıyor →
   en azından `tsc --noEmit` + `next build` + pytest'i PR'da koşan bir GitHub Actions şart.
4. **Rate limit in-memory:** birden çok instance'ta limitler ayrışır; Redis'e taşınmalı
   (ya da tek instance garantisi dokümante edilmeli).
5. **Backup/DR dokümantasyonu yok:** Cloud SQL otomatik yedek var ama restore prosedürü,
   MASTER_KEY saklama planı (Secret Manager + offline kopya) ve GCS tenant-storage
   yedeği tanımsız.
6. **Admin eksikleri:** audit log'lar DB'de ama görüntüleme UI'ı yok; admin rolü kodda
   hardcoded, UI'dan admin atanamıyor.
7. **Silinen dosyaların GCS'den temizlenmemesi:** soft-delete sonrası storage'da yetim
   dosyalar kalıyor (KVKK açısından da sorun).
8. **`purge_deleted.py` ve `update_faiz_oranlari.py` cron'a bağlanmamış** — elle koşuluyor.

### 3.4 P2 — Orta öncelik

- Redis cache (LLM yanıtları, popüler aramalar) — maliyet ve gecikme düşürür.
- LLM streaming kodda var ama deploy edilmemiş — algılanan hızı ciddi artırır.
- Export (PDF/.docx/.udf) kısmen stub — dilekçe çıktısının UDF (UYAP formatı) desteği
  avukatlar için önemli fark.
- Yargıtay arşivi 386K karardan yalnızca ~4.4K'sı çekilmiş (captcha engeli);
  2captcha entegrasyonu veya resmi veri anlaşması değerlendirilmeli.
- WhatsApp/Telegram hatırlatıcı kanalları "yakında" rozetinde.
- Emsal alarm job'ı (`scripts/emsal_alarm_job.py`) TODO durumunda.
- Hata yanıtı formatı tutarsız (bazı endpoint'ler str, bazıları dict döndürüyor).
- `billing.py` webhook mantığı 150+ satır — servise ayrılmalı.
- Büyük form bileşenleri (dilekce, ihtarname) alt bileşenlere bölünmeli.

### 3.5 UYAP → AI Anonimleştirme Mimarisi — Özel Denetim (2026-07-01)

**İstenen mimari:** Kullanıcı UYAP belgesini yükler → belge sistemde (şifreli) durur →
AI'a giden her şey anonimleştirilir → AI yanıtındaki placeholder'lar gerçek değerlerle
doldurulup kullanıcıya sunulur → **AI'a hiçbir şekilde kişisel veri gitmez.**

**Mevcut ve doğru kurulmuş olanlar:**

- Yükleme (`api/routers/uyap.py:/upload`): dosya tenant DEK'i ile şifreli saklanıyor,
  metin RLS'li DB'de, yükleme anında PII denetim raporu (`pii_audit`) tutuluyor. ✔
- AI sorgu akışı (`/sorgu`) tam istenen desen: context + soru `redact()` → LLM →
  yanıt `unredact()` → kullanıcıya gerçek değerlerle. ✔
- 3 katmanlı maskeleme (`services/pii_redaction.py`): regex (TCKN, IBAN, telefon,
  e-posta, kart, plaka) + heuristik isim/adres (rol bağlamlı) + opsiyonel NER.
  Placeholder haritası roundtrip testli. ✔
- Strict KVKK bayrağı: `PII_BLOCK_FOREIGN_LLM_WITHOUT_NER=1` → NER yoksa yurt dışı
  LLM çağrısı hiç yapılmıyor. ✔

**"Hiçbir şekilde PII gitmez" garantisini BUGÜN bozan boşluklar:**

1. **KRİTİK — Embedding yolu maskesiz:** `services/tenant_rag.py:index_document`
   chunk'ları ve `search_tenant` sorguyu HAM haliyle `services/embeddings.py`
   üzerinden **Google Embedding API'sine** gönderiyor (varsayılan
   `EMBEDDING_PROVIDER=google`). Yani belge LLM'e maskeli gidiyor ama yükleme
   anında embedding için Google'a maskesiz gidiyor. `uyap.py`'deki "local
   Chroma'da kalıyor, LLM'e gönderirken redact ederiz" yorumu pgvector göçünden
   kalma ve artık YANLIŞ.
2. **Varsayılan isim katmanı heuristik:** rol bağlamı ("Davacı X", "Av. Y") dışında
   geçen serbest isimler kaçabilir. NER modeli prod'da yapılandırılmamış, strict
   mod kapalı → garanti "en iyi çaba" seviyesinde.
3. **NER uzun metin sınırı:** transformers pipeline ~512 token keser; uzun UYAP
   belgelerinde sonraki sayfalar maskelenmeden kalabilir. NER pencereleme ile
   çağrılmalı.
4. **Unredact kırılganlığı:** LLM placeholder'ı biçimlendirirse (kalın, boşluk,
   satır kırılması) `unredact` birebir eşleşemez; kullanıcıya `<PERSON_ab12cd34>`
   sızabilir. Toleranslı eşleme + yanıt öncesi "kalan placeholder" taraması yok.
5. **PLATE regex yan etkisi:** `12 HD 2021` gibi daire/karar atıflarını plaka sanıp
   maskeleyebilir — gizlilik riski değil ama atıf kalitesini bozar.
6. **Tutarlılık denetimi:** redact, `karsi_argument` ve `kvkk` servislerinde var;
   kullanıcı metni alan TÜM LLM araçlarında (dilekçe, ihtarname, özet, denetim,
   sözleşme) aynı standart tek tek doğrulanmalı.

Çözüm işleri Faz 1 tablosuna eklendi (1.9–1.13); embedding sızıntısı UYAP erişimi
olan kullanıcı var olduğu sürece geçerli olduğundan **beta/satış öncesi zorunlu**
(P0-B #5) olarak da işaretlendi.

---

## 4. "Şu Olsa Daha İyi Olur" — Önerilen Özellikler

### 4.1 Bekleme listesi dönemine özel (şimdi — fırsat penceresi)

1. **Waitlist CRM'i:** Admin bekleme listesi paneline plan bazlı segmentasyon,
   toplu davet e-postası ve "davet kodu ile erken erişim" akışı. Satış açılınca
   hazır, sıcak bir liste olur.
2. **Referans programı:** "2 meslektaşını davet et, öne geç" — hukuk camiası küçük
   ve ağızdan ağıza güçlü; düşük maliyetli büyüme.
3. **Kullanım panosu:** Panelde günlük/aylık kullanım göstergesi (arama, dilekçe kredisi).
   Kullanıcı limiti hissederse, satış açıldığında yükseltme motivasyonu hazır olur.
4. **Onboarding turu:** İlk girişte 3-4 adımlık ürün turu + örnek arama/örnek dilekçe.
   "Alışmaya başlasınlar" hedefinin doğrudan aracı.
5. **NPS / geri bildirim istemi:** 7. gün kullanım sonrası mini anket — satış öncesi
   fiyat/paket doğrulaması için altın değerinde veri.

### 4.2 Ürün farklılaştırıcıları (satış açıldıktan sonra)

6. **Emsal alarmları (UI + job):** "Bu konuda yeni karar çıkınca haber ver" —
   abonelik tutundurmasının en güçlü aracı; job iskeleti zaten var.
7. **Dava dosyası çalışma alanı+:** dosya + notlar + hatırlatıcılar + ilgili emsaller
   tek ekranda; duruşma takvimi görünümü (.ics export ile Google/Outlook entegrasyonu).
8. **UYAP otomatik senkron:** manuel upload yerine dönemsel çekme (PHASE2_BETA'daki D seçeneği).
9. **Ekip işbirliği (Team planını gerçek kılmak):** not/dosya paylaşımı, yorum,
   görev atama. Şu an Team planının "5 kullanıcı" dışında ayırt edici özelliği zayıf.
10. **Public API + API key yönetimi:** api_keys tablosu ve panelden anahtar üretme;
    büyük bürolar ve entegratörler için Enterprise değer önerisi.
11. **Mobil PWA + push bildirim:** hatırlatıcılar için e-postadan daha etkili.
12. **Dilekçe şablon kütüphanesi:** kategori bazlı hazır şablonlar + kullanıcının kendi
    şablonlarını kaydetmesi — günlük kullanım alışkanlığı yaratır.

---

## 5. Detaylı İmplementasyon Planı

Eforlar tek geliştirici varsayımıyla; (S)=≤1 gün, (M)=2-3 gün, (L)=1 hafta+.

### Faz 0 — Lansman Sprinti (Hafta 1) → hedef: bekleme listesi modunda CANLI

| İş | Dosya/Alan | Efor | Kabul kriteri |
|----|-----------|------|---------------|
| 0.1 Prod secrets üret + Secret Manager'a yaz; MASTER_KEY için offline yedek prosedürü yaz | `infra/gcp/create_secrets.py`, yeni `DR_RUNBOOK.md` | S | Tüm placeholder'lar dolu; key rotasyon/yedek adımları dokümante |
| 0.2 Prod SMTP (Resend önerilir: TR teslimat + basit API) | `services/email.py`, env | S | Doğrulama, şifre sıfırlama, hatırlatıcı mailleri prod domain'den DKIM/SPF'li gidiyor |
| 0.3 ALLOWED_ORIGINS + NEXTAUTH_URL prod değerleri | env | S | Prod domain'de login + API çağrıları çalışıyor |
| 0.4 Embedding'i tamamla (geçici GPU VM veya batch API) | `scripts/` | M | 187K chunk'ın tamamı pgvector'da; örnek 20 sorguda kalite kontrolü |
| 0.5 Sentry DSN + uptime monitörü + basit alarm (mail) | env, UptimeRobot | S | /api/health 5 dk aralıkla izleniyor; hata alarmı geliyor |
| 0.6 Smoke test senaryosu: kayıt→doğrulama→arama→dilekçe→hatırlatıcı | yeni `tests/e2e_smoke.md` (manuel liste) | S | Prod'da uçtan uca elle doğrulandı |
| 0.7 iyzico canlı başvurusunu BAŞLAT (onay 1-2 hafta) | operasyon | S | Başvuru gönderildi (Faz 2'ye bloker olmasın) |
| 0.8 Mesafeli satış sözleşmesi + cayma/iade sayfaları (taslak) | yeni `web/app/mesafeli-satis`, `web/app/iade-politikasi` | M | Sayfalar yayında (satış kapalıyken de yayınlanabilir); footer'a link |

### Faz 1 — Güvenilirlik Sprinti (Hafta 2-3)

| İş | Dosya/Alan | Efor | Kabul kriteri |
|----|-----------|------|---------------|
| 1.1 Hatırlatıcı retry/backoff: `failed` yerine `retry_count`+`next_attempt_at` kolonları, 3 deneme, sonra failed + kullanıcıya panelde uyarı | `services/hatirlatici_gonderim.py`, migration | M | SMTP kesintisi simülasyonunda mail 2. denemede gidiyor |
| 1.2 Kota sertleştirme: `usage_events` üzerine atomik `INSERT ... SELECT ... WHERE count < limit` deseni veya Postgres advisory lock; limitleri DB'ye taşı (plan_limits tablosu) | `api/rate_limit.py`, migration | M | Eşzamanlı 50 istekte limit aşılamıyor (test ile kanıtlı); limitler admin'den düzenlenebilir zemin hazır |
| 1.3 GitHub Actions CI: `pytest` + `tsc --noEmit` + `next build` + `ruff` | yeni `.github/workflows/ci.yml` | S | PR'da kırmızı/yeşil; main'e broken kod giremiyor |
| 1.4 API e2e testleri (httpx + test DB): auth, arama, dilekçe, hatırlatıcı CRUD, billing callback idempotency | `tests/test_api_*.py` | L | Kritik 10 akış CI'da koşuyor |
| 1.5 Cron'ları bağla: `purge_deleted.py` (günlük), `update_faiz_oranlari.py` (günlük), emsal scraper (gece) | Cloud Scheduler/Railway cron | S | Loglarda düzenli çalıştıkları görülüyor |
| 1.6 GCS yetim dosya temizliği: hard-delete'te storage silme | `services/` + `purge_deleted.py` | S | Silinen tenant'ın GCS objesi kalmıyor |
| 1.7 Backup/DR runbook: restore tatbikatı bir kez yapılıp süresi not edilir | `DR_RUNBOOK.md` | M | Yedekten geri dönüş adım adım doğrulanmış |
| 1.8 Bayat dokümanları güncelle (Chroma referansları, PRODUCTION_CHECKLIST) | *.md | S | Dokümanlar kodla tutarlı |
| 1.9 **Redact-before-embed:** chunk'lar embed edilmeden ÖNCE `redact()`; `document` kolonunda orijinal metin kalır (görüntüleme/LLM-context zaten ayrıca maskeli). `embed_query` öncesi sorgu da redact. Mevcut tenant chunk'ları için yeniden indeksleme script'i | `services/tenant_rag.py`, `api/routers/uyap.py`, yeni `scripts/reindex_tenant_docs.py` | M | Dış embedding API'sine giden hiçbir payload'da TCKN/isim/adres yok; arama kalitesi örnek 20 sorguda korunuyor. (Alternatif: `EMBEDDING_PROVIDER=local` — ama public verinin de yeniden indekslenmesi gerekir; redact-before-embed daha ucuz) |
| 1.10 NER prod kurulumu: `PII_NER_MODEL=savasy/bert-base-turkish-ner-cased` + `PII_BLOCK_FOREIGN_LLM_WITHOUT_NER=1`; uzun metinler için NER pencereleme (512 token dilimleri, örtüşmeli) | `services/pii_redaction.py`, env | M | 10+ sayfalık örnek belgede son sayfadaki isimler de maskeleniyor; NER yüklenemezse LLM çağrısı bloklanıyor |
| 1.11 Unredact güçlendirme: toleranslı placeholder eşleme (biçimlendirme/boşluk bozulmalarına dayanıklı) + yanıt dönmeden kalan placeholder taraması (varsa "[gizlenmiş bilgi]" ile değiştir + logla) | `services/pii_redaction.py` | S | LLM'in placeholder'ı bozduğu senaryoda kullanıcıya ham placeholder sızmıyor |
| 1.12 PII sızıntı e2e testi: httpx mock ile dış API'lere (embedding + LLM) giden TÜM payload'ları yakala; örnek UYAP belgesindeki TCKN/isim/IBAN hiçbirinde geçmemeli — CI'da koşar | yeni `tests/test_pii_leak_e2e.py` | M | Test kırmızıyken merge edilemiyor; garanti sürekli doğrulanıyor |
| 1.13 Redact tutarlılık denetimi: kullanıcı metni alan tüm LLM servislerinde (dilekçe, ihtarname, özet, denetim, sözleşme) redact standardı; `uyap.py`'deki bayat "local Chroma" yorumunu düzelt; PLATE regex'inin daire atıflarıyla ("12 HD 2021") çakışmasını gider | `services/*.py`, `api/routers/uyap.py` | M | Tüm LLM çağrı noktaları listelenip işaretli; atıflar bozulmuyor |

### Faz 2 — Alışkanlık & Dönüşüm Sprinti (Hafta 4-6, satış açılışına hazırlık)

| İş | Dosya/Alan | Efor | Kabul kriteri |
|----|-----------|------|---------------|
| 2.1 Onboarding turu (ilk giriş, 4 adım) + örnek içerik | `web/app/panel/_onboarding.tsx` | M | Yeni kullanıcı turu tamamlama oranı ölçülüyor |
| 2.2 Kullanım panosu: panel ana sayfada günlük/aylık kullanım + limit göstergesi | `web/app/panel/_stats.tsx`, `api/routers/me.py` | M | Free kullanıcı limitini görüyor |
| 2.3 Waitlist CRM: admin panelde segment + toplu davet maili + davet kodu ile kayıt | `web/app/panel/admin/bekleme-listesi/`, `api/routers/waitlist.py` | L | Davet edilen kullanıcı kodla kayıt olabiliyor |
| 2.4 NPS mini anketi (7. gün) | `web/components/`, `api/routers/feedback.py` | S | Yanıtlar admin'de görünüyor |
| 2.5 LLM streaming'i devreye al | mevcut kod + deploy | S | Dilekçe üretimi token token akıyor |
| 2.6 Redis: rate limit + LLM/arama cache | `api/rate_limit.py`, `services/` | M | Aynı sorgu 2. kez <200ms; çok instance'ta limit tutarlı |
| 2.7 Satışı aç: `SATIS_ACIK=true`, iyzico prod anahtarları, PlanCta eski akışa | `web/lib/satis-modu.ts`, `web/components/plan-cta.tsx` | S | Uçtan uca gerçek ödeme testi (düşük tutarlı) başarılı |
| 2.8 Admin: audit log görüntüleme + admin rol atama UI | `web/app/panel/admin/`, `api/routers/admin.py` | M | Loglar filtrelenebilir listeleniyor |

### Faz 3 — Farklılaşma (2. ay ve sonrası)

Öncelik sırasıyla: **Emsal alarmları** (L) → **Dilekçe şablon kütüphanesi** (M) →
**UDF export tamamlanması** (M) → **Duruşma takvimi + .ics** (M) →
**Team işbirliği özellikleri** (L) → **UYAP oto-senkron** (L) →
**WhatsApp/Telegram kanalları** (M, resmi API onayları gerektirir) →
**Public API + api_keys** (L) → **PWA/push** (M) →
**Yargıtay arşiv genişletme** (L, hukuki/etik değerlendirme ile birlikte).

Her Faz 3 kalemi başlamadan önce Faz 2'deki kullanım verisiyle önceliklendirme
yeniden gözden geçirilmeli — alarmlar ve şablonlar muhtemelen en yüksek talebi görecek.

---

## 6. Riskler ve Azaltma

| Risk | Etki | Azaltma |
|------|------|---------|
| MASTER_ENCRYPTION_KEY kaybı | Tüm tenant verisi kalıcı okunamaz | 0.1'deki offline yedek + Secret Manager sürümleme |
| Embedding yoluyla PII sızıntısı (UYAP) | KVKK ihlali + "AI'a kişisel veri gitmez" taahhüdünün ihlali | 1.9 redact-before-embed + 1.10 NER/strict mod + 1.12 sürekli sızıntı testi |
| iyzico canlı onayının gecikmesi | Satış açılışı gecikir | 0.7 — başvuruyu hemen başlat |
| Tek instance hatırlatıcı döngüsü | Kaçan hatırlatıcı = güven kaybı | 1.1 retry + uptime alarmı; ileride Cloud Scheduler'a taşı |
| Bedava dönemde LLM maliyeti | Bütçe aşımı | Free limitleri koru (40/gün), 2.6 cache, günlük maliyet alarmı |
| Scraper'ların hukuki durumu | İtibar/yasal risk | Kaynak sitelerin kullanım şartlarını hukukçuyla değerlendir |
| Bayat dokümantasyon | Yanlış kararlar | 1.8 doküman senkronu |

---

## 7. Özet Öncelik Sırası

1. **Bu hafta (Faz 0):** secrets → SMTP → embedding → monitoring → mesafeli satış sayfaları → iyzico başvurusu → CANLI (bekleme listesi modunda)
2. **Hafta 2-3 (Faz 1):** **PII sızıntısını kapat (1.9-1.12, UYAP açılmadan önce şart)** → hatırlatıcı retry → kota sertleştirme → CI + e2e → cron'lar → DR runbook
3. **Hafta 4-6 (Faz 2):** onboarding + kullanım panosu + waitlist CRM → streaming + Redis → **satış açılışı**
4. **2. ay+ (Faz 3):** emsal alarmları → şablon kütüphanesi → UDF → takvim → ekip özellikleri

Bu sıralama, "kullanıcılar alışsın" hedefini korurken satış açılışına kadar geçen
süreyi güvenilirlik ve dönüşüm altyapısına yatırım için kullanır.
