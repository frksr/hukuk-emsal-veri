"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, FileText, Search, Coins } from "lucide-react";
import { CountUp } from "@/components/count-up";
import { Skeleton } from "@/components/ui/skeleton";

// Modül anahtarı → kısa Türkçe etiket (kredi kırılımı için).
const MODUL_ETIKET: Record<string, string> = {
  arama: "Emsal Arama",
  dilekce: "Dilekçe",
  ihtarname: "İhtarname",
  ozet: "Karar Özeti",
  denetim: "Belge Denetimi",
  karsi_argument: "Karşı Argüman",
  sozlesme: "Sözleşme Analizi",
  kvkk: "KVKK",
};

type Stat = {
  icon: typeof Activity;
  label: string;
  value: number;
  renk: string;
  href?: string;
  title?: string;
};

/** Dashboard mini istatistik şeridi — /me/rapor verisinden beslenir. */
export function DashboardStats() {
  const [stats, setStats] = useState<Stat[] | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch("/api/proxy/me/rapor", { cache: "no-store" });
        if (!r.ok) { if (alive) setStats([]); return; }
        const d = (await r.json())?.data ?? {};
        const araclar: any[] = d.araclar ?? [];
        const son30 = araclar.reduce((s, a) => s + (a.son30 ?? 0), 0);

        // Kredi: modül başına ayrı tutulur. Tek modülde kredi varsa o modülü
        // adıyla göster; birden fazlaysa toplam + kaç modül + tooltip kırılımı.
        const krediGirdiler = Object.entries((d.krediler ?? {}) as Record<string, number>)
          .filter(([, n]) => (n ?? 0) > 0);
        const krediToplam = krediGirdiler.reduce((s, [, n]) => s + (n ?? 0), 0);

        let krediLabel = "Ek paket kredisi";
        let krediTitle = "Henüz ek paket krediniz yok.";
        if (krediGirdiler.length === 1) {
          const [m, n] = krediGirdiler[0];
          krediLabel = `${MODUL_ETIKET[m] ?? m} kredisi`;
          krediTitle = `${MODUL_ETIKET[m] ?? m}: ${n} kredi`;
        } else if (krediGirdiler.length > 1) {
          krediLabel = `Ek paket · ${krediGirdiler.length} modül`;
          krediTitle = krediGirdiler
            .map(([m, n]) => `${MODUL_ETIKET[m] ?? m}: ${n}`)
            .join(" · ");
        }

        if (!alive) return;
        setStats([
          { icon: Activity, label: "Son 30 gün işlem", value: son30, renk: "text-primary" },
          { icon: FileText, label: "Toplam üretim", value: d.uretim_toplam ?? 0, renk: "text-accent" },
          { icon: Search, label: "Toplam arama", value: d.arama_toplam ?? 0, renk: "text-emerald-600 dark:text-emerald-400" },
          {
            icon: Coins, label: krediLabel, value: krediToplam,
            renk: "text-amber-600 dark:text-amber-400",
            href: "/app/ayarlar/ek-paketler", title: krediTitle,
          },
        ]);
      } catch {
        if (alive) setStats([]);
      }
    })();
    return () => { alive = false; };
  }, []);

  if (stats === null) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[68px]" />)}
      </div>
    );
  }
  if (stats.length === 0) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 stagger">
      {stats.map((s) => {
        const inner = (
          <>
            <span className={`rounded-lg bg-muted p-2 ${s.renk}`}>
              <s.icon className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <div className="text-xl font-bold tabular-nums leading-none">
                <CountUp value={s.value} />
              </div>
              <div className="text-[11px] text-muted-foreground truncate mt-1">{s.label}</div>
            </div>
          </>
        );
        const cls = "hover-lift rounded-lg border bg-card p-3 flex items-center gap-3";
        return s.href ? (
          <Link key={s.label} href={s.href} title={s.title} className={cls}>
            {inner}
          </Link>
        ) : (
          <div key={s.label} className={cls} title={s.title}>
            {inner}
          </div>
        );
      })}
    </div>
  );
}
