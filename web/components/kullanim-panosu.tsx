"use client";
/**
 * Kullanım panosu — araç bazlı bugünkü / dönemlik kullanım çubukları.
 * Backend: GET /api/proxy/me/kullanim (api/routers/kullanim.py).
 * limit === null → "Sınırsız".
 */
import { useEffect, useState } from "react";
import { Gauge } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Kalem = {
  tool: string;
  etiket: string;
  used: number;
  limit: number | null;
};

type Pano = {
  tier: string;
  gunluk: Kalem[];
  aylik: Kalem[];
  donem_bitis: string;
};

function CubukSatir({ k }: { k: Kalem }) {
  const sinirsiz = k.limit === null;
  const oran = sinirsiz ? 0 : Math.min(100, Math.round((k.used * 100) / Math.max(k.limit as number, 1)));
  const renk =
    oran >= 90 ? "bg-destructive" : oran >= 70 ? "bg-amber-500" : "bg-primary";
  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="font-medium truncate">{k.etiket}</span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {sinirsiz ? (
            <span className="rounded-full border border-emerald-400/30 bg-emerald-400/15 px-2 py-0.5 text-[10px] uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
              Sınırsız
            </span>
          ) : (
            <>
              {k.used} / {k.limit}
            </>
          )}
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-secondary">
        <div
          className={`h-full rounded-full transition-all ${sinirsiz ? "w-full bg-emerald-400/40" : renk}`}
          style={sinirsiz ? undefined : { width: `${oran}%` }}
        />
      </div>
    </div>
  );
}

export function KullanimPanosu() {
  const [pano, setPano] = useState<Pano | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [sekme, setSekme] = useState<"gunluk" | "aylik">("gunluk");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch("/api/proxy/me/kullanim", { cache: "no-store" });
        if (!r.ok) return;
        const j = await r.json();
        const d = j?.data ?? j;
        if (alive && d?.gunluk) setPano(d as Pano);
      } catch {
        /* yok say — pano opsiyonel */
      } finally {
        if (alive) setYukleniyor(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // Giriş yok / hata → panoyu hiç gösterme (panel akışını bozma).
  if (!yukleniyor && !pano) return null;

  const kalemler = pano ? (sekme === "gunluk" ? pano.gunluk : pano.aylik) : [];
  const donem = pano?.donem_bitis
    ? new Date(pano.donem_bitis).toLocaleDateString("tr-TR", { dateStyle: "medium" })
    : null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Gauge className="h-4 w-4 text-primary" /> Kullanım Panosu
          </CardTitle>
          <div className="flex items-center gap-1 rounded-md border bg-secondary/50 p-0.5 text-xs">
            <button
              onClick={() => setSekme("gunluk")}
              className={`rounded px-2 py-1 transition-colors ${
                sekme === "gunluk" ? "bg-background shadow-sm font-medium" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Bugün
            </button>
            <button
              onClick={() => setSekme("aylik")}
              className={`rounded px-2 py-1 transition-colors ${
                sekme === "aylik" ? "bg-background shadow-sm font-medium" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Bu Dönem
            </button>
          </div>
        </div>
        {sekme === "aylik" && donem && (
          <p className="text-xs text-muted-foreground">Kotalar {donem} tarihinde yenilenir.</p>
        )}
      </CardHeader>
      <CardContent>
        {yukleniyor ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg border bg-secondary/40" />
            ))}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {kalemler.map((k) => (
              <CubukSatir key={k.tool} k={k} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
