# Hukuk Emsal — Geliştirme Önerileri (Performans · UX · Büyüme)

**Tarih:** 2026-06-09
**Yöntem:** api/, services/, llm/, web/ kod incelemesi
**Format:** Her öneri = sorun → çözüm → etki/efor

---

## 🔴 P0 — Performans: Kritik

### 1. Event loop kilitleniyor (en önemli bulgu)
**Sorun:** Tüm router'lar `async def`, ama içlerinde **senkron** çağrılar var:
`dilekce.py` → `generate_dilekce()` → senkron Anthropic client (15-30 sn), `arama.py` → `search()` → senkron sentence-transformers encode + Chroma sorgusu (~100-300 ms).
Asyncio'da `async def` içindeki senkron çağrı **tüm event loop'u bloklar**: tek worker'da bir kullanıcı dilekçe üretirken `/health` dahil bütün istekler 15-30 sn bekler. 4 worker'da 4 eşzamanlı LLM isteği = site tamamen yanıtsız.

**Çözüm (efor: ~yarım gün):** İki seçenekten biri:
- LLM/RAG çağıran endpoint'leri `async def` → `def` yap (FastAPI bunları otomatik threadpool'da çalıştırır), **veya**
- `await anyio.to_thread.run_sync(generate_dilekce, ...)` ile sarmala. DB kullanan kısımlar async kalmalı.

**Etki:** Eşzamanlı kullanıcı kapasitesi ~1'den ~40'a (threadpool default) çıkar. Beta'da bile fark edilir.

### 2. LLM yanıtı stream edilmiyor
**Sorun:** Dilekçe/özet/ihtarname 15-30 sn boş spinner. Kullanıcı "bozuldu" sanıp sayfayı terk eder — LLM ürünlerinde en büyük churn nedeni.
**Çözüm (efor: 2-3 gün):** Anthropic streaming API + FastAPI `StreamingResponse` (SSE) + frontend'de token-token yazdırma. `llm/provider.py`'a `generate_stream()` ekle; önce tek endpoint'te (dilekçe) pilotla.
**Etki:** Algılanan hız ~10x; ilk token 1-2 sn'de görünür.

### 3. Hiç cache yok
**Sorun:** Aynı sorgu her seferinde embedding + Chroma + (varsa) LLM'i baştan çalıştırıyor. Para ve gecikme israfı — özellikle popüler aramalar ("kira tahliye", "icra itiraz") tekrarlanır.
**Çözüm (efor: 1 gün):** Başlangıç için Redis'e gerek yok — `cachetools.TTLCache` ile süreç içi:
arama sonuçları (query+filtre hash, TTL 1 saat), `/stats` ve `/trend` (TTL 6 saat). LLM yanıtı cache'i sadece birebir aynı input için (TTL 24 saat).
**Etki:** Tekrar sorgularda ~300 ms → ~5 ms; LLM maliyetinde tahmini %15-30 düşüş.

### 4. Arama geçmişi kaydı istek yolunda
**Sorun:** `arama.py`'da `user_searches` INSERT'i yanıt dönmeden önce yapılıyor — her aramaya gereksiz DB round-trip ekliyor.
**Çözüm (efor: 30 dk):** FastAPI `BackgroundTasks` ile yanıt sonrasına al.

---

## 🟡 P1 — Kullanıcı deneyimi

### 5. Çıktılar .txt indiriliyor — avukatlar Word/UYAP ister
**Sorun:** `dilekce-form.tsx` ve `ihtarname-form.tsx` düz `.txt` indiriyor. Avukatın gerçek iş akışı: Word'de düzenle → **UYAP'a .udf formatında yükle**.
**Çözüm (efor: 2-4 gün):** Backend'de `python-docx` ile başlıklı/biçimli **.docx export**. Ardından **.udf export** (UYAP Doküman Editörü formatı — içi XML+ZIP, reverse-engineer edilmiş kütüphaneler mevcut). 
**Etki:** Bu, rakiplerin çoğunda yok; "UYAP'a hazır dilekçe" başlı başına pazarlama mesajı ve dönüşüm artırıcı.

### 6. Hesaplayıcı sonuçları paylaşılabilir değil
**Sorun:** Faiz/zamanaşımı sonuçları sadece ekranda. Avukat bunu müvekkile veya dosyaya koymak ister.
**Çözüm (efor: 1-2 gün):** "PDF raporu indir" butonu — hesap dökümü + yıllık kırılım tablosu + yasal uyarı + tarih/logo. URL'e parametre encode edip "hesabı linkle paylaş" da ekle (ücretsiz viral döngü + backlink).

### 7. Arama sonucu → iş akışı kopuk
**Sorun:** Emsal arama sonucu listeleniyor ama oradan tek tıkla "bu emsallerle dilekçe yaz" akışı yok; kullanıcı kopyala-yapıştır yapıyor.
**Çözüm (efor: 1-2 gün):** Sonuç kartlarına "Bu kararla dilekçe oluştur" / "Karşı argüman üret" butonları — seçili chunk_id'ler dilekçe formuna taşınsın. Araçlar arası geçiş = oturum süresi ve keşfedilen özellik sayısı artar.

