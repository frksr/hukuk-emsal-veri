"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Swords, Shield, Lock, Sparkles, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { karsiArgumentCagir } from "@/lib/api";
import { usePlan, modulKullanabilir } from "@/lib/use-plan";
import { AracYukleniyor } from "@/components/arac-yukleniyor";
import { ProUpsell } from "@/components/pro-upsell";

export function KarsiArgumentForm() {
  const router = useRouter();
  const plan = usePlan();
  const { loading: planLoading, isLoggedIn } = plan;
  const erisim = modulKullanabilir(plan, "karsi_argument");
  const [tezi, setTezi] = useState("");
  const [tur, setTur] = useState("");
  const [k, setK] = useState(5);
  const [loading, setLoading] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [sonuc, setSonuc] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const kilitli = !planLoading && !erisim;

  // Emsal aramadan "karşı argüman üret" ile gelindiyse tezi ön-doldur.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get("tez");
    if (t) setTezi(t);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tezi.trim()) return;
    if (!isLoggedIn) { router.push("/kayit"); return; }
    if (!erisim) {
      router.push("/app/ayarlar/ek-paketler?modul=karsi_argument");
      return;
    }
    setLoading(true); setError(null);
    try {
      const data = await karsiArgumentCagir({ kendi_tezi: tezi, dava_turu: tur || null, k });
      setSonuc(data);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 402 || status === 401) setError("Bu araçtaki bu ayki kullanım hakkın doldu. Pro'ya geçebilir veya ek paket alabilirsin.");
      else setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  if (planLoading) return <AracYukleniyor />;
  if (kilitli)
    return (
      <ProUpsell
        isLoggedIn={isLoggedIn}
        modul="karsi_argument"
        baslik="Karşı Argüman Üreteci"
        aciklama="Karşı tarafın size atacağı en güçlü argümanları önceden görün."
        ozellikler={[
          "Aleyhe emsallere dayalı muhtemel karşı argümanlar",
          "Her argüman için güç skoru + hazır rebuttal (cevap)",
          "En zayıf noktanızın özet uyarısı",
        ]}
      />
    );

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
              {loading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : kilitli ? (
                <Lock className="mr-2 h-4 w-4" />
              ) : (
                <Swords className="mr-2 h-4 w-4" />
              )}
              {kilitli ? "Pro ile Aç" : "Karşı Argümanları Üret"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Bilgilendirme / upsell — ücretsiz kullanıcıya, sonuç yokken */}
      {kilitli && !sonuc && (
        <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" /> Karşı Argüman Üreteci — Pro özelliği
            </CardTitle>
            <CardDescription>Karşı tarafın size atacağı en güçlü argümanları önceden görün.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <p className="leading-relaxed text-foreground/80">
              Tezinizi anlatın; Yapay Zeka, <strong>aleyhinize emsalleri</strong> tarar ve karşı tarafın
              kurabileceği en güçlü argümanları güç skoruyla sıralar — her biri için{" "}
              <strong>sizin hazır cevabınızı (rebuttal)</strong> da yazar. Duruşmaya çıkmadan zayıf
              noktalarınızı kapatın.
            </p>
            <ul className="space-y-1.5">
              {[
                "Aleyhe emsallere dayalı muhtemel karşı argümanlar",
                "Her argüman için güç skoru + hazır rebuttal",
                "En zayıf noktanızın özet uyarısı",
              ].map((m) => (
                <li key={m} className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary mt-0.5 shrink-0" /> {m}
                </li>
              ))}
            </ul>
            <Button onClick={() => router.push("/fiyatlandirma")}>
              <Sparkles className="h-4 w-4 mr-1.5" /> Pro&apos;ya geç
            </Button>
          </CardContent>
        </Card>
      )}

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
