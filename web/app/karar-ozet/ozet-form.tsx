"use client";
import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Loader2, Sparkles, Copy, Download, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type OzetSonuc } from "@/lib/api";
import { usePlan, modulKullanabilir } from "@/lib/use-plan";
import { AracYukleniyor } from "@/components/arac-yukleniyor";
import { ProUpsell } from "@/components/pro-upsell";

/** Özet çağrısı proxy üzerinden (auth JWT eklenir) → backend require_plan kontrol eder. */
async function callOzet(path: "text" | "by-id", body: Record<string, unknown>): Promise<OzetSonuc> {
  const r = await fetch(`/api/proxy/ozet/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.status === 401 || r.status === 402) {
    const e = Object.assign(new Error("Bu ayki özet hakkın doldu. Pro'ya geçebilir veya ek paket alabilirsin."), { status: r.status });
    throw e;
  }
  if (!r.ok) throw new Error("Özet üretilemedi. Lütfen tekrar deneyin.");
  const j = await r.json();
  return (j?.data ?? j) as OzetSonuc;
}

export function OzetForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const decisionId = searchParams.get("id");
  const plan = usePlan();
  const { loading: planLoading, isLoggedIn } = plan;
  const erisim = modulKullanabilir(plan, "ozet");

  const [metin, setMetin] = useState("");
  const [uzunluk, setUzunluk] = useState("orta");
  const [loading, setLoading] = useState(false);
  const [sonuc, setSonuc] = useState<OzetSonuc | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Detay sayfasından ?id= ile gelindiyse VE kullanıcı ücretliyse otomatik özetle.
  useEffect(() => {
    if (!decisionId || planLoading || !erisim) return;
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await callOzet("by-id", { decision_id: decisionId, uzunluk });
        if (alive) setSonuc(data);
      } catch (err) {
        if (alive) setError(err instanceof Error ? err.message : "Hata");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
    // uzunluk değişince otomatik tekrar üretmemek için bağımlılığa eklemedik
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decisionId, planLoading, erisim]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isLoggedIn) { router.push("/kayit"); return; }
    if (!erisim) {
      router.push("/app/ayarlar/ek-paketler?modul=ozet");
      return;
    }
    if (metin.trim().length < 100) return;
    setLoading(true);
    setError(null);
    try {
      const data = await callOzet("text", { karar_metni: metin, uzunluk });
      setSonuc(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally {
      setLoading(false);
    }
  }

  function copy() {
    if (sonuc) navigator.clipboard.writeText(sonuc.ozet);
  }
  function download() {
    if (!sonuc) return;
    const md = `# Karar Özeti\n\n${sonuc.ozet}\n\n## Anahtar Noktalar\n${sonuc.anahtar_noktalar.map((n) => `- ${n}`).join("\n")}\n\n## İlgili Kanunlar\n${sonuc.ilgili_kanunlar.join(", ")}`;
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "karar-ozeti.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  const kilitli = !planLoading && !erisim;

  if (planLoading) return <AracYukleniyor />;
  if (kilitli)
    return (
      <ProUpsell
        isLoggedIn={isLoggedIn}
        baslik="Yapay Zeka Karar Özeti"
        aciklama="Uzun Yargıtay/Danıştay kararlarını saniyeler içinde sade Türkçe özete dönüştürün."
        ozellikler={[
          "3–10 paragraf sade Türkçe özet (uzunluk seçimli)",
          "Anahtar noktalar + ilgili kanun maddeleri",
          "Kopyala / Markdown indir",
        ]}
      />
    );

  return (
    <div className="space-y-6">
      {/* Ücretsiz kullanıcı: yükseltme çağrısı */}
      {kilitli && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5">
            <div className="flex items-start gap-3">
              <Lock className="h-5 w-5 text-primary mt-0.5 shrink-0" />
              <div>
                <div className="font-semibold">Yapay Zeka Karar Özeti — Pro özelliği</div>
                <p className="text-sm text-muted-foreground">
                  Uzun kararları saniyeler içinde sade Türkçe özete dönüştürmek Pro
                  aboneliğe özeldir. Yükseltin, anında kullanmaya başlayın.
                </p>
              </div>
            </div>
            <Button onClick={() => router.push("/fiyatlandirma")} className="shrink-0">
              Pro&apos;ya geç
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Otomatik özet bildirimi (id ile gelindi, erişim var) */}
      {decisionId && erisim && loading && (
        <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Seçtiğiniz kararın Yapay Zeka özeti üretiliyor…
        </div>
      )}

      <Card className={kilitli ? "opacity-60 pointer-events-none select-none" : ""}>
        <CardHeader>
          <CardTitle>Karar Metni</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Textarea
              value={metin}
              onChange={(e) => setMetin(e.target.value)}
              rows={12}
              disabled={kilitli}
              placeholder="Yargıtay/Danıştay karar metnini buraya yapıştırın..."
            />
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="text-xs text-muted-foreground">
                {metin.length.toLocaleString("tr-TR")} karakter · min 100
              </div>
              <div className="flex items-center gap-3">
                <select
                  value={uzunluk}
                  onChange={(e) => setUzunluk(e.target.value)}
                  disabled={kilitli}
                  className="h-10 rounded-md border bg-background px-3 text-sm"
                >
                  <option value="kisa">Kısa (3 paragraf)</option>
                  <option value="orta">Orta (5 paragraf)</option>
                  <option value="detayli">Detaylı (7-10 paragraf)</option>
                </select>
                <Button type="submit" disabled={loading || (!kilitli && metin.trim().length < 100)}>
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : kilitli ? (
                    <Lock className="h-4 w-4" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  <span className="ml-2">{kilitli ? "Pro ile aç" : "Özet Üret"}</span>
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          ⚠️ {error}
        </div>
      )}

      {sonuc && (
        <>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Özet</CardTitle>
              <div className="flex gap-2">
                <Button onClick={copy} variant="outline" size="sm">
                  <Copy className="h-4 w-4" />
                </Button>
                <Button onClick={download} variant="outline" size="sm">
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="prose prose-sm max-w-none whitespace-pre-wrap">{sonuc.ozet}</CardContent>
          </Card>
          {sonuc.anahtar_noktalar?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Anahtar Noktalar</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {sonuc.anahtar_noktalar.map((n, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-primary">•</span>
                      {n}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          {sonuc.ilgili_kanunlar?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>İlgili Kanunlar</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {sonuc.ilgili_kanunlar.map((k) => (
                  <span key={k} className="text-xs rounded-full bg-primary/10 text-primary px-3 py-1">
                    {k}
                  </span>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
