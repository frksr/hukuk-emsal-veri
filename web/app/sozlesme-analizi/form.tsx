"use client";
import { useState } from "react";
import { Loader2, FileCheck, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { sozlesmeAnalizText } from "@/lib/api";

const TURLER = [
  ["genel", "Genel"], ["hizmet", "Hizmet"], ["satis", "Satış"],
  ["kira", "Kira"], ["gizlilik", "Gizlilik (NDA)"], ["is", "İş Sözleşmesi"],
  ["distributorluk", "Distribütörlük"],
];

export function SozlesmeForm() {
  const [metin, setMetin] = useState("");
  const [tur, setTur] = useState("genel");
  const [loading, setLoading] = useState(false);
  const [sonuc, setSonuc] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileLoading(true);
    try {
      // PDF/DOCX için backend'e POST upload
      const formData = new FormData();
      formData.append("file", file);
      formData.append("sozlesme_turu", tur);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/sozlesme/upload`, { method: "POST", body: formData });
      const json = await res.json();
      if (json.ok) setSonuc(json.data);
      else setError(json.message || "Dosya yüklenemedi");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Yükleme hatası");
    } finally { setFileLoading(false); }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!metin.trim()) return;
    setLoading(true); setError(null);
    try {
      const data = await sozlesmeAnalizText({ metin, sozlesme_turu: tur });
      setSonuc(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  const riskRengi = (s: string) => s === "yuksek" ? "bg-red-100 text-red-900 border-red-300"
    : s === "orta" ? "bg-amber-100 text-amber-900 border-amber-300"
    : "bg-emerald-100 text-emerald-900 border-emerald-300";

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>Sözleşme Yükle veya Yapıştır</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex gap-3 items-center flex-wrap">
              <label className="text-sm font-medium">Sözleşme Türü</label>
              <select value={tur} onChange={(e) => setTur(e.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                {TURLER.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <div className="flex-1" />
              <label className="cursor-pointer">
                <input type="file" accept=".pdf,.docx,.txt" onChange={handleFileUpload} className="hidden" disabled={fileLoading} />
                <span className="inline-flex items-center gap-2 h-10 px-4 rounded-md border bg-background text-sm hover:bg-muted">
                  {fileLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  Dosya Yükle (PDF / DOCX / TXT)
                </span>
              </label>
            </div>
            <div className="relative">
              <div className="absolute inset-0 flex items-center"><div className="w-full border-t" /></div>
              <div className="relative flex justify-center text-xs"><span className="bg-background px-2 text-muted-foreground">veya yapıştır</span></div>
            </div>
            <Textarea value={metin} onChange={(e) => setMetin(e.target.value)} rows={10}
              placeholder="Sözleşme metnini buraya yapıştırın..." />
            <Button type="submit" disabled={loading || !metin.trim()} className="w-full" size="lg">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileCheck className="mr-2 h-4 w-4" />}
              Analiz Et
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>}

      {sonuc && (
        <>
          <div className="grid md:grid-cols-3 gap-3">
            <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Risk Skoru</div><div className="text-3xl font-bold">{sonuc.toplam_risk_skoru ?? "—"}/100</div></CardContent></Card>
            <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Madde Sayısı</div><div className="text-3xl font-bold">{sonuc.madde_analizleri?.length || 0}</div></CardContent></Card>
            <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">Eksik Madde</div><div className="text-3xl font-bold">{sonuc.eksik_maddeler?.length || 0}</div></CardContent></Card>
          </div>
          {sonuc.genel_ozet && (
            <Card>
              <CardHeader><CardTitle>Genel Özet</CardTitle></CardHeader>
              <CardContent className="text-sm whitespace-pre-wrap">{sonuc.genel_ozet}</CardContent>
            </Card>
          )}
          {sonuc.madde_analizleri?.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Madde Analizi</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {sonuc.madde_analizleri.map((m: any, i: number) => (
                  <div key={i} className={`border rounded-lg p-4 ${riskRengi(m.risk_seviye)}`}>
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="font-semibold">Madde {m.no}</div>
                      <span className="text-xs uppercase font-bold">{m.risk_seviye}</span>
                    </div>
                    <p className="text-sm mb-2">{m.ozet}</p>
                    {m.oneri && <p className="text-sm italic"><strong>Öneri:</strong> {m.oneri}</p>}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
          {sonuc.eksik_maddeler?.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Eksik Maddeler</CardTitle></CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {sonuc.eksik_maddeler.map((e: string, i: number) => <li key={i}>• {e}</li>)}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
