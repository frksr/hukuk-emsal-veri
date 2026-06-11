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

export interface EmsalKarar {
  id: string;
  mahkeme: Mahkeme;
  daire?: string;
  esas_no?: string;
  karar_no?: string;
  karar_tarihi?: string;
  baslik?: string;
  ozet?: string;
  metin?: string;
  konular?: string[];
  url?: string;
  benzerlik_skoru?: number;
}

export interface AramaParams {
  q: string;
  mahkeme?: Mahkeme | Mahkeme[];
  tarih_baslangic?: string;
  tarih_bitis?: string;
  konu?: string;
  limit?: number;
  offset?: number;
}

export interface AramaSonucu {
  toplam: number;
  sonuclar: EmsalKarar[];
  arama_suresi_ms?: number;
}

export interface DilekceParams {
  konu: string;
  taraflar?: { davaci?: string; davali?: string };
  olaylar: string;
  talep: string;
  mahkeme?: string;
  ekler?: string[];
}

export interface OzetParams {
  metin: string;
  uzunluk?: "kisa" | "orta" | "uzun";
}

export interface FaizParams {
  anapara: number;
  baslangic_tarihi: string;
  bitis_tarihi: string;
  faiz_tipi: "yasal" | "ticari" | "avans" | "temerrut";
  faiz_orani?: number;
}

export interface FaizSonucu {
  anapara: number;
  faiz_tutari: number;
  toplam: number;
  gun_sayisi: number;
  detay?: Array<{ tarih: string; oran: number; tutar: number }>;
}

export interface ZamanasimiParams {
  hukuk_alani: string;
  olay_tarihi: string;
  ek_bilgiler?: Record<string, unknown>;
}

export interface ZamanasimiSonucu {
  zamanasimi_suresi_yil: number;
  son_tarih: string;
  kalan_gun: number;
  aciklama: string;
  ilgili_madde?: string;
}

export interface IhtarnameParams {
  borclu: { ad_soyad: string; adres?: string; tc_kimlik?: string };
  alacakli: { ad_soyad: string; adres?: string };
  borc_tutari: number;
  borc_aciklama: string;
  son_odeme_tarihi: string;
}

export interface TrendData {
  yil: number;
  toplam_karar: number;
  konu_dagilimi?: Record<string, number>;
}

export interface KarsiArgumentParams {
  iddia: string;
  baglam?: string;
  hukuk_alani?: string;
}

export interface KvkkChecklistParams {
  sektor: string;
  veri_isleme_tipi: string[];
  calisan_sayisi?: number;
}

export interface SozlesmeAnalizParams {
  metin: string;
  sozlesme_tipi?: string;
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

export function aramaCagir(
  params: AramaParams,
  init?: { signal?: AbortSignal }
): Promise<AramaSonucu> {
  return apiFetch<AramaSonucu>("/api/arama", {
    method: "POST",
    body: params,
    signal: init?.signal,
    retry: 1,
  });
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

export function faizHesapla(params: FaizParams): Promise<FaizSonucu> {
  return apiFetch<FaizSonucu>("/api/faiz", {
    method: "POST",
    body: params,
  });
}

export function zamanasimiHesapla(
  params: ZamanasimiParams
): Promise<ZamanasimiSonucu> {
  return apiFetch<ZamanasimiSonucu>("/api/zamanasimi", {
    method: "POST",
    body: params,
  });
}

export function ihtarnameOlustur(
  params: IhtarnameParams,
  init?: { signal?: AbortSignal }
): Promise<{ ihtarname_metni: string; pdf_url?: string }> {
  return apiFetch("/api/ihtarname", {
    method: "POST",
    body: params,
    signal: init?.signal,
    timeoutMs: 60_000,
  });
}

export function trendYillik(params: {
  yil_baslangic?: number;
  yil_bitis?: number;
  konu?: string;
  mahkeme?: Mahkeme;
}): Promise<{ veriler: TrendData[] }> {
  const qs = new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)])
  ).toString();
  return apiFetch(`/api/trend/yillik${qs ? `?${qs}` : ""}`);
}

export function karsiArgumentCagir(
  params: KarsiArgumentParams,
  init?: { signal?: AbortSignal }
): Promise<{ karsi_argumanlar: Array<{ baslik: string; aciklama: string; emsal?: EmsalKarar[] }> }> {
  return apiFetch("/api/karsi-argument", {
    method: "POST",
    body: params,
    signal: init?.signal,
    timeoutMs: 60_000,
  });
}

export function kvkkChecklist(
  params: KvkkChecklistParams
): Promise<{ checklist: Array<{ madde: string; aciklama: string; tamamlandi?: boolean }> }> {
  return apiFetch("/api/kvkk-checklist", {
    method: "POST",
    body: params,
  });
}

export function sozlesmeAnaliz(
  params: SozlesmeAnalizParams,
  init?: { signal?: AbortSignal }
): Promise<{
  risk_skoru: number;
  bulgular: Array<{ madde: string; risk: "dusuk" | "orta" | "yuksek"; aciklama: string }>;
  oneriler?: string[];
}> {
  return apiFetch("/api/sozlesme-analiz", {
    method: "POST",
    body: params,
    signal: init?.signal,
    timeoutMs: 90_000,
  });
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

export function belgeDenetText(
  params: { metin: string; tur?: string; k?: number },
  init?: { signal?: AbortSignal }
): Promise<DenetimSonuc> {
  return apiFetch<DenetimSonuc>("/api/denetim/text", {
    method: "POST",
    body: params,
    signal: init?.signal,
    timeoutMs: 90_000,
  });
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
  const res = await fetch(`${API_BASE}/api/dilekce/stream`, {
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
