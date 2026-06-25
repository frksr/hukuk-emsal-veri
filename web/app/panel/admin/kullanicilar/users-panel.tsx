"use client";
import { useEffect, useState } from "react";
import { Search, Crown, CheckCircle2, Gift, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

type User = {
  id: string; email: string; name: string | null; role: string;
  email_verified: boolean; created_at: string; last_login_at: string | null;
  tenant: { id: string; name: string; plan: string; beta: boolean } | null;
};

const PLANS = ["free", "pro_solo", "pro_solo_uyap", "team", "team_uyap", "enterprise"];

export function UsersPanel() {
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const qs = search ? `?search=${encodeURIComponent(search)}` : "";
      const r = await fetch(`/api/proxy/admin/users${qs}`);
      const j = await r.json();
      if (r.ok) setUsers(j.data.users || []);
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function upgrade(tenantId: string, plan: string, days?: number) {
    setUpgrading(tenantId);
    try {
      const r = await fetch(`/api/proxy/admin/tenants/${tenantId}/upgrade`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_tier: plan,
          duration_days: days,
          reason: days ? "Beta program" : "Admin manuel",
          beta_invited_by: days ? "admin" : null,
        }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message);
      setSuccess(`Plan güncellendi: ${plan}`);
      await load();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Hata");
    } finally { setUpgrading(null); }
  }

  return (
    <div className="space-y-4">
      {success && (
        <div className="rounded border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
          ✓ {success}
        </div>
      )}

      <Card>
        <CardContent className="p-4 flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Email veya ad ile ara..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load()}
              className="pl-9"
            />
          </div>
          <Button onClick={load} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Ara"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-left border-b bg-muted/30">
              <tr>
                <th className="p-3">Kullanıcı</th>
                <th className="p-3">Plan</th>
                <th className="p-3">Kayıt</th>
                <th className="p-3">Son Giriş</th>
                <th className="p-3">İşlem</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="p-3">
                    <div className="font-medium flex items-center gap-1">
                      {u.name || "—"}
                      {u.email_verified && <CheckCircle2 className="h-3 w-3 text-emerald-600" />}
                      {u.role === "admin" && <Crown className="h-3 w-3 text-amber-600" />}
                      {u.tenant?.beta && <Gift className="h-3 w-3 text-accent" />}
                    </div>
                    <div className="text-xs text-muted-foreground">{u.email}</div>
                  </td>
                  <td className="p-3">
                    {u.tenant ? (
                      <div>
                        <div className="font-medium text-xs">{u.tenant.plan}</div>
                        <div className="text-xs text-muted-foreground truncate max-w-[150px]">{u.tenant.name}</div>
                      </div>
                    ) : <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="p-3 text-xs text-muted-foreground">
                    {new Date(u.created_at).toLocaleDateString("tr-TR")}
                  </td>
                  <td className="p-3 text-xs text-muted-foreground">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString("tr-TR") : "Hiç"}
                  </td>
                  <td className="p-3">
                    {u.tenant && (
                      <div className="flex gap-1">
                        <select
                          disabled={upgrading === u.tenant.id}
                          onChange={(e) => upgrade(u.tenant!.id, e.target.value)}
                          defaultValue=""
                          className="h-8 text-xs rounded border bg-background px-2"
                        >
                          <option value="" disabled>Plan değiştir</option>
                          {PLANS.map((p) => (
                            <option key={p} value={p}>{p}</option>
                          ))}
                        </select>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => upgrade(u.tenant!.id, "pro_solo_uyap", 180)}
                          disabled={upgrading === u.tenant.id}
                          title="180 gün beta Pro+UYAP"
                        >
                          <Gift className="h-3 w-3" />
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {users.length === 0 && !loading && (
                <tr><td colSpan={5} className="p-8 text-center text-muted-foreground">Kullanıcı bulunamadı</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
