# Türk Hukuk Emsal Karar Toplama — İmplementasyon Planı

**Konu odağı:** `tahsilat`, `ihtar`, `icra`
**Kaynaklar:** UYAP Emsal · Yargıtay · Danıştay · AYM + HUDOC
**Kullanım amacı:** ML/LLM eğitimi & RAG
**Hedef hacim:** Tam arşiv (mevcut tüm kararlar)
**Altyapı:** Yerel makine, ücretsiz/açık kaynak araçlar
**Hazırlanma tarihi:** 2026-05-04

---

## 0. Yönetici Özeti ve Gerçekçi Beklentiler

Bu plan, kısıtlı altyapıyla ulaşılabilir olanı maksimize etmek üzerine kuruludur. Birkaç dürüst nokta:

1. **Tam arşiv hedefi yerel makineyle 4-8 ay alır.** UYAP Emsal'de tek IP'den günde güvenli bir şekilde çekilebilecek karar sayısı 500-2000 bandındadır. 200K+ karar için bu matematik 100-400 gün eder. Tor üzerinden IP rotasyonu bunu paralelleştirebilir ama yine de aylar konuşuyoruz.

2. **Aşamalı strateji uyguluyoruz:** Önce hazır verisetleri ve resmi API'ler, sonra orta zorluktaki siteler, en son UYAP. İlk hafta sonunda hatırı sayılır miktarda veri elimizde olur.

3. **`tahsilat / ihtar / icra` konu filtresi avantaj.** Tam ham crawl yerine bu üç anahtar kelime çevresinde sorgulama yapacağız. Bu hacmi tam arşivin ~%15-25'ine indirir (50-150K karar civarı), yani aslında "tam arşiv"den çok "konu bazlı tam arşiv" hedefliyoruz — bu çok daha gerçekçi.

4. **Yasal çerçeve:** Bu kararlar kamuya açık. Toplu indirme TOS açısından gri alan. Veriyi yayımlayacaksan KVKK ve karar metinlerindeki anonimleştirme kontrolü kritik. Plan içinde compliance adımları var.

---

## 1. Konu Odaklı Sorgu Stratejisi

`tahsilat / ihtar / icra` konularında değerli olan kararları yakalamak için her sitede şu kelime kombinasyonlarıyla sorgu atacağız:

**Birincil anahtar kelimeler:**
`icra`, `icra takibi`, `icra emri`, `tahsilat`, `ihtar`, `ihtarname`, `ödeme emri`, `haciz`, `kambiyo senedi`, `çek`, `senet`

**Tematik genişletme:**
`itirazın iptali`, `itirazın kaldırılması`, `menfi tespit`, `istihkak`, `ihalenin feshi`, `kıymet takdiri`, `borçlunun temerrüdü`, `temerrüt faizi`, `vergi tahsilatı`, `amme alacağı`, `6183 sayılı kanun`

**Kanun bazlı:**
`İİK` (İcra İflas Kanunu), `2004 sayılı kanun`, `İİK 67`, `İİK 68`, `İİK 89`, `TBK 117` (temerrüt)

**Daire/mahkeme odağı (özellikle Yargıtay):**
- 12. Hukuk Dairesi (icra hukuku ana dairesi — KRİTİK)
- 8. Hukuk Dairesi (icra/iflas)
- 13. ve 19. Hukuk Daireleri (ticari uyuşmazlıklar)
- 3. Hukuk Dairesi (ihtar/temerrüt)

Bu daireler özelinde tam crawl yapmak, anahtar kelime sorgusundan daha verimli olabilir.

---

## 2. Mimari Genel Bakış

```
┌─────────────────────────────────────────────────────────┐
│  AŞAMA 0: Hazır Veri Envanteri (HF, GitHub, akademik)   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  AŞAMA 1: Açık API'ler  (HUDOC, mevzuat, Resmi Gazete)  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  AŞAMA 2: Orta Zorluk   (AYM Kararlar Bilgi Bankası)    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  AŞAMA 3: Aktif Kazıma  (Danıştay → Yargıtay → UYAP)    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Pipeline:  RAW → CLEAN → ENRICH → ML-READY (parquet)   │
└─────────────────────────────────────────────────────────┘
```

**Veri katmanları:**

