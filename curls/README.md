# cURL kapture klasörü

Her site için Chrome Network'ten kopyalanan cURL'leri buraya kaydet:
- `danistay.curl`
- `yargitay.curl`
- `aym.curl`
- `uyap.curl`

Sonra:
```bash
python3 scripts/curl_to_config.py curls/danistay.curl
```

Bu komut header/payload/cookie yapısını otomatik parse edip scraper'a yapıştırılacak Python snippet üretir.

**Güvenlik:** cURL'de session ID ve cookie'ler olur, bu klasörü `.gitignore`'a ekle.
