"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { StickyNote } from "lucide-react";

type Not = { id: string; baslik: string | null; icerik: string; etiketler: string[] };

/**
 * Bağlamsal not hatırlatması: verilen metinle/konuyla eşleşen kullanıcı notlarını
 * "hatırlatma" olarak gösterir. Girişsiz kullanıcıda (401) sessizce gizlenir.
 */
export function NotHatirlatma({ q }: { q: string }) {
  const [notlar, setNotlar] = useState<Not[]>([]);

  useEffect(() => {
    const sorgu = (q || "").trim();
    if (sorgu.length < 3) {
      setNotlar([]);
      return;
    }
    let alive = true;
    const t = setTimeout(async () => {
      try {
        const r = await fetch(`/api/proxy/notlar/ilgili?q=${encodeURIComponent(sorgu)}`, { cache: "no-store" });
        if (!r.ok) return; // 401/diğer → gösterme
        const j = await r.json();
        if (alive) setNotlar((j?.data ?? j)?.notlar ?? []);
      } catch {
        /* sessiz */
      }
    }, 500); // debounce — yazarken her tuşta istek atma
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q]);

  if (notlar.length === 0) return null;

  return (
    <div className="rounded-lg border border-amber-300/60 bg-amber-50 dark:bg-amber-950/20 p-3 text-sm">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="flex items-center gap-2 font-medium text-amber-800 dark:text-amber-200">
          <StickyNote className="h-4 w-4" /> Bu konuyla ilgili notların
        </span>
        <Link href="/app/notlar" className="text-xs text-amber-700 dark:text-amber-300 underline shrink-0">
          Notlarım
        </Link>
      </div>
      <ul className="space-y-1.5">
        {notlar.map((n) => (
          <li key={n.id} className="text-amber-900/90 dark:text-amber-100/90 leading-snug">
            • {n.baslik ? <strong>{n.baslik}: </strong> : null}
            {n.icerik.length > 180 ? n.icerik.slice(0, 180) + "…" : n.icerik}
          </li>
        ))}
      </ul>
    </div>
  );
}
