"use client";
import { useEffect, useState } from "react";
import { BarChart3, Receipt, History, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

type Usage = {
  tier: string;
  unlimited: boolean;
  breakdown: Array<{ event_type: string; daily_used: number; daily_limit: number; monthly_used: number; remaining: number; percent: number }>;
};
type Payment = {
  id: string; amount_try: number; currency: string; status: string;
  paid_at: string | null; invoice_number: string | null; invoice_pdf_url: string | null;
};
type Query = {
  id: string; query: string; chunk_count: number; duration_ms: number; created_at: string;
};

const EVENT_LABEL: Record<string, string> = {
  arama: "Emsal Arama", dilekce: "Dilekçe", ozet: "Karar Özet",
  ihtarname: "İhtarname", denetim: "Belge Denetim", karsi_argument: "Karşı Argüman",
  kvkk: "KVKK Checklist", sozlesme: "Sözleşme Analizi", sorgu: "UYAP AI Sorgu",
  faiz: "Faiz Hesaplama", zamanasimi: "Zamanaşımı", trend: "Trend",
};

export function RaporlarPanel() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [queries, setQueries] = useState<Query[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [uR, pR, qR] = await Promise.all([
          fetch("/api/proxy/me/usage"),
          fetch("/api/proxy/billing/invoices"),
          fetch("/api/proxy/uyap/sorgu/gecmis?limit=20").catch(() => null),
        ]);
        const uJ = await uR.json();
        if (uR.ok) setUsage(uJ.data);
        const pJ = await pR.json();
        if (pR.ok) setPayments(pJ.data?.payments || []);
        if (qR && qR.ok) {
          const qJ = await qR.json();
          setQueries(qJ.data?.queries || []);
        }
      } catch { /* sessiz */ }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2].map((i) => <div key={i} className="h-40 rounded-lg bg-muted animate-pulse" />)}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Kullanım */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" /> Günlük Kullanım — {usage?.tier || "?"}
          </CardTitle>
          {usage?.unlimited && <CardDescription>Bu pakette sınırsız kullanım.</CardDescription>}
        </CardHeader>
        <CardContent>
          {!usage?.unlimited && usage?.breakdown.length ? (
            <div className="space-y-3">
              {usage.breakdown.map((b) => (
                <div key={b.event_type}>
                  <div className="flex justify-between text-sm mb-1">
                    <span>{EVENT_LABEL[b.event_type] || b.event_type}</span>
                    <span className="text-muted-foreground">
                      {b.daily_used} / {b.daily_limit}
                    </span>
                  </div>
                  <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                    <div className={`h-full transition-all ${
                      b.percent >= 90 ? "bg-destructive"
                      : b.percent >= 70 ? "bg-amber-500"
                      : "bg-primary"
                    }`} style={{ width: `${b.percent}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : usage?.unlimited ? (
            <p className="text-sm text-emerald-600 font-medium">✓ Tüm özellikler sınırsız.</p>
          ) : (
            <p className="text-sm text-muted-foreground">Henüz kullanım yok.</p>
          )}
        </CardContent>
      </Card>

      {/* Sorgu Geçmişi */}
      {queries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <History className="h-5 w-5" /> Son AI Sorguları
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {queries.map((q) => (
              <div key={q.id} className="border-l-4 border-primary pl-3 py-1 text-sm">
                <div className="font-medium">{q.query}</div>
                <div className="text-xs text-muted-foreground mt-1 flex items-center gap-3">
                  <span>{new Date(q.created_at).toLocaleString("tr-TR")}</span>
                  <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{q.duration_ms}ms</span>
                  <span>{q.chunk_count} kaynak</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Fatura */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Receipt className="h-5 w-5" /> Fatura Geçmişi
          </CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {payments.length === 0 ? (
            <p className="text-sm text-muted-foreground">Henüz ödeme kaydı yok.</p>
          ) : (
            <table className="w-full min-w-[560px] text-sm">
              <thead className="text-left text-muted-foreground border-b">
                <tr><th className="pb-2">Tarih</th><th>Tutar</th><th>Durum</th><th>Fatura No</th><th></th></tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id} className="border-b last:border-0">
                    <td className="py-2">{p.paid_at ? new Date(p.paid_at).toLocaleDateString("tr-TR") : "—"}</td>
                    <td className="font-medium">
                      {new Intl.NumberFormat("tr-TR", { style: "currency", currency: p.currency }).format(p.amount_try)}
                    </td>
                    <td>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        p.status === "success" ? "bg-emerald-100 text-emerald-900"
                        : p.status === "refunded" ? "bg-blue-100 text-blue-900"
                        : "bg-red-100 text-red-900"
                      }`}>{p.status}</span>
                    </td>
                    <td>{p.invoice_number || "—"}</td>
                    <td>
                      {p.invoice_pdf_url && (
                        <a href={p.invoice_pdf_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline text-xs">
                          PDF
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
