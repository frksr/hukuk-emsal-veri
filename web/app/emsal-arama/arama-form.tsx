"use client";
import { useState } from "react";
import { Search, Loader2, ExternalLink } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { aramaCagir, type EmsalKarar } from "@/lib/api";

export function AramaForm() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<string>("");
  const [chamber, setChamber] = useState<string>("");
  const [k, setK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<EmsalKarar[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await aramaCagir({ query, k, source: source || null, court_chamber: chamber || null });
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
      setResults(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSearch} className="space-y-4">
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Örn: İcra takibinde emekli maaşının haczi"
            className="flex-1 h-12 text-base"
            aria-label="Arama sorgusu"
          />
          <Button type="submit" size="lg" disabled={loading || !query.trim()}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            <span className="ml-2">Ara</span>
          </Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <select value={source} onChange={(e) => setSource(e.target.value)} className="h-10 rounded-md border bg-background px-3">
            <option value="">Tüm Kaynaklar</option>
            <option value="yargitay">Yargıtay</option>
            <option value="danistay">Danıştay</option>
            <option value="hudoc">HUDOC (AİHM)</option>
          </select>
          <select value={chamber} onChange={(e) => setChamber(e.target.value)} className="h-10 rounded-md border bg-background px-3">
            <option value="">Tüm Daireler</option>
            <option>12. Hukuk Dairesi</option>
            <option>8. Hukuk Dairesi</option>
            <option>13. Hukuk Dairesi</option>
            <option>19. Hukuk Dairesi</option>
            <option>3. Daire</option>
            <option>9. Daire</option>
            <option>Vergi Dava Daireleri Kurulu</option>
            <option>İdare Dava Daireleri Kurulu</option>
          </select>
          <select value={k} onChange={(e) => setK(Number(e.target.value))} className="h-10 rounded-md border bg-background px-3">
            {[5, 10, 15, 20].map((n) => <option key={n} value={n}>{n} sonuç</option>)}
          </select>
        </div>
      </form>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          ⚠️ {error}
        </div>
      )}

      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 rounded-lg border bg-muted/30 animate-pulse" />
          ))}
        </div>
      )}

      {results && results.length === 0 && !loading && (
        <div className="text-center py-12 text-muted-foreground">
          Bu sorguya uyan emsal karar bulunamadı. Daha geniş bir arama deneyin.
        </div>
      )}

      {results && results.length > 0 && (
        <div className="space-y-3">
          <div className="text-sm text-muted-foreground">{results.length} emsal karar bulundu.</div>
          {results.map((r, i) => (
            <Card key={r.chunk_id}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h3 className="font-semibold text-base">
                      #{i + 1} — {r.court_chamber || "?"} · {r.case_no || "?"} → {r.decision_no || "?"}
                    </h3>
                    <div className="text-xs text-muted-foreground mt-1">
                      {r.decision_date || ""} · {r.source} · benzerlik: {(r.similarity * 100).toFixed(1)}%
                    </div>
                  </div>
                  {r.source_url && (
                    <a href={r.source_url} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline flex items-center gap-1">
                      Kaynak <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
                <p className="text-sm text-foreground/80 leading-relaxed line-clamp-4">{r.text}</p>
                {r.topic_tags && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {r.topic_tags.split(",").filter(Boolean).slice(0, 6).map((tag) => (
                      <span key={tag} className="text-xs rounded-full bg-secondary px-2 py-0.5 text-secondary-foreground">
                        {tag.trim()}
                      </span>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
