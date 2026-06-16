"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft, FileText, Sparkles, Loader2, Send, AlertTriangle,
  Shield, Calendar, Building2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Doc = {
  id: string;
  title: string;
  case_no: string | null;
  decision_no: string | null;
  court: string | null;
  doc_type: string;
  file_name: string;
  file_size: number;
  status: string;
  chunk_count: number;
  tags: string[] | null;
  topic_tags: string[] | null;
  pii_audit: { contains_pii: boolean; types: string[]; counts?: Record<string, number> } | null;
  summary: string | null;
  cleaned_text: string;
  document_date: string | null;
  created_at: string;
};

type Answer = {
  answer: string;
  tenant_sources: Array<{ chunk_id: string; title?: string; snippet: string; similarity: number }>;
  emsal_sources: Array<{ chunk_id: string; court_chamber?: string; case_no?: string; decision_no?: string; snippet: string; similarity: number }>;
  duration_ms: number;
};

export function DocPanel({ docId }: { docId: string }) {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`/api/proxy/uyap/${docId}`);
        const j = await r.json();
        if (!r.ok) throw new Error(j.message || "Yüklenemedi");
        setDoc(j.data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Hata");
      } finally { setLoading(false); }
    })();
  }, [docId]);

  async function askAI(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setAsking(true); setAnswer(null);
    try {
      const r = await fetch("/api/proxy/uyap/sorgu", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          document_ids: [docId],
          k: 5,
          include_emsal: true,
        }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Sorgu başarısız");
      setAnswer(j.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setAsking(false); }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-1/2 rounded bg-muted animate-pulse" />
        <div className="h-32 rounded-lg bg-muted animate-pulse" />
      </div>
    );
  }

  if (error || !doc) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <AlertTriangle className="h-12 w-12 text-destructive mx-auto mb-3" />
          <p className="text-destructive">{error || "Doküman bulunamadı"}</p>
          <Button asChild variant="outline" className="mt-4">
            <Link href="/app/dosyalar"><ArrowLeft className="h-4 w-4 mr-2" /> Dosyalara Dön</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link href="/app/dosyalar" className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1 mb-3">
          <ArrowLeft className="h-3 w-3" /> Dosyalara dön
        </Link>
        <div className="flex items-start gap-3">
          <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
            <FileText className="h-6 w-6 text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold truncate">{doc.title}</h1>
            <div className="flex flex-wrap gap-3 mt-1 text-sm text-muted-foreground">
              {doc.case_no && <span>Esas: <strong className="text-foreground">{doc.case_no}</strong></span>}
              {doc.decision_no && <span>Karar: <strong className="text-foreground">{doc.decision_no}</strong></span>}
              {doc.court && <span className="flex items-center gap-1"><Building2 className="h-3 w-3" /> {doc.court}</span>}
              {doc.document_date && <span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> {doc.document_date}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* KVKK uyarı */}
      {doc.pii_audit?.contains_pii && (
        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm flex gap-2">
          <Shield className="h-4 w-4 flex-shrink-0 mt-0.5 text-amber-700" />
          <div className="text-amber-900">
            Bu dokümanda kişisel veri tespit edildi: <strong>{doc.pii_audit.types.join(", ")}</strong>.
            Yapay Zeka sorgularında bu veriler otomatik maskelenir (Anthropic/Google görmeyecek).
          </div>
        </div>
      )}

      {/* Yapay Zeka Sorgu */}
      <Card className="border-accent/40 bg-accent/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-accent" /> Bu dosya hakkında Yapay Zeka'ya sor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={askAI} className="space-y-3">
            <Textarea
              rows={3}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Örn: Bu dosyada ödeme emri ne durumda? Hangi emsal kararlar var?"
            />
            <Button type="submit" disabled={asking || !query.trim()}>
              {asking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
              Sor
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Yapay Zeka Yanıt */}
      {answer && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Yapay Zeka Yanıtı</CardTitle>
            </CardHeader>
            <CardContent className="prose prose-sm max-w-none whitespace-pre-wrap">
              {answer.answer}
              <div className="text-xs text-muted-foreground mt-3 not-prose">
                Yanıt {answer.duration_ms}ms'de üretildi · {answer.tenant_sources.length} kendi dosyam + {answer.emsal_sources.length} emsal
              </div>
            </CardContent>
          </Card>
          {answer.tenant_sources.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base">Kullanılan Dosya Bölümleri</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {answer.tenant_sources.map((s, i) => (
                  <div key={s.chunk_id} className="text-sm border-l-4 border-primary pl-3 py-1">
                    <div className="font-semibold text-xs text-muted-foreground">
                      #{i + 1} · benzerlik {(s.similarity * 100).toFixed(0)}%
                    </div>
                    <p className="mt-1">{s.snippet}...</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
          {answer.emsal_sources.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base">İlgili Emsal Kararlar</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {answer.emsal_sources.map((s, i) => (
                  <div key={s.chunk_id} className="text-sm border-l-4 border-accent pl-3 py-1">
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

      {/* Doküman içeriği önizleme */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Doküman Metni ({doc.cleaned_text?.length || 0} karakter)</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            value={doc.cleaned_text || ""}
            readOnly
            rows={20}
            className="font-mono text-xs"
          />
        </CardContent>
      </Card>
    </div>
  );
}
