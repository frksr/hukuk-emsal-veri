/**
 * content-script.js — avukat.uyap.gov.tr üzerinde çalışır.
 *
 * ÖNEMLİ: Bu eklenti gerçek UYAP Avukat Portal DOM yapısı incelenmeden
 * yazıldı (bkz. extension/README.md — kalibrasyon adımları orada). Bu
 * yüzden iki katmanlı çalışır:
 *
 *  1) HER ZAMAN ÇALIŞAN: sağ altta sabit bir "Hızlı Aktar" paneli — avukat
 *     UYAP'tan indirdiği bir dosyayı buraya sürükleyip bırakır veya seçer,
 *     sekmeden hiç çıkmadan yüklenir. Bu, DOM yapısından tamamen bağımsızdır
 *     ve bugün, kalibrasyon yapılmadan da çalışır.
 *
 *  2) OTOMATİK TESPİT (best-effort, CONFIG gerçek portalla kalibre
 *     edilmeli): sayfadaki olası belge linklerinin yanına küçük bir
 *     "Siteme Aktar" butonu enjekte eder. Heuristikler tutmazsa sorun
 *     değil — sadece o link için buton görünmez, panel (1) yine çalışır.
 */

const CONFIG = {
  // Belge linki/butonu heuristiği: href veya onclick bu kalıplardan birine
  // uyuyorsa "muhtemelen indirilebilir belge" say. Gerçek portalda F12 →
  // bir evrağı açtığınızda ağ isteğinin/linkin gerçek deseni görülüp buraya
  // eklenmeli (bkz. README "Kalibrasyon" bölümü).
  linkHeuristics: [
    /\.(pdf|udf|docx?|txt)(\?|#|$)/i,
    /evrakgetir/i,
    /belgegoster/i,
    /dokumangetir/i,
    /dosyaindir/i,
  ],
};

const ALLOWED_EXT = ["pdf", "docx", "doc", "txt", "md", "udf"];

function extOf(name) {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

async function sendToBackground(file) {
  const dataUrl = await blobToDataUrl(file);
  return chrome.runtime.sendMessage({
    type: "UPLOAD_DOCUMENT",
    payload: { filename: file.name, dataUrl, mime: file.type },
  });
}

// ---------------------------------------------------------------------------
// 1) Hızlı Aktar paneli — her zaman çalışır, DOM yapısından bağımsız
// ---------------------------------------------------------------------------
function injectQuickPanel() {
  if (document.getElementById("hyz-ext-panel")) return;

  const panel = document.createElement("div");
  panel.id = "hyz-ext-panel";
  panel.innerHTML = `
    <div class="hyz-ext-header">
      <span>Hukukçu YZ — Hızlı Aktar</span>
      <button class="hyz-ext-toggle" type="button" title="Küçült/Büyüt">–</button>
    </div>
    <div class="hyz-ext-body">
      <div class="hyz-ext-drop" id="hyz-ext-drop">
        Dosyayı buraya sürükleyin<br/>veya seçmek için tıklayın
        <input type="file" id="hyz-ext-file" accept=".pdf,.docx,.doc,.txt,.md,.udf" hidden />
      </div>
      <div class="hyz-ext-status" id="hyz-ext-status"></div>
    </div>
  `;
  document.documentElement.appendChild(panel);

  const body = panel.querySelector(".hyz-ext-body");
  panel.querySelector(".hyz-ext-toggle").addEventListener("click", () => {
    body.style.display = body.style.display === "none" ? "" : "none";
  });

  const drop = panel.querySelector("#hyz-ext-drop");
  const fileInput = panel.querySelector("#hyz-ext-file");
  const status = panel.querySelector("#hyz-ext-status");

  drop.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target.files?.[0]) handleFile(e.target.files[0], status);
  });
  drop.addEventListener("dragover", (e) => {
    e.preventDefault();
    drop.classList.add("hyz-ext-dragover");
  });
  drop.addEventListener("dragleave", () => drop.classList.remove("hyz-ext-dragover"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("hyz-ext-dragover");
    if (e.dataTransfer.files?.[0]) handleFile(e.dataTransfer.files[0], status);
  });
}

