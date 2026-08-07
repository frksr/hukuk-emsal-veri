/**
 * API client — typed fetch wrapper.
 * Tüm backend çağrıları buradan geçer; tek noktada error handling, retry,
 * abort signal ve timeout.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DEFAULT_TIMEOUT_MS = 30_000;

// -----------------------------------------------------------------------------
// Tipler
// -----------------------------------------------------------------------------

export interface ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;
}

export type Mahkeme = "yargitay" | "danistay" | "aym" | "aihm" | "bam";

/**
 * Backend `POST /api/arama` yanıtındaki tek sonuç.
 *
 * DİKKAT — bu arayüz `api/schemas.py :: EmsalKarar` ile BİREBİR eşleşmelidir.
 * Daha önce burada tamamen farklı alanlar (id/mahkeme/esas_no/baslik/ozet…)
 * tanımlıydı; tüketen bileşen ise gerçek alanları (chunk_id/court_chamber/
 * case_no/text/similarity) kullanıyordu. Ortak tek bir alan bile yoktu.
 * `next.config.mjs`'de `typescript.ignoreBuildErrors: true` olduğu için bu
 * uyuşmazlık prod build'inde sessizce geçiyordu — yani tip güvenliği fiilen
 * yoktu. Tipi gerçek sözleşmeye hizaladık; CI'daki `tsc --noEmit` artık
 * gerçek bir kapıdır.
 */
export interface EmsalKarar {
  /** Benzersiz parça kimliği — liste anahtarı olarak kullanılır. */
  chunk_id: string;
  /** Kararın ilgili parçasının metni. */
  text: string;
  /** Kosinüs benzerliği (0-1). */
  similarity: number;
  /** Kararın tamamına giden kimlik (/karar/[id]). */
  decision_id?: string | null;
  source?: string | null;
  court_chamber?: string | null;
  case_no?: string | null;
  decision_no?: string | null;
  decision_date?: string | null;
  /** Backend virgülle ayrılmış tek string döner (dizi DEĞİL). */
  topic_tags?: string | null;
  source_url?: string | null;
  /** Sonucun hangi arama yolundan geldiği: vektör / tam metin / ikisi. */
  rank_kaynak?: "vektor" | "tam_metin" | "hibrit";
}

/** `POST /api/arama` istek gövdesi — `api/schemas.py :: AramaIstegi`. */
export interface AramaParams {
  query: string;
  k?: number;
  source?: string | null;
  court_chamber?: string | null;
}

export interface DilekceParams {
  durum: string;
  dilekce_turu: string;
  taraflar?: { alacakli?: string; borclu?: string };
  k?: number;
  /** Dropdown'daki 5 sabit türe girmeyen davalar için serbest yazılan konu
   * (örn. "Boşanma Davası"). Verilirse KONU başlığı ve gerekçe buna göre üretilir. */
  ozel_konu?: string;
}

/** `POST /api/ozet/text` — `api/schemas.py :: OzetIstegi`. */
export interface OzetParams {
  karar_metni: string;
  uzunluk?: "kisa" | "orta" | "detayli";
}

/** `services/karar_ozet.py :: ozet_uret()` dönüş şeması. */
export interface OzetSonuc {
  /** Markdown biçiminde özet. */
  ozet: string;
  anahtar_noktalar: string[];
  ilgili_kanunlar: string[];
  model: string;
  kaynak_char_count: number;
  uzunluk?: string;
  yasal_not?: string;
}

export interface FaizParams {
  anapara: number;
  temerrut_tarihi: string;
  vade_tarihi: string;
  // Form'daki <select> düz string tuttuğu için burada da geniş tip kullanılır;
  // backend geçersiz değeri 400 ile reddeder (bkz. api/routers/faiz.py).
  faiz_turu: "yasal" | "ticari_avans" | "tcmb_reeskont" | "ttk_1530" | (string & {});
}

