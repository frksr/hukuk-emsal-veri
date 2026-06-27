"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, FileCheck, Upload, Lock, Sparkles, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { sozlesmeAnaliz } from "@/lib/api";
import { usePlan, modulKullanabilir } from "@/lib/use-plan";
import { AracYukleniyor } from "@/components/arac-yukleniyor";
import { ProUpsell } from "@/components/pro-upsell";
import { useConfirm } from "@/components/confirm-dialog";

const TURLER = [
  ["genel", "Genel"], ["hizmet", "Hizmet"], ["satis", "Satış"],
  ["kira", "Kira"], ["gizlilik", "Gizlilik (NDA)"], ["is", "İş Sözleşmesi"],
  ["distributorluk", "Distribütörlük"],
];

// Dosya/metin sınırları (backend ile uyumlu)
const MAX_MB = 5;                  // en fazla 5 MB
const UYARI_MB = 2;                // bu boyutun üstünde "büyük dosya" onayı iste
const MAX_KARAKTER = 45_000;       // ≈ 10 sayfa
const UYARI_KARAKTER = 14_000;     // bu uzunluğun üstünde onay iste

export function SozlesmeForm() {
  const router = useRouter();
  const plan = usePlan();
  const { loading: planLoading, isLoggedIn } = plan;
  const erisim = modulKullanabilir(plan, "sozlesme");
  const [metin, setMetin] = useState("");
  const [tur, setTur] = useState("genel");
  const [loading, setLoading] = useState(false);
  // any: dinamik tip (lint eklentisi yok)
  const [sonuc, setSonuc] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const { confirm, dialog } = useConfirm();

  const kilitli = !planLoading && !erisim;

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (e.target) e.target.value = ""; // aynı dosya tekrar seçilebilsin
    if (!file) return;
    if (!isLoggedIn) { router.push("/kayit"); return; }
    if (!erisim) {
      router.push("/panel/ayarlar/ek-paketler?modul=sozlesme");
      return;
    }
    // Boyut sınırı
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`Dosya çok büyük (en fazla ${MAX_MB} MB, en fazla 10 sayfa). Lütfen sözleşmenin ilgili bölümünü yükleyin.`);
      return;
    }
    // Büyük dosya → uyar ve onay iste
    if (file.size > UYARI_MB * 1024 * 1024) {
      const onay = await confirm(
        "Yüklediğiniz sözleşme büyük görünüyor. Analiz birkaç adımda yapılır, biraz sürebilir ve kullanım hakkınızdan 1 düşülür. Devam edilsin mi?",
        { title: "Büyük sözleşme", confirmText: "Devam et", cancelText: "Vazgeç" },
      );
      if (!onay) return;
    }
    setFileLoading(true);
    setError(null);
    try {
      // PDF/DOCX → proxy üzerinden upload (auth JWT eklenir, backend Pro kontrol eder)
      const formData = new FormData();
      formData.append("file", file);
      formData.append("sozlesme_turu", tur);
      const res = await fetch("/api/proxy/sozlesme/upload", { method: "POST", body: formData });
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!metin.trim()) return;
    if (!isLoggedIn) { router.push("/kayit"); return; }
    if (!erisim) {
      router.push("/panel/ayarlar/ek-paketler?modul=sozlesme");
      return;
    }
    // Uzunluk sınırı
    if (metin.length > MAX_KARAKTER) {
      setError(`Sözleşme metni çok uzun (≈10 sayfa sınırı). Lütfen daha kısa bir bölüm yapıştırın.`);
      return;
    }
    // Büyük metin → uyar ve onay iste
    if (metin.length > UYARI_KARAKTER) {
      const onay = await confirm(
        "Girdiğiniz sözleşme uzun görünüyor. Analiz birkaç adımda yapılır, biraz sürebilir ve kullanım hakkınızdan 1 düşülür. Devam edilsin mi?",
        { title: "Uzun sözleşme", confirmText: "Devam et", cancelText: "Vazgeç" },
      );
      if (!onay) return;
    }
    setLoading(true); setError(null);
    try {
      const data = await sozlesmeAnaliz({ metin, sozlesme_turu: tur });
      setSonuc(data);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 402 || status === 401) setError("Bu araçtaki bu ayki kullanım hakkın doldu. Pro'ya geçebilir veya ek paket alabilirsin.");
      else setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  const riskRengi = (s: string) => s === "yuksek" ? "bg-red-100 text-red-900 border-red-300"
    : s === "orta" ? "bg-amber-100 text-amber-900 border-amber-300"
    : "bg-emerald-100 text-emerald-900 border-emerald-300";

  if (planLoading) return <AracYukleniyor />;
  if (kilitli)
    return (
      <ProUpsell
        isLoggedIn={isLoggedIn}
        modul="sozlesme"
        baslik="Sözleşme Analizi"
        aciklama="Sözleşmedeki riskleri ve eksik maddeleri imzalamadan önce görün."
        ozellikler={[
          "Madde madde risk seviyesi (düşük / orta / yüksek)",
          "Eksik / koruyucu madde tespiti",
          "Her madde için iyileştirme önerisi + genel risk skoru",
        ]}
      />
    );

  return (
    <div className="space-y-6">
      {dialog}
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
              {loading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : kilitli ? (
                <Lock className="mr-2 h-4 w-4" />
              ) : (
                <FileCheck className="mr-2 h-4 w-4" />
              )}
              {kilitli ? "Pro ile Aç" : "Analiz Et"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Bilgilendirme / upsell — ücretsiz kullanıcıya, sonuç yokken */}
      {kilitli && !sonuc && (
        <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" /> Sözleşme Analizi — Pro özelliği
            </CardTitle>
            <CardDescription>Sözleşmedeki riskleri ve eksik maddeleri imzalamadan önce görün.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <p className="leading-relaxed text-foreground/80">
              Sözleşmenizi yapıştırın veya PDF/DOCX yükleyin; Yapay Zeka <strong>madde madde risk analizi</strong>{" "}
              yapar, aleyhinize hükümleri ve <strong>eksik koruyucu maddeleri</strong> tespit eder, her madde
              için somut <strong>iyileştirme önerisi</strong> verir ve genel bir risk skoru çıkarır.
              İmza atmadan önce sizi koruyacak bir ön inceleme.
            </p>
            <ul className="space-y-1.5">
              {[
                "Madde madde risk seviyesi (düşük / orta / yüksek)",
                "Eksik / koruyucu madde tespiti",
                "Her madde için iyileştirme önerisi + genel risk skoru",
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