### 8. Favoriler / çalışma klasörü eksik (public araçlarda)
**Sorun:** `app/dosyalar` (UYAP) var ama emsal arama sonuçlarını kaydetme/yıldızlama yok. Avukat aynı dosya için günlerce aynı kararları arar.
**Çözüm (efor: 2-3 gün):** "Kararı kaydet" + basit klasörleme (dava dosyası bazlı). Kayıt zorunlu olduğu için **anonim → üye dönüşümünün ana motivasyonu** haline gelir.

### 9. Boş/yavaş durum geri bildirimleri
**Sorun:** Chroma seed edilmemişse arama sessizce boş dönüyor (`available:false`); kullanıcıya "veri yükleniyor" gibi bir açıklama gösterilmiyor. LLM 503'ünde de jenerik mesaj var.
**Çözüm (efor: yarım gün):** `/stats`'tan `available` bayrağını çekip banner göster; LLM hatasında "yoğunluk var, X sn sonra otomatik tekrar denenecek" + otomatik retry.

---

## 🟢 P2 — Müşteri kazanımı / yeni özellikler

### 10. Public fiyatlandırma sayfası yok (dönüşüm kaybı)
**Sorun:** 4 plan tanımlı (`billing.py`) ama `/fiyatlandirma` diye pazarlama sayfası yok — fiyatlar sadece giriş yapmış kullanıcının abonelik panelinde. SaaS'ta ziyaretçinin ilk baktığı sayfa fiyattır; ayrıca "hukuk asistanı fiyat" sorguları SEO trafiğidir.
**Çözüm (efor: 1 gün):** Plan karşılaştırma tablosu + SSS + CTA içeren statik sayfa; sitemap'e ekle.

### 11. Emsal alarmı (retention motoru)
**Sorun:** Kullanıcı bir kez arayıp gidiyor; geri gelme nedeni yok. `welcome_series.py` var ama karar bazlı bildirim yok.
**Çözüm (efor: 3-5 gün):** "Bu konuda yeni emsal çıkınca e-posta gönder" — kayıtlı aramalar + yeni scrape edilen kararlar üzerinde haftalık eşleştirme job'ı. Scraper pipeline'ınız zaten gece çalışıyor; üstüne eşleştirme + e-posta katmanı yeterli.
**Etki:** Haftalık geri dönüş trafiği + e-posta listesi büyümesi. Pro'ya yükseltme tetikleyicisi olarak "anlık alarm" Pro'ya konabilir.

### 12. Faiz hesaplayıcı embed widget'ı
**Çözüm (efor: 1-2 gün):** `<iframe>`/script ile hukuk bürosu sitelerine gömülebilir hesaplayıcı, altında "hukukemsal.tr" linki. Avukat blogları (mihci, buken vb. tarzı siteler) hesaplayıcıyı sever → doğal backlink ağı + marka bilinirliği. SEO stratejisindeki backlink hedefiyle birebir örtüşür.

### 13. Faiz oranları statik sözlükte — güven riski
**Sorun:** `faiz_hesaplayici.py`'da oranlar elle yazılmış (`2026: 47.5` vb.). TCMB oranı değiştiğinde hesap sessizce yanlışlanır — hukuk ürününde yanlış faiz = güven kaybı + sorumluluk riski.
**Çözüm (efor: 1-2 gün):** TCMB EVDS API'den (ücretsiz, key ile) oranları günlük çekip DB/JSON'a yaz; sözlük fallback kalsın. Sayfada "oranlar TCMB'den otomatik güncellenir, son güncelleme: X" ibaresi — bu tek cümle bile rakip statik hesaplayıcılara karşı satış argümanı.

### 14. Karar detay sayfaları (SEO stratejisiyle ortak)
10K karardan public özet sayfaları — `SEO_STRATEJI.md` Bölüm 3-C'de detaylı. Trafik kanalı olmasının yanında ürün içi "ilgili kararlar" gezinmesini de açar. En yüksek uzun vadeli ROI'li iş.

### 15. API erişimi (enterprise geliri)
Backend zaten OpenAPI ile dokümante. API key yönetimi + kota eklenerek hukuk yazılımlarına (büro yönetim sistemleri) B2B satış kanalı açılabilir. Talep gelene kadar bekletilebilir; mimari hazır.

---

## Önerilen sıra (etki/efor dengesi)

| Sıra | İş | Efor | Niye önce |
|---|---|---|---|
| 1 | #1 Event loop fix | 0.5 gün | Mevcut sistem yük altında çalışmıyor |
| 2 | #4 Background insert + #3 cache | 1.5 gün | Ucuz, anında hız |
| 3 | #2 LLM streaming (dilekçe pilotu) | 2-3 gün | En büyük algılanan UX sıçraması |
| 4 | #10 Fiyatlandırma sayfası | 1 gün | Dönüşüm + SEO, neredeyse bedava |
| 5 | #5 .docx/.udf export | 2-4 gün | Avukat segmentinde fark yaratan özellik |
| 6 | #13 TCMB oran otomasyonu | 1-2 gün | Güven + doğruluk riski kapanır |
| 7 | #8 Favoriler + #7 araçlar arası akış | 3-4 gün | Üyelik dönüşümü + retention |
| 8 | #11 Emsal alarmı | 3-5 gün | Retention motoru |
| 9 | #12 Embed widget, #14 karar sayfaları | sürekli | Büyüme kanalları |

**Toplam ilk 6 madde:** ~2 hafta — beta öncesi sığar ve hem performansı hem dönüşümü görünür şekilde değiştirir.