/** Yıl içinde oran değiştiyse (örn. 2026: 31 Temmuz kırılımı) aynı yıl için
 * birden fazla dönem satırı üretilir — bkz. services/faiz_hesaplayici.py. */
export interface FaizDonemSatiri {
  yil: number;
  baslangic: string;
  bitis: string;
  gun: number;
  oran: number;
  faiz: string;
}

export interface FaizSonucu {
  anapara: string;
  faiz_baslangic: string;
  faiz_bitis: string;
  gun_sayisi: number;
  faiz_tutari: string;
  cezaevi_harci: string;
  tahsil_harci: string;
  vekalet_ucreti: string;
  toplam_alacak: string;
  yillik_breakdown: FaizDonemSatiri[];
  uyari: string;
}

/** Geriye dönük uyumluluk için takma ad. */
export type FaizSonuc = FaizSonucu;

/** `POST /api/zamanasimi` — `api/schemas.py :: ZamanasimiIstegi` ile eşleşir. */
export interface ZamanasimiParams {
  kategori: string;
  alt_tip: string;
  /** ISO tarih (YYYY-MM-DD) */
  olay_tarihi: string;
  kesilme_tarihleri?: string[];
}

export interface ZamanasimiSonucu {
  zamanasimi_suresi_yil: number;
  son_tarih: string;
  kalan_gun: number;
  aciklama: string;
  ilgili_madde?: string;
}

/** `POST /api/ihtarname` — `api/schemas.py :: IhtarnameIstegi` ile eşleşir. */
export interface IhtarnameParams {
  tur: string;
  /** alacakli_ad / alacakli_adres / borclu_ad / borclu_adres */
  taraflar: Record<string, string>;
  /** anapara, vade_tarihi, neden, faiz_orani, dayanak_belge */
  alacak_detay: Record<string, unknown>;
  ek_talepler?: string[];
}

export interface TrendData {
  yil: number;
  toplam_karar: number;
  konu_dagilimi?: Record<string, number>;
}

/** `POST /api/karsi-argument` — `api/schemas.py :: KarsiArgumentIstegi`. */
export interface KarsiArgumentParams {
  kendi_tezi: string;
  dava_turu?: string | null;
  /** Kaç emsal getirilsin (3-10). */
  k?: number;
}

/** `POST /api/kvkk/checklist` — `api/schemas.py :: KVKKIstegi`. */
export interface KvkkChecklistParams {
  sektor: string;
  veri_turleri: string[];
  sirket_buyuklugu?: string;
  /** Yapay zeka ile sektöre özel ek maddeler (ücretli plan). */
  llm_ek?: boolean;
}

/** `POST /api/sozlesme/analyze-text` — `api/routers/sozlesme.py :: AnalyzeTextIstegi`. */
export interface SozlesmeAnalizParams {
  metin: string;
  sozlesme_turu?: string;
}

// -----------------------------------------------------------------------------
// Core fetch
// -----------------------------------------------------------------------------

interface FetchOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  timeoutMs?: number;
  retry?: number;
}

async function apiFetch<T>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const {
    body,
    headers,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    retry = 0,
    ...rest
  } = options;

  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const init: RequestInit = {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...headers,
    },
    signal: controller.signal,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  try {
    const res = await fetch(url, init);
    clearTimeout(timeoutId);

    if (!res.ok) {
      let details: unknown = undefined;
      try {
        details = await res.json();
      } catch {
        /* ignore */
      }
      const err: ApiError = Object.assign(
        new Error(`API ${res.status}: ${res.statusText}`),
        {
          status: res.status,
          code: `HTTP_${res.status}`,
          details,
        }
      );
      // 5xx için basit retry
      if (res.status >= 500 && retry > 0) {
        await sleep(500 * (DEFAULT_TIMEOUT_MS === timeoutMs ? 1 : 1));
        return apiFetch<T>(path, { ...options, retry: retry - 1 });
      }
      throw err;
    }

    // 204 no content
    if (res.status === 204) return undefined as T;

    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return (await res.json()) as T;
    }
    return (await res.text()) as unknown as T;
  } catch (err) {
    clearTimeout(timeoutId);
    if ((err as Error).name === "AbortError") {
      const e: ApiError = Object.assign(
        new Error("İstek zaman aşımına uğradı"),
        { status: 408, code: "TIMEOUT" }
      );
      throw e;
    }
    throw err;
  }
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

