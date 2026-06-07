"use client";
import { useState } from "react";
import { Loader2, Swords, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { karsiArgumentCagir } from "@/lib/api";

export function KarsiArgumentForm() {
  const [tezi, setTezi] = useState("");
  const [tur, setTur] = useState("");
  const [k, setK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [sonuc, setSonuc] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tezi.trim()) return;
    setLoading(true); setError(null);
    try {
      const data = await karsiArgumentCagir({ kendi_tezi: tezi, dava_turu: tur || null, k });
      setSonuc(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>Tezinizi Anlatın</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Textarea value={tezi} onChange={(e) => setTezi(e.target.value)} rows={6}
              placeholder="Davamda şunu iddia ediyorum: ..." />
            <div className="grid grid-cols-2 gap-3">
              <select value={tur} onChange={(e) => setTur(e.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                <option value="">Dava türü (opsiyonel)</option>
                <option value="icra">İcra</option>
                <option value="tahsilat">Tahsilat</option>
                <option value="haciz">Haciz</option>
                <option value="itirazin_iptali">İtirazın iptali</option>
                <option value="menfi_tespit">Menfi tespit</option>
              </select>
              <select value={k} onChange={(e) => setK(Number(e.target.value))} className="h-10 rounded-md border bg-background px-3 text-sm">
                {[3, 5, 7, 10].map((n) => <option key={n} value={n}>{n} emsal</option>)}
              </select>
            </div>
            <Button type="submit" disabled={loading || !tezi.trim()} className="w-full" size="lg">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Swords className="mr-2 h-4 w-4" />}
              Karşı Argümanları Üret
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>}

      {sonuc && (
        <>
          {sonuc.ozet_uyari && (
            <Card className="border-amber-300 bg-amber-50">
              <CardContent className="p-4 text-sm"><strong>⚠ En Zayıf Nokta:</strong> {sonuc.ozet_uyari}</CardContent>
            </Card>
          )}
          <div className="space-y-3">
            <h2 className="text-xl font-bold">Muhtemel Karşı Argümanlar ({sonuc.muhtemel_karsi_argumanlar?.length || 0})</h2>
            {sonuc.muhtemel_karsi_argumanlar?.map((a: any, i: number) => (
              <Card key={i} className="border-l-4 border-destructive">
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <CardTitle className="text-base">#{i + 1} {a.arguman}</CardTitle>
                    <div className="flex items-center gap-2">
                      <span className="text-xs">Güç</span>
                      <div className="w-20 h-2 bg-secondary rounded-full overflow-hidden">
                        <div className="h-full bg-destructive" style={{ width: `${(a.guc_skoru || 0) * 10}%` }} />
                      </div>
                      <span className="text-xs font-bold">{a.guc_skoru}/10</span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {a.dayanak_emsal?.length > 0 && (
                    <div className="text-xs text-muted-foreground">
                      Dayanak: {a.dayanak_emsal.join(", ")}
                    </div>
                  )}
                  <div className="flex gap-2 p-3 rounded bg-emerald-50 text-emerald-900 text-sm">
                    <Shield className="h-4 w-4 flex-shrink-0 mt-0.5" />
                    <div><strong>Sizin cevabınız:</strong> {a.rebuttal}</div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
