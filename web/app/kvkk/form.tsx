"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Shield, Sparkles, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { kvkkChecklist } from "@/lib/api";
import { usePlan } from "@/lib/use-plan";
import { useKayitDavet } from "@/components/kayit-davet";

const SEKTORLER = [
  ["saglik", "Sağlık"], ["fintech", "Fintech / Banka"], ["egitim", "Eğitim"],
  ["e_ticaret", "E-Ticaret"], ["imalat", "İmalat"], ["kamu", "Kamu"],
  ["telekom", "Telekom"], ["insan_kaynaklari", "İK / İstihdam"],
  ["hukuk_burosu", "Hukuk Bürosu"], ["diger", "Diğer"],
];

const VERI_TURLERI = [
  ["kisisel", "Kişisel"], ["ozel_nitelikli", "Özel Nitelikli"],
  ["finansal", "Finansal"], ["saglik", "Sağlık"], ["cocuk", "Çocuk"],
  ["calisan", "Çalışan"], ["musteri", "Müşteri"], ["konum", "Konum"],
  ["biyometrik", "Biyometrik"], ["iletisim_kaydi", "İletişim Kaydı"],
  ["kamera", "Kamera"], ["cerez", "Çerez"],
];

export function KVKKForm() {
  const router = useRouter();
  const { loading: planLoading, isPaid, isLoggedIn } = usePlan();
  const { davetGoster, dialog: kayitDialog } = useKayitDavet();
  const [sektor, setSektor] = useState("e_ticaret");
  const [veriTurleri, setVeriTurleri] = useState<string[]>(["kisisel", "musteri"]);
  const [llmEk, setLlmEk] = useState(true);

  // Ücretsiz kullanıcıda Yapay Zeka ek maddeler kapalı kalsın (temel checklist serbest).
  useEffect(() => {
    if (!planLoading && !isPaid) setLlmEk(false);
  }, [planLoading, isPaid]);
  const [loading, setLoading] = useState(false);
  const [sonuc, setSonuc] = useState<any>(null);
  const [tamamlananlar, setTamamlananlar] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isLoggedIn) { davetGoster(); return; }
    setLoading(true); setError(null);
    try {
      // Yapay Zeka ek maddeler yalnızca ücretli planda; aksi halde temel checklist (llm_ek=false).
      const data = await kvkkChecklist({ sektor, veri_turleri: veriTurleri, llm_ek: isPaid && llmEk });
      setSonuc(data);
      setTamamlananlar(new Set());
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 402 || status === 401) setError("Yapay Zeka ile sektöre özel ek maddeler Pro aboneliğe özeldir.");
      else setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  const toggle = (n: number) => {
    const s = new Set(tamamlananlar);
    s.has(n) ? s.delete(n) : s.add(n);
    setTamamlananlar(s);
  };

  const skor = sonuc?.maddeler && sonuc.maddeler.length > 0
    ? Math.round((tamamlananlar.size / sonuc.maddeler.length) * 100)
    : 0;

  const skorRengi = skor >= 70 ? "text-emerald-600" : skor >= 40 ? "text-amber-600" : "text-destructive";

  // Gruplar
  const gruplar: Record<string, any[]> = {};
  if (sonuc?.maddeler) {
    for (const m of sonuc.maddeler) {
      const k = m.kategori || "diger";
      if (!gruplar[k]) gruplar[k] = [];
      gruplar[k].push(m);
    }
  }

  return (
    <div className="grid lg:grid-cols-5 gap-6">
      {kayitDialog}
      <Card className="lg:col-span-2 h-fit">
        <CardHeader><CardTitle>Şirket Bilgileri</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Sektör</label>
              <select value={sektor} onChange={(e) => setSektor(e.target.value)} className="w-full h-10 rounded-md border bg-background px-3 text-sm">
                {SEKTORLER.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">İşlenen Veri Türleri</label>
              <div className="grid grid-cols-2 gap-2">
                {VERI_TURLERI.map(([v, l]) => (
                  <label key={v} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={veriTurleri.includes(v)}
                      onChange={(e) => setVeriTurleri(e.target.checked
                        ? [...veriTurleri, v]
                        : veriTurleri.filter((t) => t !== v))} />
                    {l}
                  </label>
                ))}
              </div>
            </div>
            {isPaid ? (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={llmEk} onChange={(e) => setLlmEk(e.target.checked)} />
                <Sparkles className="h-3.5 w-3.5 text-primary" /> Yapay Zeka ile sektöre özel ek maddeler üret
              </label>
            ) : (
              <div className="flex items-center justify-between gap-2 text-sm rounded-md border border-primary/30 bg-primary/5 px-3 py-2">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Lock className="h-3.5 w-3.5" /> Yapay Zeka ile sektöre özel ek maddeler
                  <span className="text-[10px] rounded-full bg-primary/10 text-primary px-1.5 py-0.5">Pro</span>
                </span>
                <button
                  type="button"
                  onClick={() => router.push("/fiyatlandirma")}
                  className="text-primary underline text-xs shrink-0"
                >
                  Pro&apos;ya geç
                </button>
              </div>
            )}
            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Shield className="mr-2 h-4 w-4" />}
              Checklist Üret
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="lg:col-span-3 space-y-4">
        {error && <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>}
        {sonuc && (
          <>
            <Card>
              <CardContent className="p-6 text-center">
                <div className="text-sm text-muted-foreground">Uyum Skoru</div>
                <div className={`text-6xl font-bold my-2 ${skorRengi}`}>{skor}%</div>
                <div className="text-sm text-muted-foreground">
                  {tamamlananlar.size} / {sonuc.maddeler?.length || 0} madde tamamlandı
                </div>
                <div className="w-full h-3 bg-secondary rounded-full overflow-hidden mt-4">
                  <div className={`h-full transition-all ${skor >= 70 ? "bg-emerald-500" : skor >= 40 ? "bg-amber-500" : "bg-destructive"}`}
                    style={{ width: `${skor}%` }} />
                </div>
              </CardContent>
            </Card>
            {Object.entries(gruplar).map(([kat, maddeler]) => (
              <Card key={kat}>
                <CardHeader><CardTitle className="text-base capitalize">{kat.replace(/_/g, " ")} ({maddeler.length})</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {maddeler.map((m: any) => (
                    <label key={m.no} className="flex items-start gap-3 p-2 rounded hover:bg-muted/50 cursor-pointer">
                      <input type="checkbox" checked={tamamlananlar.has(m.no)} onChange={() => toggle(m.no)} className="mt-1" />
                      <div className="flex-1">
                        <div className="text-sm">{m.madde}</div>
                        {m.oncelik && (
                          <span className={`text-xs ${m.oncelik === "yuksek" ? "text-destructive" : m.oncelik === "orta" ? "text-amber-600" : "text-muted-foreground"}`}>
                            {m.oncelik === "yuksek" ? "🔴 Yüksek öncelik" : m.oncelik === "orta" ? "🟡 Orta" : "🟢 Düşük"}
                          </span>
                        )}
                        {m.sektorel_not && <div className="text-xs text-muted-foreground mt-1 italic">{m.sektorel_not}</div>}
                      </div>
                    </label>
                  ))}
                </CardContent>
              </Card>
            ))}
          </>
        )}
        {!sonuc && !loading && !error && (
          <Card><CardContent className="p-8 text-center text-muted-foreground">
            <Shield className="h-12 w-12 mx-auto mb-3 opacity-30" />
            Sektör seçin, checklist burada görünecek.
          </CardContent></Card>
        )}
      </div>
    </div>
  );
}
