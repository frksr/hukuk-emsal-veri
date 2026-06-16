"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Mail, Copy, Download, Lock, Sparkles, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ihtarnameOlustur, exportBelge } from "@/lib/api";
import { usePlan, modulKullanabilir } from "@/lib/use-plan";
import { AracYukleniyor } from "@/components/arac-yukleniyor";
import { ProUpsell } from "@/components/pro-upsell";

const TURLER = [
  { value: "alacak_temerrut", label: "Alacak Temerrüt (TBK 117 - 7 gün)" },
  { value: "kira_tahliye", label: "Kira Tahliye (TBK 315/352 - 30 gün)" },
  { value: "cek_ihtari", label: "Çek İhtarı (TTK 808 - 10 gün)" },
  { value: "fesih_ihtari", label: "Fesih İhtarı (TBK 125 - 15 gün)" },
  { value: "tahliye_30gun", label: "Tahliye 30 Gün" },
  { value: "genel", label: "Genel İhtar" },
];

export function IhtarnameForm() {
  const router = useRouter();
  const plan = usePlan();
  const { loading: planLoading, isLoggedIn } = plan;
  const erisim = modulKullanabilir(plan, "ihtarname");

  const [tur, setTur] = useState("alacak_temerrut");
  const [alacakliAd, setAlacakliAd] = useState("");
  const [alacakliAdres, setAlacakliAdres] = useState("");
  const [borcluAd, setBorcluAd] = useState("");
  const [borcluAdres, setBorcluAdres] = useState("");
  const [anapara, setAnapara] = useState("");
  const [vade, setVade] = useState("");
  const [neden, setNeden] = useState("");
  const [loading, setLoading] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [sonuc, setSonuc] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const kilitli = !planLoading && !erisim;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isLoggedIn) { router.push("/kayit"); return; }
    if (!erisim) {
      router.push("/app/ayarlar/ek-paketler?modul=ihtarname");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await ihtarnameOlustur({
        tur,
        taraflar: { alacakli_ad: alacakliAd, alacakli_adres: alacakliAdres, borclu_ad: borcluAd, borclu_adres: borcluAdres },
        alacak_detay: { anapara: Number(anapara) || 0, vade_tarihi: vade, neden, faiz_orani: 0, dayanak_belge: "" },
        ek_talepler: [],
      });
      setSonuc(data);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 402 || status === 401) setError("Bu araçtaki bu ayki kullanım hakkın doldu. Pro'ya geçebilir veya ek paket alabilirsin.");
      else setError(err instanceof Error ? err.message : "Hata");
    } finally {
      setLoading(false);
    }
  }

  function copy() {
    if (sonuc?.ihtarname_metni) navigator.clipboard.writeText(sonuc.ihtarname_metni);
  }
  async function downloadAs(format: "docx" | "udf") {
    if (!sonuc?.ihtarname_metni) return;
    try {
      await exportBelge(format, { metin: sonuc.ihtarname_metni, dosya_adi: `ihtarname-${tur}` });
    } catch (err) {
      setError(err instanceof Error ? err.message : "İndirme hatası.");
    }
  }

  if (planLoading) return <AracYukleniyor />;
  if (kilitli)
    return (
      <ProUpsell
        isLoggedIn={isLoggedIn}
        modul="ihtarname"
        baslik="Yapay Zeka İhtarname"
        aciklama="Doğru yasal süre ve resmî dille, notere sunulabilir ihtarname taslağı."
        ozellikler={[
          "Türe göre otomatik yasal süre + dayanak (TBK 117, TTK 808, TBK 315/352…)",
          "Resmî ihtarname formatında, eksiksiz taslak",
          "Word ve UYAP (.udf) olarak indirme",
        ]}
      />
    );

  return (
    <div className="grid lg:grid-cols-5 gap-6">
      <Card className="lg:col-span-2 h-fit">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            İhtarname Bilgileri
            <span className="text-[10px] rounded-full bg-primary/10 text-primary px-2 py-0.5">Yapay Zeka · Pro</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-3 text-sm">
            <div>
              <label className="font-medium mb-1 block">Tür</label>
              <select value={tur} onChange={(e) => setTur(e.target.value)} className="w-full h-10 rounded-md border bg-background px-3">
                {TURLER.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
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
              {loading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : kilitli ? (
                <Lock className="mr-2 h-4 w-4" />
              ) : (
                <Mail className="mr-2 h-4 w-4" />
              )}
              {kilitli ? "Pro ile Aç" : "İhtarname Üret"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="lg:col-span-3 space-y-4">
        {/* Bilgilendirme / upsell — ücretsiz kullanıcıya, sonuç yokken */}
        {kilitli && !sonuc && (
          <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" /> Yapay Zeka İhtarname — Pro özelliği
              </CardTitle>
              <CardDescription>
                Doğru yasal süre ve resmî dille, notere sunulabilir ihtarname taslağı.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <p className="leading-relaxed text-foreground/80">
                Seçtiğiniz türe göre (alacak temerrüdü, kira tahliyesi, çek ihtarı, fesih…) Yapay Zeka;
                <strong> doğru ihtar süresini ve yasal dayanağı</strong> (TBK 117, TTK 808, TBK 315/352 vb.)
                otomatik kurar, taraf ve alacak bilgilerinizi resmî ihtarname diline döker. Saniyeler
                içinde Word veya UYAP (.udf) olarak indirip notere götürebileceğiniz bir taslak elde edersiniz.
              </p>
              <ul className="space-y-1.5">
                {[
                  "Türe göre otomatik yasal süre + dayanak (TBK/TTK maddeleri)",
                  "Resmî ihtarname formatında, eksiksiz taslak",
                  "Word ve UYAP (.udf) olarak indirme",
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
        {loading && (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin mx-auto mb-3" />
              İhtarname yazılıyor...
            </CardContent>
          </Card>
        )}
        {sonuc && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>İhtarname Taslağı</CardTitle>
              <div className="flex gap-2">
                <Button onClick={copy} variant="outline" size="sm" title="Panoya kopyala">
                  <Copy className="h-4 w-4" />
                </Button>
                <Button onClick={() => downloadAs("docx")} variant="outline" size="sm" title="Word olarak indir">
                  <Download className="h-4 w-4 mr-1" /> Word
                </Button>
                <Button onClick={() => downloadAs("udf")} variant="outline" size="sm" title="UYAP belgesi olarak indir">
                  <Download className="h-4 w-4 mr-1" /> UYAP
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Textarea value={sonuc.ihtarname_metni} readOnly rows={25} className="font-mono text-sm" />
              {sonuc.yasa_referanslari?.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {sonuc.yasa_referanslari.map((r: string) => (
                    <span key={r} className="text-xs rounded-full bg-primary/10 text-primary px-3 py-1">
                      {r}
                    </span>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}
        {!sonuc && !loading && !error && !kilitli && (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              <Mail className="h-12 w-12 mx-auto mb-3 opacity-30" />
              Bilgileri doldurun, ihtarnameniz burada görünecek.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
