# Uygulama Özeti — GELISTIRME_ONERILERI.md maddeleri (2026-06-09)

11 öneri maddesinin tamamı kodlandı. Değişiklik haritası ve devreye alma notları.

## Yapılanlar

| # | İş | Dosyalar |
|---|---|---|
| 1 | **Event loop fix** — tüm senkron LLM/RAG/DuckDB çağrıları thread'e alındı | `api/concurrency.py` (yeni), tüm router'lar (`arama, dilekce, ozet, ihtarname, karsi_argument, denetim, sozlesme, trend, kvkk, uyap`) |
| 2 | **TTL cache + background insert** — arama/stats/trend cache'li; geçmiş yazımı BackgroundTasks'ta | `api/cache.py` (yeni), `api/routers/arama.py`, `api/routers/trend.py` |
| 3 | **LLM streaming (SSE)** — dilekçe token-token akıyor; emsaller anında görünüyor; stream koparsa klasik endpoint'e otomatik fallback | `llm/provider.py` (`generate_stream`), `services/dilekce_emsalli.py` (`generate_dilekce_stream`), `api/routers/dilekce.py` (`POST /stream`), `web/lib/api.ts` (`dilekceStream`), `web/app/dilekce/dilekce-form.tsx` |
| 4 | **Fiyatlandırma sayfası** — 4 plan + SSS + FAQPage JSON-LD; header/footer'a link; **bonus:** header/footer'daki 6 kırık link (404) düzeltildi | `web/app/fiyatlandirma/page.tsx` (yeni), `components/layout/header.tsx`, `footer.tsx`, `app/sitemap.ts` |
| 5 | **.docx + .udf (UYAP) export** — dilekçe ve ihtarname Word/UYAP formatında iniyor | `services/export_belge.py` (yeni), `api/routers/export.py` (yeni), iki form + `lib/api.ts` |
| 6 | **TCMB oran otomasyonu** — oranlar `data/faiz_oranlari.json`'dan; EVDS çekme + elle güncelleme script'i; `/api/faiz/options` artık `oran_kaynagi` (son güncelleme) dönüyor | `services/faiz_oranlari.py` (yeni), `scripts/update_faiz_oranlari.py` (yeni), `services/faiz_hesaplayici.py`, `api/routers/faiz.py` |
| 7 | **Favoriler + akış + boş durum** — karar yıldızlama (klasörlü), arama sonucundan tek tık "dilekçe yaz"/"karşı argüman", Chroma hazır değilse uyarı banner'ı | `infra/db/10_saved_decisions.sql` (yeni), `api/routers/me.py` (`/kararlar`), `web/app/emsal-arama/arama-form.tsx`, dilekçe+karşı argüman formları URL parametresi okuyor |
| 8 | **Emsal alarmı** — "takip et" butonu → `saved_search_alerts`; gece job'ı yeni eşleşmeleri diff'leyip e-posta atıyor (ilk koşuda baseline, spam yok) | `api/routers/me.py` (`/alerts`), `scripts/emsal_alarm_job.py` (yeni), `services/email.py` (`send_emsal_alarm_email`) |
| 9 | **Embed widget** — `/embed/faiz` iframe sayfası (chrome'suz, noindex) + faiz sayfasında kopyalanabilir embed kodu | `web/app/embed/faiz/page.tsx`, `components/embed-kodu.tsx`, `components/layout/chrome-guard.tsx` (yeni) |
| 10 | **Karar detay sayfaları (SEO pilotu)** — `/karar/{id}` ISR sayfası (Article+Breadcrumb JSON-LD, KVKK anonimleştirme bariyeri) + 10×1000'lik parçalı sitemap + `/api/karar/liste` | `web/app/karar/[id]/page.tsx`, `web/app/karar/sitemap.ts`, `api/routers/karar.py`, `services/rag.py` (`list_decisions`) |
| 11 | **Public API (v1)** — `X-API-Key` ile `/api/v1/arama`; anahtar yönetimi `/api/me/api-keys` (hash'li saklama, günlük kota, audit) | `api/routers/v1.py` (yeni), `api/routers/me.py`, migration'da `api_keys` + `api_key_usage` |

**Bonus güvenlik düzeltmesi:** `services/rag.py get_full_decision()` SQL injection açığı (f-string ile DuckDB sorgusu) parametreli sorguya çevrildi.

## Devreye alma adımları

1. `python scripts/init_db.py` — yeni migration (`10_saved_decisions.sql`: favoriler, alarmlar, API anahtarları).
2. Cron'a iki job: `update_faiz_oranlari.py --evds` (günlük 03:00, `EVDS_API_KEY` gerekli) ve `emsal_alarm_job.py` (scraper'lardan sonra, örn. 06:00).
3. `.env`: yeni değişkenler `.env.example` sonuna eklendi (EVDS_API_KEY, ANYIO_THREAD_LIMIT, API_INTERNAL_URL).
4. `web`: `npm run build` ile doğrulayın (sandbox'ta tam build koşulamadı; tüm dosyalar tek tek syntax-doğrulandı, backend 72/72 test geçti).

## Bilinçli sınırlar

- Cache süreç içi (Redis değil) — multi-worker'da her worker kendi cache'ini tutar; beta için yeterli, ölçekte Redis'e geçiş arayüzü hazır.
- UDF üretici minimal-geçerli belge üretir; UYAP editörünün güncel sürümüyle bir kez elle test edilmeli.
- EVDS seri kodları env ile değiştirilebilir (`EVDS_SERIE_AVANS/REESKONT`) — TCMB seri adı değiştirirse script uyarı verir; **yasal faiz** mevzuatla değiştiği için EVDS'de yoktur, `--set yasal YIL ORAN` ile elle girilir.
- Karar sayfaları pilotu ilk 10K ile sınırlı; indekslenme görüldükten sonra `SAYFA_SAYISI` artırılır.
