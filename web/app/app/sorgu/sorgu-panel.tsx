"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Send, Sparkles, FileText, Lock, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Doc = { id: string; title: string; doc_type: string; case_no: string | null };
type Answer = {
  answer: string;
  tenant_sources: Array<{ chunk_id: string; title?: string; document_id?: string; snippet: string; similarity: number }>;
  emsal_sources: Array<{ chunk_id: string; court_chamber?: string; case_no?: string; decision_no?: string; snippet: string; similarity: number }>;
  duration_ms: number;
};
type HistoryItem = {
  id: string; query: string; answer: string; chunk_count: number;
  duration_ms: number; created_at: string;
};

export function SorguPanel() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [includeEmsal, setIncludeEmsal] = useState(true);
  const [k, setK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [docsR, histR] = await Promise.all([
          fetch("/api/proxy/uyap/?limit=100"),
          fetch("/api/proxy/uyap/sorgu/gecmis?limit=10"),
        ]);
        if (docsR.status === 402) {
          const j = await docsR.json();
          setPlanError(j.message || "UYAP planı gerekli");
          return;
        }
        const docsJ = await docsR.json();
        if (docsR.ok) setDocs(docsJ.data?.documents || []);
        if (histR.ok) {
          const histJ = await histR.json();
          setHistory(histJ.data?.queries || []);
        }
      } catch { /* sessiz */ }
    })();
  }, []);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true); setError(null); setAnswer(null);
    try {
      const r = await fetch("/api/proxy/uyap/sorgu", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          document_ids: selectedDocs.size > 0 ? Array.from(selectedDocs) : null,
          k,
          include_emsal: includeEmsal,
        }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Sorgu başarısız");
      setAnswer(j.data);
      // History yenile
      const histR = await fetch("/api/proxy/uyap/sorgu/gecmis?limit=10");
      if (histR.ok) {
        const histJ = await histR.json();
        setHistory(histJ.data?.queries || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  function toggleDoc(id: string) {
    const s = new Set(selectedDocs);
    if (s.has(id)) s.delete(id); else s.add(id);
    setSelectedDocs(s);
  }

  if (planError) {
    return (
      <Card className="border-accent/40 bg-accent/5">
        <CardContent className="p-8 text-center">
          <Lock className="h-12 w-12 text-accent mx-auto mb-3" />
          <h2 className="text-xl font-semibold mb-2">UYAP Eklentisi Gerekli</h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto mb-4">{planError}</p>
          <Button asChild><Link href="/app/ayarlar/abonelik">Planı Yükselt</Link></Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid lg:grid-cols-4 gap-6">
      <div className="lg:col-span-3 space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-accent" /> Soru Sor
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={ask} className="space-y-4">
              <Textarea
                rows={4}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Örn: Geçen yılki tahsilat dosyalarımda ortak gerekçe nedir? veya: Müvekkilime gelen ihtarnameyi inceleyip emsallere göre cevap stratejisi öner."
              />
              <div className="flex flex-wrap gap-4 items-center text-sm">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={includeEmsal} onChange={(e) => setIncludeEmsal(e.target.checked)} />
                  Public emsal kararları da dahil et
                </label>
                <select
                  value={k}
                  onChange={(e) => setK(Number(e.target.value))}
                  className="h-9 rounded-md border bg-background px-3 text-sm"
                >
                  {[3, 5, 7, 10].map((n) => <option key={n} value={n}>{n} kaynak</option>)}
                </select>
                <div className="flex-1" />
                <Button type="submit" disabled={loading || !query.trim()}>
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                  Sor
                </Button>
              </div>
              {selectedDocs.size > 0 && (
                <div className="text-xs text-muted-foreground">
                  <strong>{selectedDocs.size}</strong> dosya ile sınırlandırılmış sorgu.{" "}
                  <button type="button" onClick={() => setSelectedDocs(new Set())} className="text-primary hover:underline">
                    Temizle
                  </button>
                </div>
              )}
            </form>
          </CardContent>
        </Card>

        {error && (
          <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            ⚠ {error}
          </div>
        )}

        {answer && (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Yanıt</CardTitle>
              </CardHeader>
              <CardContent className="prose prose-sm max-w-none whitespace-pre-wrap">
                {answer.answer}
                <div className="text-xs text-muted-foreground mt-3 not-prose flex items-center gap-1">
                  <Clock className="h-3 w-3" /> {answer.duration_ms}ms · {answer.tenant_sources.length + answer.emsal_sources.length} kaynak
                </div>
              </CardContent>
            </Card>

            {answer.tenant_sources.length > 0 && (
              <Card>
                <CardHeader><CardTitle className="text-base">Kendi Dosyalarımdan</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {answer.tenant_sources.map((s, i) => (
                    <Link
                      key={s.chunk_id}
                      href={s.document_id ? `/app/dosya/${s.document_id}` : "#"}
                      className="block border-l-4 border-primary pl-3 py-1 text-sm hover:bg-muted/50 rounded-r"
                    >
                      <div className="font-semibold text-xs text-muted-foreground">
                        #{i + 1} · {s.title || "Doküman"} · {(s.similarity * 100).toFixed(0)}%
                      </div>
                      <p className="mt-1">{s.snippet}...</p>
                    </Link>
                  ))}
                </CardContent>
              </Card>
            )}

            {answer.emsal_sources.length > 0 && (
              <Card>
                <CardHeader><CardTitle className="text-base">Emsal Kararlardan</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {answer.emsal_sources.map((s, i) => (
                    <div key={s.chunk_id} className="border-l-4 border-accent pl-3 py-1 text-sm">
                      <div className="font-semibold text-xs">
                        #{i + 1} · {s.court_chamber} · E.{s.case_no}/K.{s.decision_no}
                      </div>
                      <p className="mt-1 text-muted-foreground">{s.snippet}...</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </>
        )}

        {history.length > 0 && !answer && (
          <Card>
            <CardHeader><CardTitle className="text-base">Son Sorgular</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {history.map((h) => (
                <button
                  key={h.id}
                  onClick={() => setQuery(h.query)}
                  className="w-full text-left p-3 rounded hover:bg-muted/50 border text-sm"
                >
                  <div className="font-medium truncate">{h.query}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {new Date(h.created_at).toLocaleString("tr-TR")} · {h.chunk_count} kaynak
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4" /> Dosyalarım ({docs.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 max-h-[600px] overflow-y-auto">
            <div className="text-xs text-muted-foreground mb-2">
              Sınırlandırmak için seçin (boş bırakırsan tüm dosyalarda arar):
            </div>
            {docs.map((d) => (
              <label key={d.id} className="flex items-start gap-2 p-2 rounded hover:bg-muted/50 cursor-pointer text-sm">
                <input
                  type="checkbox"
                  checked={selectedDocs.has(d.id)}
                  onChange={() => toggleDoc(d.id)}
                  className="mt-0.5"
                />
                <div className="flex-1 min-w-0">
                  <div className="truncate font-medium">{d.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {d.doc_type} {d.case_no && `· ${d.case_no}`}
                  </div>
                </div>
              </label>
            ))}
            {docs.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">
                Henüz dosya yok. <Link href="/app/dosyalar" className="text-primary hover:underline">Yükleyin</Link>
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
