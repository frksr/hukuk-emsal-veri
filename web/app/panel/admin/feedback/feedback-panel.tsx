"use client";
import { useEffect, useState } from "react";
import { Bug, Lightbulb, Heart, Frown, HelpCircle, MessageSquare, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type Feedback = {
  id: string;
  user: { email: string; name: string | null } | null;
  type: string;
  severity: string;
  subject: string | null;
  message: string;
  page_url: string | null;
  status: string;
  admin_note: string | null;
  created_at: string;
  resolved_at: string | null;
};

const TYPE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  bug: Bug, feature: Lightbulb, praise: Heart,
  complaint: Frown, question: HelpCircle, other: MessageSquare,
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: "bg-red-100 text-red-900 border-red-300",
  high: "bg-orange-100 text-orange-900 border-orange-300",
  normal: "bg-blue-100 text-blue-900 border-blue-300",
  low: "bg-gray-100 text-gray-700 border-gray-300",
};

export function FeedbackPanel() {
  const [items, setItems] = useState<Feedback[]>([]);
  const [statusFilter, setStatusFilter] = useState("new");
  const [severityFilter, setSeverityFilter] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      if (statusFilter) qs.set("status", statusFilter);
      if (severityFilter) qs.set("severity", severityFilter);
      const r = await fetch(`/api/proxy/admin/feedback?${qs.toString()}`);
      const j = await r.json();
      if (r.ok) setItems(j.data.feedback || []);
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [statusFilter, severityFilter]);

  async function update(id: string, patch: { status?: string; admin_note?: string }) {
    const r = await fetch(`/api/proxy/admin/feedback/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (r.ok) await load();
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-4 flex flex-wrap gap-3">
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-9 rounded border bg-background px-3 text-sm">
            <option value="">Tüm durumlar</option>
            <option value="new">Yeni</option>
            <option value="reviewing">İnceleniyor</option>
            <option value="in_progress">Üstünde çalışılıyor</option>
            <option value="resolved">Çözüldü</option>
            <option value="wont_fix">Çözülmeyecek</option>
          </select>
          <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} className="h-9 rounded border bg-background px-3 text-sm">
            <option value="">Tüm öncelikler</option>
            <option value="critical">Kritik</option>
            <option value="high">Yüksek</option>
            <option value="normal">Normal</option>
            <option value="low">Düşük</option>
          </select>
          <div className="flex-1" />
          <div className="text-sm text-muted-foreground">{items.length} kayıt</div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-32 rounded-lg bg-muted animate-pulse" />)}</div>
      ) : items.length === 0 ? (
        <Card><CardContent className="p-8 text-center text-muted-foreground">Bu filtreyle geri bildirim yok.</CardContent></Card>
      ) : items.map((f) => {
        const Icon = TYPE_ICON[f.type] || MessageSquare;
        return (
          <Card key={f.id} className={f.severity === "critical" ? "border-destructive" : ""}>
            <CardContent className="p-4 space-y-3">
              <div className="flex items-start gap-3">
                <Icon className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className={`text-xs px-2 py-0.5 rounded border ${SEVERITY_COLOR[f.severity]}`}>
                      {f.severity}
                    </span>
                    <span className="text-xs bg-secondary px-2 py-0.5 rounded">{f.type}</span>
                    <span className="text-xs text-muted-foreground">
                      {f.user ? `${f.user.name || f.user.email}` : "(anonim)"}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(f.created_at).toLocaleString("tr-TR")}
                    </span>
                  </div>
                  {f.subject && <div className="font-semibold mb-1">{f.subject}</div>}
                  <p className="text-sm whitespace-pre-wrap">{f.message}</p>
                  {f.page_url && (
                    <a href={f.page_url} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline mt-2 inline-flex items-center gap-1">
                      <ExternalLink className="h-3 w-3" /> {f.page_url}
                    </a>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 items-center pt-2 border-t">
                <select
                  value={f.status}
                  onChange={(e) => update(f.id, { status: e.target.value })}
                  className="h-8 text-xs rounded border bg-background px-2"
                >
                  <option value="new">Yeni</option>
                  <option value="reviewing">İnceleniyor</option>
                  <option value="in_progress">Çalışılıyor</option>
                  <option value="resolved">Çözüldü</option>
                  <option value="wont_fix">Çözülmeyecek</option>
                </select>
                <input
                  type="text"
                  placeholder="Admin notu..."
                  defaultValue={f.admin_note || ""}
                  onBlur={(e) => e.target.value !== (f.admin_note || "") && update(f.id, { admin_note: e.target.value })}
                  className="flex-1 h-8 text-xs rounded border bg-background px-2 min-w-[200px]"
                />
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