async function handleFile(file, statusEl) {
  const ext = extOf(file.name);
  if (!ALLOWED_EXT.includes(ext)) {
    statusEl.textContent = `Desteklenmeyen format: .${ext || "?"}`;
    statusEl.className = "hyz-ext-status hyz-ext-error";
    return;
  }
  statusEl.textContent = `Yükleniyor: ${file.name}...`;
  statusEl.className = "hyz-ext-status";
  const res = await sendToBackground(file);
  if (res?.ok) {
    statusEl.textContent = `✓ Aktarıldı: ${file.name}`;
    statusEl.className = "hyz-ext-status hyz-ext-success";
  } else {
    statusEl.textContent = `✗ ${res?.message || "Yükleme başarısız."}`;
    statusEl.className = "hyz-ext-status hyz-ext-error";
  }
}

// ---------------------------------------------------------------------------
// 2) Otomatik belge tespiti (best-effort)
// ---------------------------------------------------------------------------
function looksLikeDocumentLink(el) {
  const href = el.getAttribute("href") || "";
  const onclick = el.getAttribute("onclick") || "";
  const combined = `${href} ${onclick}`;
  return CONFIG.linkHeuristics.some((re) => re.test(combined));
}

async function fetchAsFile(url, suggestedName) {
  // credentials: "include" — avukatın UYAP oturum cookie'siyle AYNI origin'den
  // isteniyor; tarayıcı cookie'yi otomatik ekler, biz kimlik bilgisi görmeyiz.
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const match = cd.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
  const name = (match ? decodeURIComponent(match[1]) : suggestedName) || "belge";
  return new File([blob], name, { type: blob.type });
}

function injectTransferButton(anchor) {
  if (anchor.dataset.hyzExtDone) return;
  anchor.dataset.hyzExtDone = "1";

  const btn = document.createElement("button");
  btn.textContent = "Siteme Aktar";
  btn.className = "hyz-ext-inline-btn";
  btn.type = "button";
  btn.addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const original = btn.textContent;
    btn.textContent = "Aktarılıyor...";
    btn.disabled = true;
    try {
      const url = anchor.href || anchor.getAttribute("href");
      const file = await fetchAsFile(url, anchor.textContent?.trim() || "belge.pdf");
      const res = await sendToBackground(file);
      btn.textContent = res?.ok ? "✓ Aktarıldı" : "✗ Hata";
      if (!res?.ok) console.warn("[HYZ UYAP Aktarım]", res?.message);
    } catch (err) {
      btn.textContent = "✗ Hata";
      console.warn("[HYZ UYAP Aktarım] belge alınamadı:", err);
    } finally {
      btn.disabled = false;
      setTimeout(() => { btn.textContent = original; }, 3000);
    }
  });
  anchor.insertAdjacentElement("afterend", btn);
}

function scanForDocumentLinks(root = document) {
  try {
    root.querySelectorAll("a[href]").forEach((a) => {
      if (looksLikeDocumentLink(a)) injectTransferButton(a);
    });
  } catch (e) {
    // Sayfa yapısı beklenmedik olabilir — sessizce yut, panel (1) yine çalışır.
  }
}

// ---------------------------------------------------------------------------
// Başlat
// ---------------------------------------------------------------------------
injectQuickPanel();
scanForDocumentLinks();

// UYAP Avukat Portal (yeni arayüz) büyük ölçüde SPA — sayfa içeriği route
// değişince yeniden render olur. MutationObserver ile yeni eklenen linkleri
// de yakala.
const observer = new MutationObserver((mutations) => {
  for (const m of mutations) {
    if (m.addedNodes.length > 0) {
      scanForDocumentLinks(document);
      break;
    }
  }
});
observer.observe(document.body, { childList: true, subtree: true });
