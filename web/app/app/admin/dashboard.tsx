"use client";
import { useEffect, useState } from "react";
import { Users, TrendingUp, AlertTriangle, Gift, FileText, Sparkles, DollarSign } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Stats = {
  users: { total: number; new_24h: number; new_7d: number; new_30d: number; dau: number; mau: number };
  tiers: Array<{ plan: string; count: number }>;
  revenue: { monthly_try: number; beta_count: number };
  feedback: { open: number; critical: number };
  uyap: { documents: number; queries_30d: number };
};

const TIER_LABEL: Record<string, string> = {
  free: "Free",
  pro_solo: "Pro Solo",
  pro_solo_uyap: "Pro + UYAP",
  team: "Team",
  team_uyap: "Team + UYAP",
  enterprise: "Enterprise",
};

const TIER_COLOR: Record<string, string> = {
  free: "bg-gray-200 text-gray-800",
  pro_solo: "bg-blue-100 text-blue-900",
  pro_solo_uyap: "bg-indigo-100 text-indigo-900",
  team: "bg-purple-100 text-purple-900",
  team_uyap: "bg-violet-100 text-violet-900",
  enterprise: "bg-amber-100 text-amber-900",
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

  if (loading) return <div className="grid md:grid-cols-4 gap-4">{[1,2,3,4,5,6,7,8].map(i => <div key={i} className="h-28 rounded-lg bg-muted animate-pulse" />)}</div>;
  if (error || !stats) return <Card><CardContent className="p-6 text-destructive">⚠ {error || "Veri alınamadı"}</CardContent></Card>;

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-2">
              <Users className="h-5 w-5 text-primary" />
              <span className="text-xs text-muted-foreground">Kullanıcı</span>
            </div>
            <div className="text-3xl font-bold">{stats.users.total.toLocaleString("tr-TR")}</div>
            <div className="text-xs text-emerald-600 mt-1">+{stats.users.new_24h} (24h) · +{stats.users.new_7d} (7g)</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              <span className="text-xs text-muted-foreground">Aktif</span>
            </div>
            <div className="text-3xl font-bold">{stats.users.dau.toLocaleString("tr-TR")}</div>
            <div className="text-xs text-muted-foreground mt-1">DAU · MAU: {stats.users.mau}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-2">
              <DollarSign className="h-5 w-5 text-emerald-600" />
              <span className="text-xs text-muted-foreground">Aylık MRR</span>
            </div>
            <div className="text-3xl font-bold">
              {new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 0 }).format(stats.revenue.monthly_try)}
            </div>
            <div className="text-xs text-muted-foreground mt-1">Son 30 gün gelir</div>
          </CardContent>
        </Card>

        <Card className={stats.feedback.critical > 0 ? "border-destructive" : ""}>
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-2">
              <AlertTriangle className={`h-5 w-5 ${stats.feedback.critical > 0 ? "text-destructive" : "text-muted-foreground"}`} />
              <span className="text-xs text-muted-foreground">Açık Feedback</span>
            </div>
            <div className="text-3xl font-bold">{stats.feedback.open}</div>
            {stats.feedback.critical > 0 && (
              <div className="text-xs text-destructive mt-1">⚠ {stats.feedback.critical} kritik</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tier Dağılımı */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Plan Dağılımı</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {stats.tiers.map((t) => {
              const total = stats.tiers.reduce((a, x) => a + x.count, 0);
              const pct = total > 0 ? (t.count / total) * 100 : 0;
              return (
                <div key={t.plan}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium">{TIER_LABEL[t.plan] || t.plan}</span>
                    <span>{t.count} ({pct.toFixed(0)}%)</span>
                  </div>
                  <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className={`h-full ${TIER_COLOR[t.plan]?.replace("text-", "bg-").replace("-900", "-500") || "bg-primary"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* UYAP & Beta */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-2">
              <FileText className="h-5 w-5 text-primary" />
              <span className="text-xs text-muted-foreground">UYAP</span>
            </div>
            <div className="space-y-2 mt-3 text-sm">
              <div className="flex justify-between"><span>Toplam doküman</span><strong>{stats.uyap.documents.toLocaleString("tr-TR")}</strong></div>
              <div className="flex justify-between"><span>AI sorgu (30g)</span><strong>{stats.uyap.queries_30d.toLocaleString("tr-TR")}</strong></div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-2">
              <Gift className="h-5 w-5 text-accent" />
              <span className="text-xs text-muted-foreground">Beta Program</span>
            </div>
            <div className="text-3xl font-bold mt-3">{stats.revenue.beta_count}</div>
            <div className="text-xs text-muted-foreground mt-1">Aktif beta avukat</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
