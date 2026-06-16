import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Tailwind sınıflarını güvenli birleştir.
 *  cn("p-2", condition && "bg-red-500", "p-4") -> "bg-red-500 p-4"
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Türk Lirası formatlama. Locale "tr-TR".
 */
export function formatTRY(
  value: number | string | null | undefined,
  options?: { fractionDigits?: number; withSymbol?: boolean }
): string {
  const fractionDigits = options?.fractionDigits ?? 2;
  const withSymbol = options?.withSymbol ?? true;
  const num =
    typeof value === "string" ? Number(value.replace(/,/g, ".")) : value ?? 0;
  if (!Number.isFinite(num)) return withSymbol ? "0,00 ₺" : "0,00";

  const formatted = new Intl.NumberFormat("tr-TR", {
    style: withSymbol ? "currency" : "decimal",
    currency: "TRY",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(num as number);

  return formatted;
}

/**
 * Türkçe tarih formatlama. Default: "14 Mayıs 2026".
 */
export function formatTarih(
  input: string | number | Date | null | undefined,
  options?: Intl.DateTimeFormatOptions
): string {
  if (!input) return "";
  const d = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat(
    "tr-TR",
    options ?? { day: "numeric", month: "long", year: "numeric" }
  ).format(d);
}

/**
 * Tarih + saat formatlama. "14 Mayıs 2026 14:30".
 */
export function formatTarihSaat(input: string | number | Date | null | undefined): string {
  return formatTarih(input, {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Türkçe karakter güvenli URL slug üretici.
 * "İstanbul Bölge Adliye" -> "istanbul-bolge-adliye"
 */
export function slugify(input: string): string {
  const trMap: Record<string, string> = {
    ç: "c", Ç: "c",
    ğ: "g", Ğ: "g",
    ı: "i", I: "i",
    İ: "i",
    ö: "o", Ö: "o",
    ş: "s", Ş: "s",
    ü: "u", Ü: "u",
  };
  return input
    .replace(/[çÇğĞıIİöÖşŞüÜ]/g, (m) => trMap[m] ?? m)
    .toLocaleLowerCase("tr-TR")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

/**
 * Güvenli truncate (kelime sınırına).
 */
export function truncate(text: string, max: number, suffix = "…"): string {
  if (!text) return "";
  if (text.length <= max) return text;
  const sliced = text.slice(0, max);
  const lastSpace = sliced.lastIndexOf(" ");
  return (lastSpace > 0 ? sliced.slice(0, lastSpace) : sliced) + suffix;
}

/**
 * Basit absolute URL oluşturucu (SSR güvenli).
 */
export function absoluteUrl(path: string): string {
  const base =
    process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalized}`;
}
