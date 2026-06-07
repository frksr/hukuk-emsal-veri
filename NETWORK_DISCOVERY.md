# Gerçek Endpoint Keşfi — Yargıtay & Danıştay

Bu siteler AJAX endpoint'lerini ve payload yapılarını periyodik olarak değiştirir.
Scraper'ın çalışması için **gerçek payload**'ı kendi tarayıcında inspect etmen gerekir.

## Adımlar (Chrome/Edge için)

### 1. Yargıtay

1. Tarayıcıda aç: <https://karararama.yargitay.gov.tr/>
2. **F12** → **Network** sekmesi
3. Sol üst: kayıt aktif olsun (kırmızı yuvarlak); **Fetch/XHR** filtresi seç
4. Site üzerinde:
   - "Aranacak Kelime" kutusuna `icra` yaz
   - "Hukuk Daireleri" seç → 12. Hukuk Dairesi
   - **Ara** butonuna bas
5. Network panelinde yeni bir POST isteği belirir (büyük ihtimalle `aramalist` ya da `aramadetaylist`)
6. O isteğe sağ tık → **Copy** → **Copy as cURL (bash)**
7. Yapıştırdığını bana gönder, ya da en azından:
   - **Request URL** (tam URL)
   - **Request Headers** (özellikle `Content-Type`, `X-CSRF-Token` varsa)
   - **Request Payload** (JSON body — Headers altında "Payload" sekmesi)
   - **Response** snippet'ı (ilk 500 karakter)

### 2. Danıştay

Aynısını <https://karararama.danistay.gov.tr/> için yap.

### 3. UYAP Emsal

<https://emsal.uyap.gov.tr/> için yap — bu en sert korumalı, captcha çıkabilir.

## Ne kontrol ediyoruz?

| Bilgi | Neden gerekli |
|---|---|
| Tam endpoint URL | `https://karararama.x.gov.tr/aramalist` mu yoksa farklı bir path mi? |
| Method (POST/GET) | Genelde POST ama bazıları GET |
| Content-Type | `application/json` mı `x-www-form-urlencoded` mu? |
| Payload yapısı | `{data: {...}}` wrapped mı yoksa flat mı? Field isimleri ne? |
| CSRF/Auth token | Bir kerelik token sayfa load'ta veriliyor mu? |
| Response yapısı | Sonuçlar `data.data` mı `results` mı `rows` mu? |

## Hızlı Yöntem — Otomatik Probe

Eğer Network sekmesini incelemek istemiyorsan, otomatik probe çalıştır:

```bash
python3 scripts/probe_yargitay.py
python3 scripts/probe_danistay.py
```

Bu scriptler birkaç yaygın endpoint varyasyonu deniyor. Çıktıdan hangisi JSON
döndürürse, ona göre scraper'ı kalibre ederiz.

## Probe Çıktısını Yapıştır

Yukarıdaki scriptlerden gelen output'u (ya da Chrome Network çıktısını) bana
yapıştır — scraper'daki `payload` yapısını ve `_pick` parse path'lerini dakikalar
içinde düzeltirim.
