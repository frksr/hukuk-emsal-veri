"use client";
import { useEffect, useState } from "react";
import { Check } from "lucide-react";

type Limits = Record<string, Record<string, number | null>>;

// Modül seviyesi cache → 4 kart tek istekle beslenir.
let _cache: Limits | null = null;

const TOOL_LABEL: Record<string, string> = {
  arama: "emsal arama",
  dilekce: "Yapay Zeka dilekçe",
  ihtarname: "ihtarname",
  ozet: "karar özeti",
  sozlesme: "sözleşme analizi",
};
const TOOL_ORDER = ["arama", "dilekce", "ihtarname", "ozet", "sozlesme"];

function satir(tool: string, limit: number | null): string {
  const label = TOOL_LABEL[tool] ?? tool;
  if (limit === null || limit >= 10000) return `Sınırsız ${label}`;
  return `Ayda ${limit} ${label}`;
}

/**
 * Bir plan (tier) için limit-bazlı özellik satırlarını admin ayarlarından
 * (public /billing/plan-limits) dinamik üretir. Admin limiti değiştirince yansır.
 */
export function PlanLimitler({ tier }: { tier: string }) {
  const [limits, setLimits] = useState<Limits | null>(_cache);

  useEffect(() => {
    if (_cache) { setLimits(_cache); return; }
    let alive = true;
    fetch("/api/proxy/billing/plan-limits", { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => {
        _cache = (j?.data ?? j)?.limits ?? {};
        if (alive) setLimits(_cache);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const tl = limits?.[tier];

  if (!tl) {
    return (
      <ul className="space-y-2">
        {TOOL_ORDER.map((t) => (
          <li key={t} className="h-4 w-2/3 rounded bg-muted animate-pulse" />
        ))}
      </ul>
    );
  }

  return (
    <ul className="space-y-2 text-sm">
      {TOOL_ORDER.map((t) => {
        const lim = tl[t];
        if (lim === 0) return null; // bu plana dahil değil → gösterme
        return (
          <li key={t} className="flex gap-2">
            <Check className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
            <span>{satir(t, lim)}</span>
          </li>
        );
      })}
    </ul>
  );
}