- `data/raw/` — Ham HTML/JSON dump'ları, kaynak başına dizin
- `data/cleaned/` — Normalize edilmiş, alanları çıkarılmış JSONL
- `data/enriched/` — Anonimleştirme kontrolü, dedup, konu etiketleme yapılmış
- `data/final/` — ML/RAG için parquet + chunked text

---

## 3. Teknik Yığın (Hepsi Ücretsiz/Açık Kaynak)

| Katman | Araç | Neden |
|---|---|---|
| Tarayıcı otomasyonu | **Playwright (Python)** + `playwright-stealth` | Cloudflare/Akamai challenge için en stabil |
| Anti-detection | `undetected-chromedriver` (yedek) | Selenium gerekirse |
| HTTP istemci | `httpx` (async) | API endpoint'leri için |
| HTML parse | `selectolax` veya `lxml` | BeautifulSoup'tan 10x hızlı |
| IP rotasyonu | **Tor + stem** kontrolü | Ücretsiz proxy havuzu |
| Kuyruk | **SQLite** (`jobs` tablosu) | Resumable, basit |
| Final depolama | Parquet + DuckDB | Hızlı analitik sorgu |
| Orchestration | `asyncio` + `tenacity` retry | Built-in, ek bağımlılık yok |
| OCR (gerekirse) | `tesseract` + `pytesseract` | PDF tarama olursa |
| Metin temizleme | `clean-text`, custom regex | Türkçe karakter normalizasyonu |
| Konu sınıflama | `BERTurk` embedding | Final etiketleme |
| Dedup | MinHash (`datasketch`) | Yakın-duplicate karar tespiti |

---

## 4. Aşama Aşama Detaylı Plan

### Aşama 0: Keşif & Hazır Veri Envanteri (Hafta 1)

**Amaç:** Sıfırdan kazımaya başlamadan, topluluğun zaten yaptığı işi tespit etmek.

**Görevler:**

1. Hugging Face Hub'da `language:tr` + `legal/law` filtresiyle dataset taraması:
   - `KocLab-Bilkent/turkish-constitutional-court`
   - `umarigan/turkish_corpus_legal`
   - `Holmeister/Turkish-Legal-NLP`
   - `boun-tabi-LMG/turkish-legal-text` (varsa)
2. GitHub'da arama: `yargitay scraper`, `danistay api`, `turkish legal dataset`, `uyap kararlar`
3. Akademik repolar: Bilkent NLP grubu, Koç Üniversitesi, ODTÜ İYTE arşivleri
4. Türkiye Açık Veri Portalı (`veri.gov.tr`) hukuk başlığı altı taraması
5. Bulunan her veri seti için: lisans, hacim, format, son güncelleme, kapsanan dönem dokümante edilir

**Çıktı:** `data/external/INVENTORY.md` — bulunan kaynaklar tablosu, tahsilat/ihtar/icra ilgisi notu

---

### Aşama 1: HUDOC API (Hafta 1-2)

**Neden önce:** Resmi REST API'si var, anti-bot koruması yok, hemen sonuç üretir.

**Endpoint:** `https://hudoc.echr.coe.int/app/query/results?...`

**Strateji:**
- Türkiye aleyhine (`respondent=TUR`) tüm kararlar
- Filtre: `Article=P1-1` (mülkiyet hakkı) + `Article=6` (adil yargılanma)
- "tahsilat", "icra", "ihtar" anahtar kelime sorgusu
- Her karar JSON + tam metin (HTML/Word formatında indirilebilir)
- Tahmini hacim: 1-3K Türkçe çevirili karar

**Risk:** Düşük. Resmi public API.

---

### Aşama 2: AYM Kararlar Bilgi Bankası (Hafta 2-3)

**URL:** `https://kararlarbilgibankasi.anayasa.gov.tr/`

**Neden burada:** Bot koruması orta düzey. AJAX endpoint'leri var. Bireysel başvuru kararlarında mülkiyet hakkı / adil yargılanma kapsamında icra-tahsilat içerikli zengin veri.

**Strateji:**
- Network sekmesinden POST endpoint'lerinin reverse engineering'i
- Anahtar kelime + konu (mülkiyet hakkı, adil yargılanma) filtresi
- Sayfalama: ~50 sonuç/sayfa, async paralel fetch (3-5 worker)
- Her karar HTML detay sayfası + PDF varsa indirilir
- Tahmini hacim: 5-15K ilgili karar

**Anti-bot:** User-Agent rotasyonu, 2-5sn bekleme, Tor opsiyonel.

