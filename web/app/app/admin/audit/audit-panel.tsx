"use client";
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

type Log = {
  id: number;
  user_id: string | null;
  tenant_id: string | null;
  action: string;
  resource: string | null;
  ip_address: string | null;
  success: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
};

export function AuditPanel() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const qs = actionFilter ? `?action=${encodeURIComponent(actionFilter)}` : "";
      const r = await fetch(`/api/proxy/admin/audit-log${qs}`);
      const j = await r.json();
      if (r.ok) setLogs(j.data.logs || []);
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-4 flex gap-2">
          <Input
            placeholder="Action ile filtrele (örn: login, document.uploaded)"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
          />
          <Button onClick={load} disabled={loading}>Ara</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-left border-b bg-muted/30 text-xs">
              <tr>
                <th className="p-2">Tarih</th>
                <th className="p-2">Action</th>
                <th className="p-2">Resource</th>
                <th className="p-2">IP</th>
                <th className="p-2">User</th>
                <th className="p-2">OK</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-b last:border-0 hover:bg-muted/30 text-xs">
                  <td className="p-2 whitespace-nowrap">{new Date(l.created_at).toLocaleString("tr-TR")}</td>
                  <td className="p-2 font-mono">{l.action}</td>
                  <td className="p-2 font-mono text-muted-foreground">{l.resource || "—"}</td>
                  <td className="p-2 font-mono text-muted-foreground">{l.ip_address || "—"}</td>
                  <td className="p-2 font-mono text-muted-foreground">{l.user_id ? l.user_id.slice(0, 8) : "—"}</td>
                  <td className="p-2">{l.success ? "✓" : "✗"}</td>
                </tr>
              ))}
              {logs.length === 0 && !loading && (
                <tr><td colSpan={6} className="p-8 text-center text-muted-foreground">Kayıt yok</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
