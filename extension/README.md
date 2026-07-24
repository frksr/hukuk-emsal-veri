# UYAP Aktarım — Tarayıcı Eklentisi (MV3)

Avukatın UYAP Avukat Portal'da (`avukat.uyap.gov.tr`) kendi oturumu açıkken
gördüğü belgeleri, sekmeden çıkmadan Hukukçu Yapay Zekası hesabındaki
"Dosyalarım"a aktarmasını sağlar. Eklenti UYAP'a giriş yapmaz, kimlik bilgisi
görmez — yalnızca avukatın zaten açık olan oturumunun üzerine content script
olarak biner (bkz. `content-script.js` başındaki not).

## Durum

Bu iskelet **gerçek Avukat Portal DOM yapısı incelenmeden** yazıldı (bu ortamda
UYAP'a e-imzayla giriş yapılamıyor). Bu yüzden iki katmanlı tasarlandı:

1. **Hızlı Aktar paneli (bugün çalışır):** sağ altta sabit bir sürükle-bırak /
   dosya seçme paneli. Avukat UYAP'tan indirdiği bir dosyayı buraya bırakır,
   sekmeden çıkmadan yüklenir. DOM yapısından tamamen bağımsız.
2. **Otomatik "Siteme Aktar" butonları (kalibrasyon gerekir):** sayfadaki olası
   belge linklerinin yanına otomatik buton ekler. `content-script.js` içindeki
   `CONFIG.linkHeuristics` genel kalıplarla (`.pdf`, `evrakGetir` vb.) çalışmayı
   dener ama gerçek portalla test edilip inceltilmeli.

## Kurulum (geliştirici modu)

1. `chrome://extensions` (veya Edge için `edge://extensions`) açın.
2. "Geliştirici modu"nu açın.
3. "Paketlenmemiş öğe yükle" → bu klasörü (`extension/`) seçin.
4. Eklenti simgesine tıklayıp panelden alınan `uyapext_...` erişim
   anahtarını girin, "Bağlantıyı Test Et" ile doğrulayın.
5. `https://avukat.uyap.gov.tr` adresine gidin — sağ altta panel görünmeli.

Anahtar üretimi: panelde **Ayarlar → UYAP Eklentisi** (`/panel/ayarlar/uyap-eklenti`).

## Kalibrasyon — gerçek portal erişimi olduğunda

Amaç: `content-script.js` içindeki `CONFIG.linkHeuristics`'i gerçek DOM'a göre
sıkılaştırmak/genişletmek, böylece otomatik "Siteme Aktar" butonu doğru
yerlerde çıksın.

1. `avukat.uyap.gov.tr`'ye e-imza ile giriş yapın, bir dosyanın evrak
   listesine gidin.
2. F12 → Elements sekmesinde bir evrak/belge linkine sağ tık → Inspect.
3. Linkin `href` deseni neye benziyor? (örn. `.../evrakGoruntule?id=123` gibi)
   Bunu `CONFIG.linkHeuristics` dizisine bir regex olarak ekleyin.
4. Eğer belgeler `<a href>` değil de JS `onclick`/Angular `(click)` ile
   açılıyorsa: Network sekmesinde belgeye tıklayıp hangi isteğin (XHR/fetch)
   dosyayı döndürdüğünü bulun — URL deseni ve response content-type'ı not
   alın, `fetchAsFile()` ve heuristikleri buna göre güncelleyin.
5. Satır bazlı buton konumlandırması gerekiyorsa (örn. tablo satırının sonuna
   eklemek istiyorsanız) `injectTransferButton()`'daki
   `insertAdjacentElement` hedefini değiştirin.
6. `chrome://extensions` → eklentiyi "Yeniden yükle" ile değişiklikleri test edin.

Bu adımlar, ana projenin `README.md`'sindeki "Yargıtay/Danıştay endpoint
doğrulaması" bölümüyle aynı mantık: canlı sistem zaman zaman değişebileceği
için, otomatik tespit kısmı kalıcı bir "doğrulama gerekir" notuyla bırakıldı.

## Mimari notu

- `content-script.js` UYAP sayfası origin'inde çalışır, sayfanın CORS/CSP
  kısıtlarına tabidir → API'ye doğrudan istek atamaz.
- `background.js` (service worker) `manifest.json`'daki `host_permissions`
  sayesinde `api.hukukcuyapayzekasi.com`'a CORS'suz erişebilir → gerçek
  yükleme isteği burada yapılır.
- Kimlik doğrulama: `chrome.storage.local`'de saklanan `uyapext_...` kişisel
  erişim anahtarı, `Authorization: Bearer` header'ı olarak gönderilir.
  Backend tarafı: `api/auth.py` (`_resolve_extension_token`) +
  `api/routers/extension.py` (üretme/listeleme/iptal).
- Yükleme, mevcut `/api/uyap/upload` endpoint'ini kullanır — panelden manuel
  yüklemeyle aynı doğrulama/parse/KVKK akışından geçer (bkz. `api/routers/uyap.py`).

## Yasal/ToS notu

Eklenti yalnızca avukatın o an görüntülediği/tıkladığı belgeyi aktarır;
arka planda otomatik/toplu UYAP kazıması YAPMAZ. Bu, rakip UYAP entegrasyon
araçlarının (Hukuk Asistan, Av. Asistan vb.) da belirttiği ilkeyle uyumludur.
Tam otomatik arka plan senkronizasyonu ayrı, daha riskli bir kapsamdır ve bu
iskelete dahil edilmedi.
