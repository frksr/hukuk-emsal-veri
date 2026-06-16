"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, FileSearch, Upload, AlertTriangle, CheckCircle2, ChevronDown, Lock, Sparkles, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { belgeDenetText, type DenetimSonuc } from "@/lib/api";
import { usePlan, modulKullanabilir } from "@/lib/use-plan";
import { AracYukleniyor } from "@/components/arac-yukleniyor";
import { ProUpsell } from "@/components/pro-upsell";

const TURLER = [
  ["dilekce", "Dilekçe (genel)"],
  ["dava_dilekce", "Dava Dilekçesi"],
  ["cevap_dilekce", "Cevap Dilekçesi"],
  ["ihtarname", "İhtarname"],
  ["sozlesme", "Sözleşme"],
  ["genel", "Genel Hukuki Belge"],
];

export function DenetimForm() {
  const router = useRouter();
  const plan = usePlan();
  const { loading: planLoading, isLoggedIn } = plan;
  const erisim = modulKullanabilir(plan, "denetim");
  const [metin, setMetin] = useState("");
  const [tur, setTur] = useState("dilekce");
  const [loading, setLoading] = useState(false);
  const [sonuc, setSonuc] = useState<DenetimSonuc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);

  const kilitli = !planLoading && !erisim;

  function gate(): boolean {
    // true → işleme devam edilebilir; false → yönlendirildi
    if (!isLoggedIn) { router.push("/kayit"); return false; }
    if (!erisim) { router.push("/app/ayarlar/ek-paketler?modul=denetim"); return false; }
    return true;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (metin.trim().length < 50) return;
    if (!gate()) return;
    setLoading(true); setError(null);
    try {
      const data = await belgeDenetText({ metin, tur, k: 5 });
      setSonuc(data);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 402 || status === 401) setError("Bu araçtaki bu ayki kullanım hakkın doldu. Pro'ya geçebilir veya ek paket alabilirsin.");
      else setError(err instanceof Error ? err.message : "Hata");
      setSonuc(null);
    } finally { setLoading(false); }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!gate()) return;
    setFileLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("tur", tur);
      // Proxy üzerinden (auth + Pro kontrolü backend'de)
      const res = await fetch("/api/proxy/denetim/upload", { method: "POST", body: formData });
      if (res.status === 401 || res.status === 402) {
        setError("Bu araçtaki bu ayki kullanım hakkın doldu. Pro'ya geçebilir veya ek paket alabilirsin.");
        return;
      }
      const json = await res.json();
      if (json.ok) setSonuc(json.data ?? json);
      else setError(json.message || "Dosya yüklenemedi");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Yükleme hatası");
    } finally { setFileLoading(false); }
  }

  const ciddiyetRengi = (c: string) =>
    c === "yuksek" ? "bg-red-50 border-red-300 text-red-900 dark:bg-red-950/40 dark:border-red-800/60 dark:text-red-200"
    : c === "orta" ? "bg-amber-50 border-amber-300 text-amber-900 dark:bg-amber-950/40 dark:border-amber-800/60 dark:text-amber-200"
    : "bg-blue-50 border-blue-300 text-blue-900 dark:bg-blue-950/40 dark:border-blue-800/60 dark:text-blue-200";

  const skorRengi = (s: number) =>
    s >= 70 ? "text-destructive" : s >= 40 ? "text-amber-600" : "text-emerald-600";

  if (planLoading) return <AracYukleniyor />;
  if (kilitli)
    return (
      <ProUpsell
        isLoggedIn={isLoggedIn}
        modul="denetim"
        baslik="Belge Denetleyici"
        aciklama="Dilekçe/ihtarname/sözleşmenizi mahkemeye sunmadan Yapay Zeka ile denetleyin."
        ozellikler={[
          "Yasal dayanak ve emsal uyumluluk kontrolü",
          "Eksik / zayıf bölüm tespiti + iyileştirme önerisi",
          "Genel risk skoru",
        ]}
      />
    );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>Belgeyi Yapıştır veya Yükle</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex gap-3 items-center flex-wrap">
              <label className="text-sm font-medium">Belge Türü</label>
              <select value={tur} onChange={(e) => setTur(e.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                {TURLER.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <div className="flex-1" />
              <label className="cursor-pointer">
                <input type="file" accept=".pdf,.docx,.txt,.md" onChange={handleFileUpload} className="hidden" disabled={fileLoading} />
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
            <Textarea value={metin} onChange={(e) => setMetin(e.target.value)} rows={12}
              placeholder="Denetlemek istediğiniz dilekçe / ihtarname / sözleşme metnini buraya yapıştırın..." />
            <div className="flex items-center justify-between">
              <div className="text-xs text-muted-foreground">
                {metin.length.toLocaleString("tr-TR")} karakter · min 50
              </div>
              <Button type="submit" disabled={loading || metin.trim().length < 50} size="lg">
                {loading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : kilitli ? (
                  <Lock className="mr-2 h-4 w-4" />
                ) : (
                  <FileSearch className="mr-2 h-4 w-4" />
                )}
                {kilitli ? "Pro ile Aç" : "Denetle"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Bilgilendirme / upsell — ücretsiz kullanıcıya, sonuç yokken */}
      {kilitli && !sonuc && (
        <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" /> Belge Denetleyici — Pro özelliği
            </CardTitle>
            <CardDescription>Dilekçe/ihtarname/sözleşmenizi mahkemeye sunmadan Yapay Zeka ile denetleyin.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <p className="leading-relaxed text-foreground/80">
              Yazdığınız belgeyi yükleyin veya yapıştırın; Yapay Zeka <strong>yasal dayanağın doğruluğunu</strong>,
              <strong> eksik bölümleri</strong>, Yargıtay emsallerine aykırı argümanları ve karşı tarafın
              yakalayabileceği <strong>zayıf noktaları</strong> tespit eder, her biri için iyileştirme önerir.
            </p>
            <ul className="space-y-1.5">
              {[
                "Yasal dayanak ve emsal uyumluluk kontrolü",
                "Eksik/zayıf bölüm tespiti + iyileştirme önerisi",
                "Genel risk skoru",
              ].map((m) => (
                <li key={m} className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-primary mt-0.5 shrink-0" /> {m}
                </li>
              ))}
            </ul>
            <Button onClick={() => router.push(isLoggedIn ? "/fiyatlandirma" : "/kayit")}>
              <Sparkles className="h-4 w-4 mr-1.5" /> {isLoggedIn ? "Pro'ya geç" : "Ücretsiz kayıt ol"}
            </Button>
          </CardContent>
        </Card>
      )}

      {error && <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>}

      {loading && (
        <Card><CardContent className="p-12 text-center text-muted-foreground">
          <Loader2 className="h-10 w-10 animate-spin mx-auto mb-3" />
          <p>Belge denetleniyor... Yasal dayanak, emsal uyumluluk ve yapı kontrolleri yapılıyor.</p>
        </CardContent></Card>
      )}

      {sonuc && (
        <>
          {/* Risk skoru */}
          <Card>
            <CardContent className="p-6">
              <div className="grid md:grid-cols-3 gap-6 items-center">
                <div className="text-center">
                  <div className="text-xs text-muted-foreground mb-1">Genel Risk Skoru</div>
                  <div className={`text-6xl font-bold ${skorRengi(sonuc.genel_risk_skoru)}`}>
                    {sonuc.genel_risk_skoru}<span className="text-2xl text-muted-foreground">/100</span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    {sonuc.genel_risk_skoru >= 70 ? "🔴 Yüksek risk" : sonuc.genel_risk_skoru >= 40 ? "🟡 Orta risk" : "🟢 Düşük risk"}
                  </div>
                </div>
                <div className="md:col-span-2">
                  <div className="text-sm font-semibold mb-2">Özet</div>
                  <p className="text-sm text-muted-foreground">{sonuc.ozet || "—"}</p>
                  <div className="flex gap-4 mt-4 text-sm">
                    <div><span className="font-bold text-destructive">{sonuc.uyarilar?.length || 0}</span> uyarı</div>
                    <div><span className="font-bold text-amber-600">{sonuc.eksik_bolumler?.length || 0}</span> eksik bölüm</div>
                    <div><span className="font-bold text-emerald-600">{sonuc.guclu_yonler?.length || 0}</span> güçlü yön</div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Kritik sorunlar */}
          {sonuc.kritik_sorunlar?.length > 0 && (
            <Card className="border-destructive">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-destructive" /> Kritik Sorunlar
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {sonuc.kritik_sorunlar.map((s, i) => <li key={i} className="flex gap-2"><span className="text-destructive">●</span>{s}</li>)}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Uyarılar — detaylı */}
          {sonuc.uyarilar?.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base">Detaylı Uyarılar ({sonuc.uyarilar.length})</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {sonuc.uyarilar.map((u, i) => (
                  <details key={i} className={`rounded border p-3 ${ciddiyetRengi(u.ciddiyet)}`}>
                    <summary className="cursor-pointer text-sm font-semibold flex items-center gap-2">
                      <span className="text-xs uppercase">{u.ciddiyet}</span>
                      <span className="text-xs rounded-full bg-white/50 px-2 py-0.5 dark:bg-white/10">{u.kategori}</span>
                      <span className="flex-1">{u.sorun}</span>
                      <ChevronDown className="h-4 w-4" />
                    </summary>
                    <div className="mt-3 space-y-2 text-sm">
                      {u.ilgili_bolum && (
                        <div className="bg-white/60 rounded p-2 text-xs font-mono dark:bg-white/10">
                          <span className="opacity-60">İlgili bölüm:</span> {u.ilgili_bolum}
                        </div>
                      )}
                      <div><strong>Öneri:</strong> {u.oneri}</div>
                    </div>
                  </details>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Eksik bölümler */}
          {sonuc.eksik_bolumler?.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base">Eksik Bölümler / Maddeler</CardTitle></CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {sonuc.eksik_bolumler.map((b, i) => (
                    <span key={i} className="text-sm rounded-full bg-amber-100 text-amber-900 px-3 py-1">⚠ {b}</span>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Emsal uyumsuzluk */}
          {sonuc.emsal_uyumsuzluk?.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base">Emsal Aykırılıkları</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {sonuc.emsal_uyumsuzluk.map((u, i) => (
                  <div key={i} className="text-sm border-l-4 border-destructive pl-3 py-1">
                    <div className="font-semibold">{u.karar_id}</div>
                    <div className="text-muted-foreground">{u.neden}</div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Güçlü yönler */}
          {sonuc.guclu_yonler?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Güçlü Yönler
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {sonuc.guclu_yonler.map((g, i) => <li key={i} className="flex gap-2"><span className="text-emerald-600">✓</span>{g}</li>)}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Dayanak emsaller */}
          {sonuc.dayanak_emsaller?.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base">Konuyla İlgili Emsal Kararlar</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {sonuc.dayanak_emsaller.map((e, i) => (
                  <details key={i} className="rounded border p-3">
                    <summary className="cursor-pointer text-sm font-semibold">
                      {e.atif} · {e.tarih}
                    </summary>
                    <p className="mt-2 text-sm text-muted-foreground">{e.ozet}</p>
                  </details>
                ))}
              </CardContent>
            </Card>
          )}

          <div className="text-xs text-muted-foreground p-3 rounded border border-amber-200 bg-amber-50">
            ⚠️ {sonuc.yasal_uyari}
          </div>
        </>
      )}

      {!sonuc && !loading && !error && (
        <Card><CardContent className="p-12 text-center text-muted-foreground">
          <FileSearch className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>Belgeyi yapıştırın veya yükleyin, Yapay Zeka denetim raporu burada görünecek.</p>
        </CardContent></Card>
      )}
    </div>
  );
}
