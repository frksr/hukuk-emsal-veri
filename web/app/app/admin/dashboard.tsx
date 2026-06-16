"use client";
import { useEffect, useState } from "react";
import { Users, TrendingUp, AlertTriangle, Gift, FileText, DollarSign } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { CountUp } from "@/components/count-up";

type Stats = {
  users: { total: number; new_24h: number; new_7d: number; new_30d: number; dau: number; mau: number };
  tiers: Array<{ plan: string; count: number }>;
  revenue: { monthly_try: number; beta_count: number };
  feedback: { open: number; critical: number };
  uyap: { documents: number; queries_30d: number };
};

const TIER_LABEL: Record<string, string> = {
  free: "Free", pro_solo: "Pro Solo", pro_solo_uyap: "Pro + UYAP",
  team: "Team", team_uyap: "Team + UYAP", enterprise: "Enterprise",
};

const TIER_BAR: Record<string, string> = {
  free: "bg-slate-400",
  pro_solo: "bg-blue-500",
  pro_solo_uyap: "bg-indigo-500",
  team: "bg-purple-500",
  team_uyap: "bg-violet-500",
  enterprise: "bg-amber-500",
};

export function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch("/api/proxy/admin/dashboard");
        const j = await r.json();
        if (!r.ok) throw new Error(j.message || "Hata");
        setStats(j.data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Hata");
      } finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return (
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[116px]" />)}
      </div>
    );
  }
  if (error || !stats) {
    return <Card><CardContent className="p-6 text-destructive">⚠ {error || "Veri alınamadı"}</CardContent></Card>;
  }

  const tierTotal = stats.tiers.reduce((a, x) => a + x.count, 0);

  const kpis = [
    {
      icon: Users, label: "Toplam Kullanıcı", value: stats.users.total,
      sub: `+${stats.users.new_24h} (24s) · +${stats.users.new_7d} (7g)`, subRenk: "text-emerald-600 dark:text-emerald-400",
      renk: "text-primary", bg: "bg-primary/10",
    },
    {
      icon: TrendingUp, label: "Aktif (DAU)", value: stats.users.dau,
      sub: `MAU: ${stats.users.mau.toLocaleString("tr-TR")}`, subRenk: "text-muted-foreground",
      renk: "text-sky-600 dark:text-sky-400", bg: "bg-sky-500/10",
    },
    {
      icon: DollarSign, label: "Aylık Gelir (MRR)", value: stats.revenue.monthly_try, suffix: " ₺",
      sub: "Son 30 gün başarılı ödeme", subRenk: "text-muted-foreground",
      renk: "text-amber-600 dark:text-amber-400", bg: "bg-amber-500/10",
    },
    {
      icon: AlertTriangle, label: "Açık Geri Bildirim", value: stats.feedback.open,
      sub: stats.feedback.critical > 0 ? `⚠ ${stats.feedback.critical} kritik` : "Kritik yok",
      subRenk: stats.feedback.critical > 0 ? "text-destructive" : "text-muted-foreground",
      renk: stats.feedback.critical > 0 ? "text-destructive" : "text-muted-foreground",
      bg: stats.feedback.critical > 0 ? "bg-destructive/10" : "bg-muted",
      kritik: stats.feedback.critical > 0,
    },
  ];

  return (
    <div className="space-y-6">
      {/* KPI kartları */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 stagger">
        {kpis.map((k) => (
          <Card key={k.label} className={`group hover-lift ${k.kritik ? "border-destructive/40" : ""}`}>
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-3">
                <span className={`rounded-xl p-2 transition-transform duration-300 group-hover:scale-110 ${k.bg} ${k.renk}`}>
                  <k.icon className="h-5 w-5" />
                </span>
                <span className="text-[11px] uppercase tracking-wider text-muted-foreground">{k.label}</span>
              </div>
              <div className="text-3xl font-bold tabular-nums leading-none">
                <CountUp value={k.value} />{k.suffix ?? ""}
              </div>
              <div className={`text-xs mt-1.5 ${k.subRenk}`}>{k.sub}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Plan dağılımı */}
      <Card className="hover-lift">
        <CardHeader>
          <CardTitle className="text-base">Plan Dağılımı</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {stats.tiers.map((t) => {
              const pct = tierTotal > 0 ? (t.count / tierTotal) * 100 : 0;
              return (
                <div key={t.plan}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium">{TIER_LABEL[t.plan] || t.plan}</span>
                    <span className="tabular-nums text-muted-foreground">{t.count} · %{pct.toFixed(0)}</span>
                  </div>
                  <div className="w-full h-2.5 bg-secondary rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${TIER_BAR[t.plan] || "bg-primary"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
            {stats.tiers.length === 0 && (
              <p className="text-sm text-muted-foreground">Henüz aktif hesap yok.</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* UYAP & Beta */}
      <div className="grid md:grid-cols-2 gap-4 stagger">
        <Card className="group hover-lift">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-3">
              <span className="rounded-xl bg-primary/10 p-2 text-primary transition-transform duration-300 group-hover:scale-110">
                <FileText className="h-5 w-5" />
              </span>
              <span className="text-sm font-medium">UYAP Kullanımı</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Toplam doküman</span><strong className="tabular-nums"><CountUp value={stats.uyap.documents} /></strong></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Yapay Zeka sorgu (30g)</span><strong className="tabular-nums"><CountUp value={stats.uyap.queries_30d} /></strong></div>
            </div>
          </CardContent>
        </Card>

        <Card className="group hover-lift">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-3">
              <span className="rounded-xl bg-accent/15 p-2 text-accent transition-transform duration-300 group-hover:scale-110">
                <Gift className="h-5 w-5" />
              </span>
              <span className="text-sm font-medium">Beta Program</span>
            </div>
            <div className="text-3xl font-bold tabular-nums"><CountUp value={stats.revenue.beta_count} /></div>
            <div className="text-xs text-muted-foreground mt-1">Aktif beta avukat</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