// -----------------------------------------------------------------------------
// Endpoint fonksiyonları
// -----------------------------------------------------------------------------

export async function aramaCagir(
  params: AramaParams,
  init?: { signal?: AbortSignal }
): Promise<EmsalKarar[]> {
  // Proxy üzerinden: NextAuth JWT eklenir → backend aramayı KULLANICIYA bağlı loglar
  // (usage_events + user_searches). Böylece raporlara/dashboard'a yansır.
  // proxyPost zaten zarfı açıp data'yı döndürür.
  const arr = await proxyPost<EmsalKarar[]>("arama", params, init);
  return Array.isArray(arr) ? arr : [];
}

export function dilekceCagir(
  params: DilekceParams,
  init?: { signal?: AbortSignal }
): Promise<{ dilekce_metni: string; uyarilar?: string[] }> {
  return apiFetch("/api/dilekce", {
    method: "POST",
    body: params,
    signal: init?.signal,
    timeoutMs: 60_000,
  });
}

/** Hızlı şablon dilekçe (LLM'siz, ücretsiz). Backend zarfını açıp data döndürür. */
export async function dilekceSablon(
  params: DilekceParams,
  init?: { signal?: AbortSignal }
): Promise<{ dilekce_metni: string; kullanilan_emsaller: unknown[]; uyari?: string }> {
  // Proxy üzerinden → kullanıcı token'ı gider, backend üretimi kullanıcıya bağlı loglar.
  return proxyPost("dilekce/sablon", params, init);
}

export function ozetCagir(
  params: OzetParams,
  init?: { signal?: AbortSignal }
): Promise<{ ozet: string; anahtar_kelimeler?: string[] }> {
  return apiFetch("/api/ozet", {
    method: "POST",
    body: params,
    signal: init?.signal,
  });
}

export async function faizHesapla(params: FaizParams): Promise<FaizSonucu> {
  // Proxy üzerinden → kullanıcı token'ı gider, kullanım rapora yansır. data açılır.
  return proxyPost<FaizSonucu>("faiz", params);
}

export async function zamanasimiHesapla(
  params: ZamanasimiParams
): Promise<ZamanasimiSonucu> {
  return proxyPost<ZamanasimiSonucu>("zamanasimi", params);
}

export async function ihtarnameOlustur(
  params: IhtarnameParams,
  init?: { signal?: AbortSignal }
): Promise<{ ihtarname_metni: string; yasa_referanslari?: string[]; [k: string]: unknown }> {
  // Proxy üzerinden: AI ihtarname Pro plan ister (auth JWT eklenir, backend kontrol eder).
  const r = await fetch("/api/proxy/ihtarname", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
    signal: init?.signal,
  });
  if (r.status === 401 || r.status === 402) {
    throw Object.assign(new Error("Yapay Zeka ihtarname Pro aboneliğe özeldir."), { status: r.status });
  }
  if (!r.ok) throw new Error("İhtarname üretilemedi. Lütfen tekrar deneyin.");
  const j = await r.json();
  return j?.data ?? j;
}

export async function trendYillik(
  query?: string
): Promise<{ data: Array<[string, number]>; total: number; filters?: unknown; dummy?: boolean }> {
  // query: hazır query string (örn. "konu_filtresi=icra&kaynak=yargitay")
  const qs = query ? `?${query}` : "";
  // Backend APIResponse zarfını ({ok,data}) açıp payload'ı döndür.
  const res = await apiFetch<{ data: { data: Array<[string, number]>; total: number } }>(
    `/api/trend/yillik${qs}`,
  );
  // any: dinamik tip (lint eklentisi yok)
  return (res?.data ?? res) as any;
}

