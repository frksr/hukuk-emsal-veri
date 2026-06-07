"use client";
import { useState } from "react";
import { Loader2, Sparkles, Copy, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ozetCagir, type OzetSonuc } from "@/lib/api";

export function OzetForm() {
  const [metin, setMetin] = useState("");
  const [uzunluk, setUzunluk] = useState("orta");
  const [loading, setLoading] = useState(false);
  const [sonuc, setSonuc] = useState<OzetSonuc | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (metin.trim().length < 100) return;
    setLoading(true); setError(null);
    try {
      const data = await ozetCagir({ karar_metni: metin, uzunluk });
      setSonuc(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  function copy() { if (sonuc) navigator.clipboard.writeText(sonuc.ozet); }
  function download() {
    if (!sonuc) return;
    const md = `# Karar Özeti\n\n${sonuc.ozet}\n\n## Anahtar Noktalar\n${sonuc.anahtar_noktalar.map(n => `- ${n}`).join("\n")}\n\n## İlgili Kanunlar\n${sonuc.ilgili_kanunlar.join(", ")}`;
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "karar-ozeti.md"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>Karar Metni</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Textarea value={metin} onChange={(e) => setMetin(e.target.value)} rows={12}
              placeholder="Yargıtay/Danıştay karar metnini buraya yapıştırın..." />
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="text-xs text-muted-foreground">
                {metin.length.toLocaleString("tr-TR")} karakter · min 100
              </div>
              <div className="flex items-center gap-3">
                <select value={uzunluk} onChange={(e) => setUzunluk(e.target.value)}
                  className="h-10 rounded-md border bg-background px-3 text-sm">
                  <option value="kisa">Kısa (3 paragraf)</option>
                  <option value="orta">Orta (5 paragraf)</option>
                  <option value="detayli">Detaylı (7-10 paragraf)</option>
                </select>
                <Button type="submit" disabled={loading || metin.trim().length < 100}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  <span className="ml-2">Özet Üret</span>
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>}

      {sonuc && (
        <>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Özet</CardTitle>
              <div className="flex gap-2">
                <Button onClick={copy} variant="outline" size="sm"><Copy className="h-4 w-4" /></Button>
                <Button onClick={download} variant="outline" size="sm"><Download className="h-4 w-4" /></Button>
              </div>
            </CardHeader>
            <CardContent className="prose prose-sm max-w-none whitespace-pre-wrap">{sonuc.ozet}</CardContent>
          </Card>
          {sonuc.anahtar_noktalar?.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Anahtar Noktalar</CardTitle></CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {sonuc.anahtar_noktalar.map((n, i) => <li key={i} className="flex gap-2"><span className="text-primary">•</span>{n}</li>)}
                </ul>
              </CardContent>
            </Card>
          )}
          {sonuc.ilgili_kanunlar?.length > 0 && (
            <Card>
              <CardHeader><CardTitle>İlgili Kanunlar</CardTitle></CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {sonuc.ilgili_kanunlar.map((k) => (
                  <span key={k} className="text-xs rounded-full bg-primary/10 text-primary px-3 py-1">{k}</span>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
