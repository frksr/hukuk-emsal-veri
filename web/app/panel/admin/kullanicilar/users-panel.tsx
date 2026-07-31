"use client";
import { useEffect, useState } from "react";
import { Search, Crown, CheckCircle2, Gift, Loader2, ShieldAlert, ShieldX, ShieldCheck, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/toast";

type User = {
  id: string; email: string; name: string | null; role: string;
  email_verified: boolean; is_active: boolean; restricted: boolean;
  restricted_reason: string | null;
  created_at: string; last_login_at: string | null;
  tenant: { id: string; name: string; plan: string; beta: boolean } | null;
};

const PLANS = ["free", "pro_solo", "pro_solo_uyap", "team", "team_uyap", "enterprise"];

const STATUS_FILTERS: { key: string; label: string }[] = [
  { key: "all", label: "Tümü" },
  { key: "pending", label: "Onay bekleyen" },
  { key: "suspended", label: "Askıya alınmış" },
  { key: "restricted", label: "Kısıtlı" },
  { key: "active", label: "Aktif" },
];

export function UsersPanel() {
  const toast = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(false);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (status && status !== "all") params.set("status", status);
      const qs = params.toString() ? `?${params.toString()}` : "";
      const r = await fetch(`/api/proxy/admin/users${qs}`);
      const j = await r.json();
      if (r.ok) setUsers(j.data.users || []);
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [status]);

  async function accountAction(userId: string, action: "verify" | "suspend" | "reactivate" | "restrict" | "unrestrict", reason?: string) {
    setActing(`${userId}:${action}`);
    try {
      const r = await fetch(`/api/proxy/admin/users/${userId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: reason || null }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) {
        const detay = typeof j.detail === "string" ? j.detail : j.detail?.message;
        throw new Error(j.message || detay || `İşlem başarısız (HTTP ${r.status}).`);
      }
      toast(j.message || "İşlem tamamlandı.", "success");
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Sunucuya ulaşılamadı.", "error");
    } finally {
      setActing(null);
    }
  }

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
      const j = await r.json().catch(() => ({}));
      if (!r.ok) {
        const detay = typeof j.detail === "string" ? j.detail : j.detail?.message;
        throw new Error(j.message || detay || `Plan güncellenemedi (HTTP ${r.status}).`);
      }
      toast(`Plan güncellendi: ${plan}`, "success");
      setSuccess(`Plan güncellendi: ${plan}`);
      await load();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Sunucuya ulaşılamadı.", "error");
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
        <CardContent className="p-4 space-y-3">
          <div className="flex gap-2">
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
          </div>
          <div className="flex flex-wrap gap-1">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setStatus(f.key)}
                className={`text-xs px-3 py-1 rounded-full border transition ${
                  status === f.key
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-background text-muted-foreground border-border hover:bg-muted"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="text-left border-b bg-muted/30">
              <tr>
                <th className="p-3">Kullanıcı</th>
                <th className="p-3">Durum</th>
                <th className="p-3">Plan</th>
                <th className="p-3">Kayıt</th>
                <th className="p-3">Son Giriş</th>
                <th className="p-3">İşlem</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const busy = (action: string) => acting === `${u.id}:${action}`;
                return (
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
                    <div className="flex flex-col gap-1 items-start">
                      {!u.is_active && (
                        <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-destructive/10 text-destructive">
                          <ShieldX className="h-3 w-3" /> Askıya alınmış
                        </span>
                      )}
                      {u.is_active && !u.email_verified && (
                        <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
                          <Clock className="h-3 w-3" /> Onay bekliyor
                        </span>
                      )}
                      {u.is_active && u.restricted && (
                        <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-800"
                              title={u.restricted_reason || undefined}>
                          <ShieldAlert className="h-3 w-3" /> Kısıtlı
                        </span>
                      )}
                      {u.is_active && u.email_verified && !u.restricted && (
                        <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                          <ShieldCheck className="h-3 w-3" /> Aktif
                        </span>
                      )}
                    </div>
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
                    <div className="flex flex-wrap gap-1 items-center">
                      {u.role !== "admin" && !u.email_verified && (
                        <Button
                          size="sm" variant="outline"
                          disabled={busy("verify")}
                          onClick={() => accountAction(u.id, "verify")}
                          title="E-postayı manuel doğrula"
                        >
                          {busy("verify") ? <Loader2 className="h-3 w-3 animate-spin" /> : "Onayla"}
                        </Button>
                      )}
                      {u.role !== "admin" && u.is_active && (
                        <Button
                          size="sm" variant="outline"
                          disabled={busy("suspend")}
                          onClick={() => accountAction(u.id, "suspend")}
                          title="Hesabı askıya al (giriş engellenir)"
                        >
                          {busy("suspend") ? <Loader2 className="h-3 w-3 animate-spin" /> : "Askıya Al"}
                        </Button>
                      )}
                      {!u.is_active && (
                        <Button
                          size="sm" variant="outline"
                          disabled={busy("reactivate")}
                          onClick={() => accountAction(u.id, "reactivate")}
                        >
                          {busy("reactivate") ? <Loader2 className="h-3 w-3 animate-spin" /> : "Aktif Et"}
                        </Button>
                      )}
                      {u.role !== "admin" && !u.restricted && (
                        <Button
                          size="sm" variant="outline"
                          disabled={busy("restrict")}
                          onClick={() => accountAction(u.id, "restrict")}
                          title="Giriş yapabilir ama AI/arama kullanamaz"
                        >
                          {busy("restrict") ? <Loader2 className="h-3 w-3 animate-spin" /> : "Kısıtla"}
                        </Button>
                      )}
                      {u.restricted && (
                        <Button
                          size="sm" variant="outline"
                          disabled={busy("unrestrict")}
                          onClick={() => accountAction(u.id, "unrestrict")}
                        >
                          {busy("unrestrict") ? <Loader2 className="h-3 w-3 animate-spin" /> : "Kısıtlamayı Kaldır"}
                        </Button>
                      )}
                      {u.tenant && (
                        <div className="flex gap-1">
                          <select
                            key={`${u.tenant.id}-${u.tenant.plan}`}
                            disabled={upgrading === u.tenant.id}
                            onChange={(e) => {
                              if (!e.target.value) return;
                              upgrade(u.tenant!.id, e.target.value);
                            }}
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
                    </div>
                  </td>
                </tr>
                );
              })}
              {users.length === 0 && !loading && (
                <tr><td colSpan={6} className="p-8 text-center text-muted-foreground">Kullanıcı bulunamadı</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
