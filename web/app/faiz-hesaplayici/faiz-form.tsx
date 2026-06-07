"use client";
import { useState } from "react";
import { Loader2, Calculator } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { faizHesapla, type FaizSonuc } from "@/lib/api";
import { formatTRY } from "@/lib/utils";

export function FaizForm() {
  const [anapara, setAnapara] = useState("100000");
  const [temerrut, setTemerrut] = useState("2024-01-01");
  const [vade, setVade] = useState(new Date().toISOString().slice(0, 10));
  const [tur, setTur] = useState("yasal");
  const [loading, setLoading] = useState(false);
  const [sonuc, setSonuc] = useState<FaizSonuc | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await faizHesapla({
        anapara: Number(anapara),
        temerrut_tarihi: temerrut,
        vade_tarihi: vade,
        faiz_turu: tur,
      });
      setSonuc(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid lg:grid-cols-5 gap-6">
      <Card className="lg:col-span-2 h-fit">
        <CardHeader><CardTitle>Hesaplama Bilgileri</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Anapara (TRY)</label>
              <Input type="number" value={anapara} onChange={(e) => setAnapara(e.target.value)} step="0.01" min="0" />
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Temerrüt Tarihi</label>
              <Input type="date" value={temerrut} onChange={(e) => setTemerrut(e.target.value)} />
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Vade / Hesap Tarihi</label>
              <Input type="date" value={vade} onChange={(e) => setVade(e.target.value)} />
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Faiz Türü</label>
              <select value={tur} onChange={(e) => setTur(e.target.value)} className="w-full h-10 rounded-md border bg-background px-3 text-sm">
                <option value="yasal">Yasal Faiz (TBK 88)</option>
                <option value="ticari_avans">Ticari Avans (TCMB)</option>
                <option value="tcmb_reeskont">TCMB Reeskont</option>
              </select>
            </div>
            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Calculator className="mr-2 h-4 w-4" />}
              Hesapla
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="lg:col-span-3 space-y-4">
        {error && <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>}
        {sonuc && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                ["Anapara", sonuc.anapara],
                ["Faiz", sonuc.faiz_tutari],
                ["Harçlar", `${Number(sonuc.cezaevi_harci) + Number(sonuc.tahsil_harci)}`],
                ["Vekalet", sonuc.vekalet_ucreti],
              ].map(([l, v]) => (
                <Card key={l}>
                  <CardContent className="p-4">
                    <div className="text-xs text-muted-foreground">{l}</div>
                    <div className="text-lg font-bold">{formatTRY(v)}</div>
                  </CardContent>
                </Card>
              ))}
            </div>
            <Card className="bg-primary text-primary-foreground">
              <CardContent className="p-6">
                <div className="text-sm opacity-80">Toplam Alacak</div>
                <div className="text-3xl font-bold">{formatTRY(sonuc.toplam_alacak)}</div>
                <div className="text-xs opacity-70 mt-1">{sonuc.gun_sayisi} gün · {sonuc.faiz_baslangic} → {sonuc.faiz_bitis}</div>
              </CardContent>
            </Card>
            {sonuc.yillik_breakdown?.length > 0 && (
              <Card>
                <CardHeader><CardTitle className="text-base">Yıllık Faiz Dağılımı</CardTitle></CardHeader>
                <CardContent>
                  <table className="w-full text-sm">
                    <thead className="text-left text-muted-foreground border-b">
                      <tr><th className="pb-2">Yıl</th><th>Gün</th><th>Oran %</th><th className="text-right">Faiz</th></tr>
                    </thead>
                    <tbody>
                      {sonuc.yillik_breakdown.map((y) => (
                        <tr key={y.yil} className="border-b last:border-0">
                          <td className="py-2">{y.yil}</td>
                          <td>{y.gun}</td>
                          <td>{y.oran}</td>
                          <td className="text-right font-medium">{formatTRY(y.faiz)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            )}
            <div className="text-xs text-muted-foreground p-3 rounded border border-amber-200 bg-amber-50">
              ⚠️ {sonuc.uyari}
            </div>
          </>
        )}
        {!sonuc && !loading && !error && (
          <Card><CardContent className="p-8 text-center text-muted-foreground">
            <Calculator className="h-12 w-12 mx-auto mb-3 opacity-30" />
            Hesaplama bilgilerini girin, sonuç burada görünecek.
          </CardContent></Card>
        )}
      </div>
    </div>
  );
}
