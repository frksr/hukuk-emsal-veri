const DEFAULT_API_BASE = "https://api.hukukcuyapayzekasi.com";

const tokenInput = document.getElementById("token");
const apiBaseInput = document.getElementById("apiBase");
const statusEl = document.getElementById("status");

async function load() {
  const { apiToken, apiBaseUrl } = await chrome.storage.local.get(["apiToken", "apiBaseUrl"]);
  if (apiToken) tokenInput.value = apiToken;
  apiBaseInput.value = apiBaseUrl || DEFAULT_API_BASE;
}

async function persist() {
  const apiToken = tokenInput.value.trim();
  const apiBaseUrl = (apiBaseInput.value.trim() || DEFAULT_API_BASE).replace(/\/+$/, "");
  await chrome.storage.local.set({ apiToken, apiBaseUrl });
  return { apiToken, apiBaseUrl };
}

document.getElementById("save").addEventListener("click", async () => {
  await persist();
  statusEl.textContent = "Kaydedildi.";
  statusEl.className = "ok";
});

document.getElementById("test").addEventListener("click", async () => {
  statusEl.textContent = "Test ediliyor...";
  statusEl.className = "";
  await persist(); // kaydedilmemiş değişiklikleri de test edebilmek için önce kaydet

  const res = await chrome.runtime.sendMessage({ type: "TEST_CONNECTION" });
  statusEl.textContent = res?.message || (res?.ok ? "Bağlantı başarılı." : "Bağlantı başarısız.");
  statusEl.className = res?.ok ? "ok" : "err";
});

load();