---

### Aşama 3: Danıştay karararama (Hafta 3-6)

**URL:** `https://karararama.danistay.gov.tr/`

**Neden burada:** Vergi tahsilatı, amme alacağı, idari icra için kritik. Bot koruması Yargıtay'dan biraz daha yumuşak.

**Strateji:**
1. **Discovery fazı:** Playwright ile arama formunu manuel doldur, network trafiğini yakala. Genellikle bir POST endpoint JSON döner.
2. **Endpoint exploitation:** Doğrudan o endpoint'e HTTPX ile istek; HTML render gereksinimini bypass et.
3. **Sorgu matrisi:** Her anahtar kelime × daire × yıl kombinasyonu (sonuç limiti tipik olarak 1000, parçalama gerekebilir).
4. **Detay sayfası:** Her karar ID'si için ayrı detay isteği. Burada Playwright fallback gerekebilir.
5. **Tahmini hacim:** 20-40K ilgili karar.

**Çoklu IP:** Tor stem kontrolü ile her N istekte bir circuit yenileme.

---

### Aşama 4: Yargıtay karararama (Hafta 6-12)

**URL:** `https://karararama.yargitay.gov.tr/`

**Neden burada:** İcra hukuku için **en kritik** kaynak. Yargıtay 12. HD'nin kararları emsal araştırmasının kalbi. Bot koruması ciddi ama UYAP'tan biraz daha yumuşak.

**Strateji:**
1. Daire bazlı tam crawl (12. HD önce, sonra 8. HD, 13. HD, 19. HD, 3. HD)
2. Her daire için: tarih aralığı parçalama (yıl × ay), her parça için anahtar kelime sorgusu yerine **tam liste**
3. Karar detayları için ayrı pipeline; ID-bazlı, idempotent
4. **Yavaş ve istikrarlı:** Saatte 300-500 istek hedefi
5. **Tahmini hacim:** 80-150K ilgili karar (sadece ilgili daireler)

**Anti-bot katmanları:**
- Playwright + stealth + headless modu kapalı (görünür ama küçültülmüş pencere)
- Tor SOCKS5 proxy + her 50 istekte yeni circuit
- Mouse hareket simülasyonu, klavye event'leri
- Gece saatleri (00:00-06:00) önceliklendirilir
- Failed request'ler exponential backoff ile retry

---

### Aşama 5: UYAP Emsal (Hafta 12-24)

**URL:** `https://emsal.uyap.gov.tr/`

**Neden en sona:** En sert koruma. Yerel mahkeme + Bölge Adliye + Yargıtay birleşik arşivi. Tam coverage burada haftalar/aylar sürer.