/**
 * AI endpoint'leri için proxy POST: NextAuth JWT eklenir (Pro plan kontrolü backend'de).
 * Backend zarfını ({ok,data,message}) açıp data döndürür. 401/402'de status'lu hata fırlatır.
 */
async function proxyPost<T = unknown>(
  path: string,
  body: unknown,
  init?: { signal?: AbortSignal }
): Promise<T> {
  const r = await fetch(`/api/proxy/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: init?.signal,
  });
  if (r.status === 401 || r.status === 402) {
    throw Object.assign(new Error("Bu özellik Pro aboneliğe özeldir."), { status: r.status });
  }
  if (!r.ok) {
    let detail = `İstek başarısız (${r.status})`;
    try {
      const j = await r.json();
      if (j?.detail || j?.message) detail = String(j.detail ?? j.message);
    } catch { /* ignore */ }
    throw Object.assign(new Error(detail), { status: r.status });
  }
  const j = await r.json();
  return (j?.data ?? j) as T;
}

// any: dinamik tip (lint eklentisi yok)
export function karsiArgumentCagir(params: KarsiArgumentParams, init?: { signal?: AbortSignal }): Promise<any> {
  return proxyPost("karsi-argument", params, init);
}

// any: dinamik tip (lint eklentisi yok)
export function kvkkChecklist(params: KvkkChecklistParams): Promise<any> {
  return proxyPost("kvkk/checklist", params);
}

// any: dinamik tip (lint eklentisi yok)
export function sozlesmeAnaliz(params: SozlesmeAnalizParams, init?: { signal?: AbortSignal }): Promise<any> {
  return proxyPost("sozlesme/analyze-text", params, init);
}

// Belge Denetim ----------------------------------------------------------------

export type DenetimUyari = {
  kategori: string;
  ciddiyet: "yuksek" | "orta" | "dusuk";
  ilgili_bolum: string;
  sorun: string;
  oneri: string;
};

export type DenetimSonuc = {
  belge_turu: string;
  metin_uzunluk: number;
  genel_risk_skoru: number;
  ozet: string;
  kritik_sorunlar: string[];
  uyarilar: DenetimUyari[];
  eksik_bolumler: string[];
  emsal_uyumsuzluk: Array<{ karar_id: string; neden: string }>;
  guclu_yonler: string[];
  dayanak_emsaller: Array<{ karar_id: string; atif: string; ozet: string; tarih: string }>;
  demo_modu?: boolean;
  yasal_uyari: string;
};

export async function belgeDenetText(
  params: { metin: string; tur?: string; k?: number },
  init?: { signal?: AbortSignal }
): Promise<DenetimSonuc> {
  // Proxy üzerinden (auth + Pro kontrolü backend'de), zarfı açıp data döndür.
  return proxyPost<DenetimSonuc>("denetim/text", params, init);
}

// -----------------------------------------------------------------------------
// Yardımcılar
// -----------------------------------------------------------------------------

export function isApiError(err: unknown): err is ApiError {
  return (
    typeof err === "object" &&
    err !== null &&
    "status" in err &&
    typeof (err as ApiError).status === "number"
  );
}

export const api = {
  arama: aramaCagir,
  dilekce: dilekceCagir,
  ozet: ozetCagir,
  faiz: faizHesapla,
  zamanasimi: zamanasimiHesapla,
  ihtarname: ihtarnameOlustur,
  trendYillik,
  karsiArgument: karsiArgumentCagir,
  kvkkChecklist,
  sozlesmeAnaliz,
};

// -----------------------------------------------------------------------------
// Streaming (SSE) — dilekçe token-token üretim
// -----------------------------------------------------------------------------

export interface DilekceStreamMeta {
  kullanilan_emsaller: Array<{
    karar_id?: string;
    atif_text: string;
    ilgili_bolum: string;
  }>;
  uyari: string;
  demo: boolean;
}

export interface DilekceSonuc {
  dilekce_metni: string;
  kullanilan_emsaller: Array<{ karar_id?: string; atif_text: string; ilgili_bolum: string }>;
  uyari?: string;
}

export interface DilekceStreamHandlers {
  onMeta?: (meta: DilekceStreamMeta) => void;
  onDelta?: (text: string) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
}

/**
 * POST /api/dilekce/stream — SSE akışını okur, event'leri handler'lara dağıtır.
 * fetch + ReadableStream kullanır (EventSource POST desteklemediği için).
 */
export async function dilekceStream(
  params: DilekceParams,
  handlers: DilekceStreamHandlers,
  init?: { signal?: AbortSignal }
): Promise<void> {
  // Proxy üzerinden: NextAuth JWT eklenir (AI dilekçe Pro plan ister).
  const res = await fetch(`/api/proxy/dilekce/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
    signal: init?.signal,
  });

  if (!res.ok || !res.body) {
    let detail = `API ${res.status}`;
    try {
      const j = await res.json();
      if (j?.detail) detail = String(j.detail);
    } catch { /* ignore */ }
    throw Object.assign(new Error(detail), { status: res.status });
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  const processChunk = (raw: string) => {
    const line = raw.trim();
    if (!line.startsWith("data:")) return;
    const payload = line.slice(5).trim();
    if (!payload) return;
    let evt: { type?: string; text?: string; message?: string } & Partial<DilekceStreamMeta>;
    try {
      evt = JSON.parse(payload);
    } catch {
      return;
    }
    switch (evt.type) {
      case "meta":
        handlers.onMeta?.({
          kullanilan_emsaller: evt.kullanilan_emsaller ?? [],
          uyari: evt.uyari ?? "",
          demo: Boolean(evt.demo),
        });
        break;
      case "delta":
        if (evt.text) handlers.onDelta?.(evt.text);
        break;
      case "error":
        handlers.onError?.(evt.message ?? "Akış hatası");
        break;
      case "done":
        handlers.onDone?.();
        break;
    }
  };

  // SSE: event'ler "\n\n" ile ayrılır
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      processChunk(buffer.slice(0, idx));
      buffer = buffer.slice(idx + 2);
    }
  }
  if (buffer.trim()) processChunk(buffer);
}

