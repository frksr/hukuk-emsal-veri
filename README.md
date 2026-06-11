# hukuk-emsal-veri

Türk hukukunda **tahsilat / ihtar / icra** konulu emsal kararları toplamak için scraper kümesi.

Kaynaklar: HUDOC (AİHM) · Anayasa Mahkemesi · Yargıtay · Danıştay
Hedef format: ML/RAG için JSONL → Parquet
Detaylı plan: [`IMPLEMENTASYON_PLANI.md`](IMPLEMENTASYON_PLANI.md)

---

## Kurulum

```bash
pip install -r requirements.txt
# veya
pip install "httpx[socks]" selectolax tenacity pyyaml duckdb pyarrow python-dateutil tqdm orjson
```

Python 3.10+ gerekli (PEP 604 union type'ları kullanılıyor).

## Hızlı Başlangıç

```bash
# Birim testler — kurulumu doğrula
python3 tests/test_normalize.py
python3 tests/test_anonymize.py
python3 tests/test_job_queue.py

# HUDOC ile başla (en kolay, açık API)
python3 scripts/run_scraper.py --source hudoc --max 200

# Diğer kaynaklar
python3 scripts/run_scraper.py --source aym       --max 500
python3 scripts/run_scraper.py --source danistay  --max 500
python3 scripts/run_scraper.py --source yargitay  --max 500

# Final parquet üret (cleaned/*.jsonl -> final/all_decisions.parquet)
python3 pipelines/export_final.py
```

## Yargıtay/Danıştay endpoint doğrulaması

Bu siteler zaman zaman endpoint payload yapısını değiştirir. İlk çalıştırmadan önce:

1. `https://karararama.yargitay.gov.tr` aç
2. Tarayıcı F12 → Network sekmesi
3. Bir arama yap (örn. "icra" + 12. HD)
4. `aramalist` POST isteğinin payload'ını incele
5. `scrapers/yargitay.py` içindeki `payload` yapısını uyarla
6. `python3 scripts/probe_yargitay.py` ile doğrula

## Dizin Yapısı

```
hukuk-emsal-veri/
├── IMPLEMENTASYON_PLANI.md   ← Detaylı 6 aylık plan
├── README.md
├── requirements.txt
├── queries/keywords.yaml      ← tahsilat/ihtar/icra sorgu matrisi
├── common/                    ← Ortak yardımcılar
│   ├── normalize.py           ← Türkçe-aware metin normalize
│   ├── anonymize.py           ← KVKK PII tespit/maskele
│   ├── http_client.py         ← Saygılı async HTTP (retry + throttle)
│   └── job_queue.py           ← SQLite resumable kuyruk
├── scrapers/
│   ├── base.py                ← Soyut taban sınıf
│   ├── hudoc.py               ← AİHM (resmi REST API)
│   ├── aym.py                 ← Anayasa Mahkemesi
│   ├── danistay.py            ← Vergi/idari icra
│   └── yargitay.py            ← İcra (en kritik)
├── pipelines/
│   └── export_final.py        ← Parquet + dedup
├── scripts/
│   ├── run_scraper.py         ← CLI runner
│   ├── inventory_existing.py  ← HF/GitHub envanter
│   └── probe_yargitay.py      ← Endpoint doğrulama
├── tests/                     ← 20 birim test, hepsi geçiyor
└── data/                      ← raw/, cleaned/, enriched/, final/
```

## Aşamalı Çalıştırma Önerisi

İlk hafta hangi sırayla?

1. **HUDOC** (gün 1) — açık API, anti-bot yok, hemen çalışır
2. **AYM** (gün 2-3) — orta zorlukta, HTML scraping
3. **Danıştay** (gün 4-7) — AJAX endpoint analizi gerekli
4. **Yargıtay** (hafta 2-6) — en yoğun veri, daire bazlı tam crawl
5. **UYAP Emsal** (sonraya bırakıldı, ayrı modül gerekli — ileri seviye anti-bot)

Her aşama sonunda `pipelines/export_final.py` ile birleştirilmiş parquet üretilir.

## Anti-Bot Stratejisi

`common/http_client.py` her domain için:
- 4-8 saniye rastgele bekleme arası
- 4 kez retry, exponential backoff
- User-Agent rotasyonu (4 gerçek tarayıcı imzası)
- `Accept-Language: tr-TR` header'ı
- HTTP 429/403'te otomatik geri çekilme

İleri seviye için (Yargıtay/UYAP) Playwright + stealth + Tor `stem` rotasyonu önerilir; bunlar `IMPLEMENTASYON_PLANI.md` Bölüm 5'te detaylı.

## Veri Şeması

```jsonc
{
  "id": "yargitay_12hd_2024_e2023-1234_k2024-5678",
  "source": "yargitay",
  "court_chamber": "12. Hukuk Dairesi",
  "case_no": "2023/1234",
  "decision_no": "2024/5678",
  "decision_date": "2024-03-15",
  "subject_keywords_query": ["icra"],
  "topic_tags": ["icra", "haciz", "ihtar"],
  "raw_text": "...",
  "cleaned_text": "...",
  "anonymization_check": {"contains_pii": false, "types": []},
  "char_count": 4523,
  "scraped_at": "2026-05-09T...",
  "source_url": "..."
}
```

## KVKK Uyumluluğu

`common/anonymize.py` her karar metnini şu PII pattern'leri için tarar:
TC kimlik no, telefon, IBAN, e-posta, kredi kartı.

Her kayıt `anonymization_check` alanı taşır. Yayım öncesi:

```python
from common.anonymize import anonymize
clean_text, counts = anonymize(raw_text)
```

İleri seviye için BERTurk NER (kişi adı tespiti) ek bir aşama olarak eklenmeli.

## Yasal Çerçeve

Bu kararlar kamuya açıktır. Toplu indirme TOS açısından gri alandır.
Veriyi yayımlayacaksanız: KVKK avukat görüşü + lisans seçimi gereklidir.
Detay: `IMPLEMENTASYON_PLANI.md` Bölüm 13.

## Test Durumu

```bash
pip install -r requirements-dev.txt
python3 -m pytest tests/ -q
```

Kapsam: normalize, anonymize, job_queue, encryption, pii_redaction,
billing (TCKN/telefon validasyonu), db entegrasyon, faiz_hesaplayici, zamanasimi.

