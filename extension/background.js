/**
 * background.js — MV3 service worker.
 *
 * Neden burada fetch ediyoruz, content-script'te değil?
 * content-script.js, UYAP sayfasının origin'inde çalışır ve sayfanın
 * CSP/CORS kısıtlarına tabidir (api.hukukcuyapayzekasi.com'a doğrudan
 * fetch atamaz). Background service worker ise manifest'teki
 * `host_permissions` sayesinde bu domain'e CORS'suz erişebilir. Bu yüzden
 * content-script sadece veriyi toplar, gerçek API çağrısını buraya
 * (chrome.runtime.sendMessage ile) devreder.
 *
 * Kimlik doğrulama: kullanıcının panelden ürettiği "uyapext_..." kişisel
 * erişim anahtarı chrome.storage.local'de saklanır (bkz. popup.js) ve her
 * istekte Authorization: Bearer header'ı olarak gönderilir.
 */

const DEFAULT_API_BASE = "https://api.hukukcuyapayzekasi.com";

async function getSettings() {
  const { apiBaseUrl, apiToken } = await chrome.storage.local.get(["apiBaseUrl", "apiToken"]);
  return {
    apiBaseUrl: (apiBaseUrl || DEFAULT_API_BASE).replace(/\/+$/, ""),
    apiToken: apiToken || null,
  };
}

async function uploadDocument({ filename, dataUrl, mime }) {
  const { apiBaseUrl, apiToken } = await getSettings();
  if (!apiToken) {
    return { ok: false, message: "Önce eklenti simgesinden erişim anahtarınızı girin." };
  }

  // dataUrl (content-script'ten base64 data URL olarak gelir) -> Blob.
  // Service worker'da doğrudan fetch(dataUrl) çalışır; bu en basit ve
  // güvenilir dönüşüm yoludur (FileReader service worker'da yok).
  let blob;
  try {
    const res = await fetch(dataUrl);
    blob = await res.blob();
  } catch (e) {
    return { ok: false, message: `Dosya hazırlanamadı: ${e}` };
  }

  const fd = new FormData();
  fd.append("file", new File([blob], filename, { type: mime || blob.type || "application/octet-stream" }));
  fd.append("title", filename);

  try {
    const r = await fetch(`${apiBaseUrl}/api/uyap/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${apiToken}` },
      body: fd,
    });
    const j = await r.json().catch(() => null);
    if (!r.ok) {
      return { ok: false, message: j?.message || `Yükleme başarısız (HTTP ${r.status}).` };
    }
    return { ok: true, data: j?.data };
  } catch (e) {
    return { ok: false, message: `Bağlantı hatası: ${e}` };
  }
}

async function testConnection() {
  const { apiBaseUrl, apiToken } = await getSettings();
  if (!apiToken) return { ok: false, message: "Anahtar girilmemiş." };
  try {
    const r = await fetch(`${apiBaseUrl}/api/uyap/?limit=1`, {
      headers: { Authorization: `Bearer ${apiToken}` },
    });
    if (r.status === 401) return { ok: false, message: "Anahtar geçersiz veya iptal edilmiş." };
    if (r.status === 402) return { ok: false, message: "Bu hesapta UYAP eklentili plan aktif değil." };
    if (!r.ok) return { ok: false, message: `Sunucu hatası (HTTP ${r.status}).` };
    return { ok: true, message: "Bağlantı başarılı." };
  } catch (e) {
    return { ok: false, message: `Bağlanılamadı: ${e}` };
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "UPLOAD_DOCUMENT") {
    uploadDocument(msg.payload).then(sendResponse);
    return true; // async yanıt
  }
  if (msg?.type === "TEST_CONNECTION") {
    testConnection().then(sendResponse);
    return true;
  }
  return false;
});