// -----------------------------------------------------------------------------
// Belge export — .docx / .udf (UYAP) indirme
// -----------------------------------------------------------------------------

export async function exportBelge(
  format: "docx" | "udf",
  params: { metin: string; baslik?: string; dosya_adi?: string }
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/export/${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    let detail = `Export hatası (${res.status})`;
    try {
      const j = await res.json();
      if (j?.detail) detail = String(j.detail);
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const m = cd.match(/filename="?([^";]+)"?/);
  const fname = m?.[1] ?? `${params.dosya_adi ?? "belge"}.${format}`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fname;
  a.click();
  URL.revokeObjectURL(url);
}

// -----------------------------------------------------------------------------
// Kaydedilen kararlar + koleksiyon durumu
// -----------------------------------------------------------------------------

export function aramaStats(): Promise<{
  ok: boolean;
  data: { chunk_count?: number; available: boolean };
}> {
  return apiFetch("/api/arama/stats", { method: "GET" });
}

export interface KararKaydetParams {
  decision_id: string;
  chunk_id?: string;
  klasor?: string;
  baslik?: string;
  ozet?: string;
  meta?: Record<string, unknown>;
  not_metni?: string;
}

export function kararKaydet(params: KararKaydetParams): Promise<unknown> {
  return apiFetch("/api/me/kararlar", { method: "POST", body: params });
}

export function alarmOlustur(params: {
  query: string;
  filters?: Record<string, unknown>;
}): Promise<unknown> {
  return apiFetch("/api/me/alerts", { method: "POST", body: params });
}