**Strateji:**
1. Önce Yargıtay'da elde ettiğimiz veriyle ne kadar overlap var ölç — UYAP Emsal'in eklediği marjinal değeri belirle
2. **Hibrit yaklaşım:** Anahtar kelime sorgusu sonuçları + mahkeme türü filtresi (icra mahkemeleri özellikle)
3. Çok uzun bekleme süreleri (5-15sn arası rastgele)
4. Tor circuit + sürekli session yenileme
5. Captcha çıkarsa: **manuel destekli** mod (`pause_for_human` switch'i ile gece-gündüz hibrit çalışma) — kapçaları çözmek için 2captcha gibi servislere bütçe çıkarsa otomasyon ileri seviye olur

**Tahmini hacim:** 30-80K marjinal yeni karar (Yargıtay overlap'ı düşülünce).

**Risk:** En yüksek. IP banı, hesap gerektirme, format değişikliği. Plan B: bu aşama paralel olarak resmi bilgi edinme başvurusuyla yedeklenmeli (bkz. Bölüm 9).

---

## 5. Anti-Bot Stratejisi (Detay)

### 5.1 Tarayıcı Kimliği Gizleme
- Playwright'in default Chromium'unu `playwright-stealth` ile patchle
- `webdriver`, `chrome.runtime`, `plugins.length` gibi tipik tespit yüzeylerini maskele
- User-Agent havuzu: gerçek Chrome/Firefox sürümlerinden oluşan 50+ kayıt, rastgele rotasyon
- `Accept-Language: tr-TR,tr;q=0.9,en;q=0.8` Türk kullanıcı sinyali

### 5.2 IP Rotasyonu (Ücretsiz)
- **Tor:** `stem` kütüphanesiyle `NEWNYM` sinyali, her 30-50 istekte bir
- Tek seferde 10 paralel Tor circuit'i mümkün (`MaxClientCircuitsPending`)
- Yedek olarak free proxy listeleri (`free-proxy-list.net`) — ama bunlar genelde yavaş ve güvensiz, son çare

### 5.3 Davranışsal Simülasyon
- Sayfa yüklenince 1-3sn human-like wait
- Mouse hareketi: `page.mouse.move()` ile rastgele yörüngeler
- Scroll: `window.scrollTo()` adım adım
- Form doldurma: `type()` karakter karakter, 50-150ms gecikmeyle

### 5.4 Rate Limiting (Self-imposed)
- Her domain için ayrı async semaphore
- Yargıtay: max 2 paralel, 4-8sn bekleme
- Danıştay: max 3 paralel, 3-6sn bekleme
- UYAP: max 1 paralel (!), 8-15sn bekleme
- HUDOC/AYM: max 5 paralel, 1-3sn bekleme

### 5.5 Resilience
- Her istek `tenacity` ile 5 retry, exponential backoff
- HTTP 429/403 alınca o IP/circuit 30dk timeout'a alınır
- Cloudflare interstitial tespit edilince Playwright fallback'a geçilir
- Her başarılı karar anında SQLite'a `processed=1` olarak işaretlenir → durup kaldığın yerden devam

---

## 6. Veri Modeli ve Format

**JSONL formatı (her satır bir karar):**

```json
{
  "id": "yargitay_12hd_2024_e2023-1234_k2024-5678",
  "source": "yargitay",
  "court_chamber": "12. Hukuk Dairesi",
  "court_level": "yuksek_mahkeme",
  "case_no": "2023/1234",
  "decision_no": "2024/5678",
  "decision_date": "2024-03-15",
  "publication_date": "2024-04-02",
  "subject_keywords_query": ["icra", "itirazın iptali"],
  "topic_tags": ["icra_hukuku", "itirazin_iptali", "kambiyo"],
  "referenced_laws": ["İİK 67", "TBK 117"],
  "raw_html_path": "data/raw/yargitay/2024/03/yargitay_...html",
  "raw_text": "...",
  "cleaned_text": "...",
  "summary": null,
  "anonymization_check": {"contains_pii": false, "method": "regex_v1"},
  "scraped_at": "2026-05-04T12:34:56Z",
  "scraper_version": "1.0.0",
  "source_url": "https://karararama.yargitay.gov.tr/...",
  "language": "tr",
  "char_count": 4523
}
```

**Kararı parçalama (RAG için):**
- `cleaned_text` 800-1200 karakter chunk'lara bölünür (`langchain.text_splitter` veya manuel)
- Her chunk için BERTurk embedding pre-compute (opsiyonel)
- Final parquet: `id`, `chunk_id`, `chunk_text`, `embedding`, metadata foreign key'leri

---

## 7. Repo İskeleti

```
hukuk-emsal-veri/
├── README.md
├── IMPLEMENTASYON_PLANI.md          # bu dosya
├── pyproject.toml                   # poetry/uv
├── .env.example
├── docker-compose.yml               # Tor + opsiyonel postgres
│
├── data/
│   ├── raw/{source}/{year}/...
│   ├── cleaned/{source}.jsonl
│   ├── enriched/
│   ├── final/all_decisions.parquet
│   └── external/INVENTORY.md
│
├── scrapers/
│   ├── __init__.py
│   ├── base.py                      # BaseScraper abstract class
│   ├── hudoc.py
│   ├── aym.py
│   ├── danistay.py
│   ├── yargitay.py
│   └── uyap_emsal.py
│
├── common/
│   ├── browser.py                   # Playwright wrapper + stealth
│   ├── tor_proxy.py                 # Tor circuit rotation
│   ├── job_queue.py                 # SQLite-backed queue
│   ├── http_client.py               # httpx with retry
│   ├── normalize.py                 # Türkçe metin normalizasyonu
│   └── anonymize.py                 # KVKK uyumluluğu kontrolü
│
├── pipelines/
│   ├── extract.py                   # raw → cleaned
│   ├── enrich.py                    # konu etiketleme, dedup
│   ├── chunk.py                     # RAG için bölme
│   └── embed.py                     # BERTurk vektörleri
│
├── queries/
│   ├── keywords.yaml                # tahsilat/ihtar/icra sorgu matrisi
│   └── chambers.yaml                # daire bilgileri
│
├── analytics/
│   ├── coverage.py                  # ne kadarını topladık?
│   └── quality.py                   # tam metin oranı, metadata tamlığı
│
├── tests/
│   ├── test_normalize.py
│   ├── test_anonymize.py
│   └── fixtures/
│
└── scripts/
    ├── inventory_existing.py        # Aşama 0
    ├── run_scraper.py               # CLI: --source yargitay --resume
    └── export_final.py              # parquet üretimi
```

---

## 8. Öncelik Matrisi: Hangi Konular Hangi Kaynakta Var?

| Konu | UYAP | Yargıtay | Danıştay | AYM | HUDOC |
|---|---|---|---|---|---|
| `icra` (özel hukuk) | ●●● | ●●● | ○ | ●● | ●● |
| `tahsilat` (ticari) | ●●● | ●●● | ●● | ● | ● |
| `tahsilat` (vergi/amme) | ●● | ● | ●●● | ● | ○ |
| `ihtar` (TBK 117) | ●●● | ●●● | ● | ○ | ○ |
| `kambiyo / çek / senet` | ●●● | ●●● | ○ | ● | ○ |

`●●●` çok zengin · `●●` orta · `●` az · `○` yok

**Stratejik karar:** Yargıtay ve UYAP icra hukukunda overlap'lı; Yargıtay'ı önce tamamla, sonra UYAP'ı sadece marjinal kazanç için sürdür.

---

## 9. Paralel Yasal Yol: Bilgi Edinme Başvurusu

**Bu aktif kazımayla paralel ilerlemeli.** Bedavaya tonlarca veri kazandırabilir:

1. CİMER veya doğrudan Adalet Bakanlığı'na 4982 sayılı Bilgi Edinme Kanunu kapsamında başvuru
2. Talep: "Anonimleştirilmiş, yapılandırılmış formatta (XML/JSON) icra hukuku konulu Yargıtay 12. HD kararları, son 10 yıl"
3. Akademik amaç beyan edilebilir (eğer durum öyleyse)
4. Cevap süresi: 15-30 gün
5. Kabul oranı: ~%30-40 (deneyime göre değişir)
6. Reddedilse bile reddin gerekçesi sonraki başvurular için yön gösterir

UYAP avukat portalına erişimi olan bir avukatla işbirliği yapılabilirse veri çekimi katlanarak hızlanır (yasal bir profesyonel yol).

---

## 10. Risk Analizi ve Mitigasyon

| Risk | Olasılık | Etki | Mitigasyon |
|---|---|---|---|
| IP banı (UYAP/Yargıtay) | Yüksek | Yüksek | Tor rotasyonu, yavaş crawl, gece saatleri |
| Site HTML/endpoint değişikliği | Orta | Orta | Modüler scraper'lar, schema validasyon, alarm |
| Captcha çıkması | Orta | Yüksek | Manuel-yardım modu, Playwright headed run |
| Veri kalitesi (eksik metin) | Orta | Yüksek | Multi-source verification, char_count threshold |
| KVKK / kişisel veri sızıntısı | Düşük | Çok yüksek | Anonimleştirme audit'i, regex + NER pipeline |
| Telif/ToS ihlali iddiası | Düşük | Yüksek | Sadece kamuya açık veri, dağıtım öncesi hukuki danışma |
| Disk doluluğu (TBs) | Yüksek | Orta | Sıkıştırma (zstd), eski raw'ları arşivle |
| Tor yavaşlığı/down | Orta | Orta | Çoklu Tor instance, fallback proxy listesi |

---

## 11. Zaman Çizelgesi (Yerel + Ücretsiz Senaryosu)

```
Hafta 1     ▓▓░░░░░░░░░░░░░░░░░░░░░░  Aşama 0: Envanter + repo iskeleti
Hafta 2-3   ░░▓▓░░░░░░░░░░░░░░░░░░░░  Aşama 1: HUDOC ✓
Hafta 3-4   ░░░▓▓░░░░░░░░░░░░░░░░░░░  Aşama 2: AYM ✓
Hafta 4-7   ░░░░░▓▓▓░░░░░░░░░░░░░░░░  Aşama 3: Danıştay
Hafta 7-13  ░░░░░░░▓▓▓▓▓▓░░░░░░░░░░░  Aşama 4: Yargıtay (en kritik)
Hafta 13-22 ░░░░░░░░░░░░░▓▓▓▓▓▓▓▓▓░░  Aşama 5: UYAP Emsal
Hafta 22-24 ░░░░░░░░░░░░░░░░░░░░░░▓▓  Final: Pipeline, dedup, parquet, RAG hazırlık
```

**Toplam: ~6 ay tam scope.** Kısaltmak istersen residential proxy bütçesi planı 2-3 aya indirir.

---

## 12. Başarı Metrikleri

- **Coverage:** Toplanan kararlar / kaynaktaki tahmini toplam ilgili karar (hedef: %85+)
- **Quality:**
  - Tam metin oranı (`char_count > 500` olanlar): hedef %95+
  - Metadata tamlığı (case_no, decision_no, date dolu): hedef %98+
  - Anonymization audit pass oranı: hedef %100
- **Throughput:** Günlük çekilen karar sayısı kaynak başına
- **Dedup ratio:** Yakın-duplicate kararların oranı (hedef <%10 final dataset'te)
- **Topic relevance:** Konu tag'leri ile arama keyword'lerinin örtüşme oranı

Her aşama sonunda `analytics/coverage.py` ve `analytics/quality.py` çalıştırılıp dashboard üretilir.

---

## 13. Compliance & Etik Kontrol Listesi

- [ ] Her kaynağın `robots.txt`'i incelenir, agresif olarak ihlal edilmez
- [ ] User-Agent'larda iletişim bilgisi (`+contact:email@example.com`) — saygılı crawler kuralı
- [ ] Rate limit'ler kaynağı zorlamayacak şekilde
- [ ] Anonimleştirme: TC kimlik no, telefon, IBAN, açık ad-soyad regex ile maskelenir
- [ ] NER (BERTurk) ile ek anonimleştirme audit'i
- [ ] Veri seti yayımlanacaksa: lisans seçimi (CC-BY-NC-SA önerilir), kaynak attribution
- [ ] KVKK: ticari kullanım öncesi avukat görüşü
- [ ] Her scraper'ın `--dry-run` modu, `--max-requests N` switch'i var

---

## 14. İlk Hafta Eylem Planı

**Pazartesi-Salı:**
1. Repo iskeleti kurulur (yukarıdaki yapı)
2. `pyproject.toml` ile bağımlılıklar (`playwright`, `httpx`, `selectolax`, `stem`, `tenacity`, `duckdb`, `pyarrow`)
3. Tor docker-compose ile ayağa kaldırılır
4. `common/browser.py` ve `common/tor_proxy.py` yazılır + test edilir

**Çarşamba-Perşembe:**
5. `scripts/inventory_existing.py` çalıştırılır → HuggingFace + GitHub envanteri
6. HUDOC scraper'ı yazılır ve çalıştırılır → ilk veri akmaya başlar

**Cuma:**
7. AYM scraper'ı için endpoint discovery (Network sekmesi reverse engineering)
8. İlk haftalık coverage raporu

İlk hafta sonunda elimizde: HuggingFace'ten gelen N adet karar + HUDOC'tan ~1-3K Türkiye kararı + AYM endpoint analizi tamamlanmış.

---

## 15. Açık Sorular ve Karar Bekleyen Noktalar

1. **GPU erişimi var mı?** BERTurk embedding için GPU 10x hızlandırır. Yoksa son aşama CPU'da haftalar sürer.
2. **Disk kapasitesi?** Tam arşiv ham + işlenmiş ~500GB-1TB sürebilir.
3. **Manuel captcha çözmeye zaman ayırabilir miyiz?** UYAP'ta bu fark yaratabilir.
4. **Bir avukatla/hukuk firmasıyla bağlantı var mı?** UYAP avukat portalı erişimi her şeyi değiştirir.
5. **Lisans hedefi: özel kullanım mı, açık dataset mi?** Bu compliance sıkılığını belirler.

---

## 16. Sonraki Adım

Bu plan onaylanınca **Aşama 0 ve Aşama 1'in implementasyonuyla başlamayı öneriyorum** — ilk hafta sonunda elimize fiili veri geçer ve sonraki aşamalar için baseline'ımız olur. Hangi aşamadan başlayalım, ya da plan üzerinde değiştirmek istediğin yer var mı?
