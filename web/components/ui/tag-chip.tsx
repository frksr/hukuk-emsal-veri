import { cn } from "@/lib/utils";

/**
 * Etiket "chip" — baştaki # gösterilmeden, etiket string'ine göre deterministik
 * renkli rozet olarak görünür. Renkler hem açık hem koyu temada okunabilir.
 *
 * Not: yalnızca GÖRÜNÜM. Etiketin gerçek değeri (data) değişmez.
 */

// Hoş, birbiriyle uyumlu pastel/rozet paleti.
// Her giriş: açık tema (bg/text/border) + koyu tema (dark: ...) sınıfları.
const PALET = [
  "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/50 dark:text-blue-300 dark:border-blue-800/60",
  "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800/60",
  "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800/60",
  "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:border-rose-800/60",
  "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950/50 dark:text-violet-300 dark:border-violet-800/60",
  "bg-cyan-50 text-cyan-700 border-cyan-200 dark:bg-cyan-950/50 dark:text-cyan-300 dark:border-cyan-800/60",
  "bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200 dark:bg-fuchsia-950/50 dark:text-fuchsia-300 dark:border-fuchsia-800/60",
  "bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/50 dark:text-teal-300 dark:border-teal-800/60",
  "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/50 dark:text-indigo-300 dark:border-indigo-800/60",
  "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/50 dark:text-orange-300 dark:border-orange-800/60",
];

/** Etiket string'inden deterministik renk indeksi (basit FNV-benzeri hash). */
function etiketRengi(etiket: string): string {
  let h = 0;
  for (let i = 0; i < etiket.length; i++) {
    h = (h * 31 + etiket.charCodeAt(i)) >>> 0;
  }
  return PALET[h % PALET.length];
}

export function TagChip({
  etiket,
  className,
}: {
  etiket: string;
  className?: string;
}) {
  // Baştaki # işaretini görselden temizle (veri değişmez).
  const gosterim = etiket.replace(/^#+/, "");
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
        etiketRengi(etiket),
        className
      )}
    >
      {gosterim}
    </span>
  );
}
