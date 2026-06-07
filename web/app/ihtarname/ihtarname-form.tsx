"use client";
import { useState } from "react";
import { Loader2, Mail, Copy, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ihtarnameOlustur } from "@/lib/api";

const TURLER = [
  { value: "alacak_temerrut", label: "Alacak Temerrüt (TBK 117 - 7 gün)" },
  { value: "kira_tahliye", label: "Kira Tahliye (TBK 315/352 - 30 gün)" },
  { value: "cek_ihtari", label: "Çek İhtarı (TTK 808 - 10 gün)" },
  { value: "fesih_ihtari", label: "Fesih İhtarı (TBK 125 - 15 gün)" },
  { value: "tahliye_30gun", label: "Tahliye 30 Gün" },
  { value: "genel", label: "Genel İhtar" },
];

export function IhtarnameForm() {
  const [tur, setTur] = useState("alacak_temerrut");
  const [alacakliAd, setAlacakliAd] = useState("");
  const [alacakliAdres, setAlacakliAdres] = useState("");
  const [borcluAd, setBorcluAd] = useState("");
  const [borcluAdres, setBorcluAdres] = useState("");
  const [anapara, setAnapara] = useState("");
  const [vade, setVade] = useState("");
  const [neden, setNeden] = useState("");
  const [loading, setLoading] = useState(false);
  const [sonuc, setSonuc] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setError(null);
    try {
      const data = await ihtarnameOlustur({
        tur,
        taraflar: { alacakli_ad: alacakliAd, alacakli_adres: alacakliAdres, borclu_ad: borcluAd, borclu_adres: borcluAdres },
        alacak_detay: { anapara: Number(anapara) || 0, vade_tarihi: vade, neden, faiz_orani: 0, dayanak_belge: "" },
        ek_talepler: [],
      });
      setSonuc(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  function copy() { if (sonuc?.ihtarname_metni) navigator.clipboard.writeText(sonuc.ihtarname_metni); }
  function download() {
    if (!sonuc?.ihtarname_metni) return;
    const blob = new Blob([sonuc.ihtarname_metni], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `ihtarname-${tur}-${Date.now()}.txt`; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="grid lg:grid-cols-5 gap-6">
      <Card className="lg:col-span-2 h-fit">
        <CardHeader><CardTitle>İhtarname Bilgileri</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-3 text-sm">
            <div>
              <label className="font-medium mb-1 block">Tür</label>
              <select value={tur} onChange={(e) => setTur(e.target.value)} className="w-full h-10 rounded-md border bg-background px-3">
                {TURLER.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="border-t pt-3 space-y-2">
              <div className="font-semibold text-foreground">Alacaklı</div>
              <Input placeholder="Ad / Unvan" value={alacakliAd} onChange={(e) => setAlacakliAd(e.target.value)} />
              <Input placeholder="Adres" value={alacakliAdres} onChange={(e) => setAlacakliAdres(e.target.value)} />
            </div>
            <div className="border-t pt-3 space-y-2">
              <div className="font-semibold text-foreground">Borçlu</div>
              <Input placeholder="Ad / Unvan" value={borcluAd} onChange={(e) => setBorcluAd(e.target.value)} />
              <Input placeholder="Adres" value={borcluAdres} onChange={(e) => setBorcluAdres(e.target.value)} />
            </div>
            <div className="border-t pt-3 space-y-2">
              <div className="font-semibold text-foreground">Alacak Detayı</div>
              <Input placeholder="Anapara (TRY)" type="number" value={anapara} onChange={(e) => setAnapara(e.target.value)} />
              <Input placeholder="Vade tarihi" type="date" value={vade} onChange={(e) => setVade(e.target.value)} />
              <Textarea placeholder="Neden / dayanak (örn: 15.01.2024 tarihli sözleşmeden doğan)" rows={3} value={neden} onChange={(e) => setNeden(e.target.value)} />
            </div>
            <Button type="submit" disabled={loading || !alacakliAd || !borcluAd} className="w-full" size="lg">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Mail className="mr-2 h-4 w-4" />}
              İhtarname Üret
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="lg:col-span-3 space-y-4">
        {error && <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>}
        {sonuc && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>İhtarname Taslağı</CardTitle>
              <div className="flex gap-2">
                <Button onClick={copy} variant="outline" size="sm"><Copy className="h-4 w-4" /></Button>
                <Button onClick={download} variant="outline" size="sm"><Download className="h-4 w-4" /></Button>
              </div>
            </CardHeader>
            <CardContent>
              <Textarea value={sonuc.ihtarname_metni} readOnly rows={25} className="font-mono text-sm" />
              {sonuc.yasa_referanslari?.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {sonuc.yasa_referanslari.map((r: string) => (
                    <span key={r} className="text-xs rounded-full bg-primary/10 text-primary px-3 py-1">{r}</span>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}
        {!sonuc && !loading && !error && (
          <Card><CardContent className="p-8 text-center text-muted-foreground">
            <Mail className="h-12 w-12 mx-auto mb-3 opacity-30" />
            Bilgileri doldurun, ihtarnameniz burada görünecek.
          </CardContent></Card>
        )}
      </div>
    </div>
  );
}
