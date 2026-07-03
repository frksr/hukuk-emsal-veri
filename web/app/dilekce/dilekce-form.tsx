"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, Download, Copy, FileText, Sparkles, Lock, Check, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { dilekceSablon, dilekceStream, exportBelge, type DilekceSonuc } from "@/lib/api";
import { usePlan, modulKullanabilir } from "@/lib/use-plan";
import { NotHatirlatma } from "@/components/not-hatirlatma";
import { AracYukleniyor } from "@/components/arac-yukleniyor";

const TURLER = [
  { value: "itirazin_iptali", label: "İtirazın İptali (İİK 67)" },
  { value: "ihalenin_feshi", label: "İhalenin Feshi (İİK 134)" },
  { value: "menfi_tespit", label: "Menfi Tespit (İİK 72)" },
  { value: "tahsilat", label: "Tahsilat Davası" },
  { value: "genel", label: "Genel Hukuk Davası" },
  { value: "diger", label: "Diğer (belirtin)" },
];

type Mode = "sablon" | "ai";

export function DilekceForm() {
  const router = useRouter();
  const plan = usePlan();
  const { loading: planLoading, isPaid, isLoggedIn } = plan;
  const dilekceErisim = modulKullanabilir(plan, "dilekce");

  const [mode, setMode] = useState<Mode>("sablon");
  const [durum, setDurum] = useState("");
  const [tur, setTur] = useState("itirazin_iptali");
  // "Diğer" seçilince kullanıcının serbest yazdığı dilekçe konusu (örn.
  // "Boşanma Davası") — dropdown'da olmayan türler için çözüm.
  const [ozelKonu, setOzelKonu] = useState("");
  const [alacakli, setAlacakli] = useState("");
  const [borclu, setBorclu] = useState("");
  const [loading, setLoading] = useState(false);
  const [sonuc, setSonuc] = useState<DilekceSonuc | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Emsal aramadan "bu konuda dilekçe yaz" ile gelindiyse durumu ön-doldur.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const d = params.get("durum");
    if (d) setDurum(d);
  }, []);

  // Ücretli kullanıcıya varsayılan olarak Yapay Zeka modunu öner (yalnızca bir kez).
  const modeInit = useRef(false);
  useEffect(() => {
    if (planLoading || modeInit.current) return;
    modeInit.current = true;
    if (isPaid) setMode("ai");
  }, [planLoading, isPaid]);

  const aiKilitli = mode === "ai" && !planLoading && !dilekceErisim;

  // Plan çözülene kadar formu gösterme (flash önleme)
  if (planLoading) return <AracYukleniyor />;

  const digerSecili = tur === "diger";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!durum.trim()) return;
    if (digerSecili && !ozelKonu.trim()) return;
    if (!isLoggedIn) { router.push("/kayit"); return; }
    if (mode === "ai" && !dilekceErisim) {
      router.push("/panel/ayarlar/ek-paketler?modul=dilekce");
      return;
    }
    setLoading(true);
    setError(null);
    setSonuc(null);

    // "Diğer" seçiliyse backend'e geçerli bir dilekce_turu ("genel") gönderilir;
    // asıl konu ozel_konu alanıyla iletilir (dropdown'da olmayan türler için).
    const params = {
      durum,
      dilekce_turu: digerSecili ? "genel" : tur,
      taraflar: { alacakli, borclu },
      k: 5,
      ...(digerSecili ? { ozel_konu: ozelKonu.trim() } : {}),
    };

    // Şablon modu — LLM yok, anında.
    if (mode === "sablon") {
      try {
        const data = await dilekceSablon(params);
        setSonuc(data as unknown as DilekceSonuc);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Şablon üretilemedi.");
      } finally {
        setLoading(false);
      }
      return;
    }

    // Yapay Zeka + Emsal modu — proxy üzerinden streaming (auth + Pro kontrolü backend'de).
    try {
      let metin = "";
      let streamErr: string | null = null;
      await dilekceStream(params, {
        onMeta: (meta) => {
          setSonuc({
            dilekce_metni: "",
            kullanilan_emsaller: meta.kullanilan_emsaller,
            uyari: meta.uyari,
          } as DilekceSonuc);
        },
        onDelta: (text) => {
          metin += text;
          setSonuc((prev) =>
            prev
              ? { ...prev, dilekce_metni: metin }
              : ({ dilekce_metni: metin, kullanilan_emsaller: [] } as unknown as DilekceSonuc)
          );
        },
        onError: (msg) => {
          streamErr = msg;
        },
      });
      if (streamErr) throw new Error(streamErr);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 402 || status === 401) {
        setError("Bu ayki Yapay Zeka dilekçe hakkın doldu. Pro'ya geçebilir veya ek paket alabilirsin.");
        setSonuc(null);
      } else {
        setError(err instanceof Error ? err.message : "Dilekçe üretilemedi.");
      }
    } finally {
      setLoading(false);
    }
  }

  function copyDilekce() {
    if (sonuc?.dilekce_metni) navigator.clipboard.writeText(sonuc.dilekce_metni);
  }

  async function downloadAs(format: "docx" | "udf") {
    if (!sonuc?.dilekce_metni) return;
    try {
      await exportBelge(format, { metin: sonuc.dilekce_metni, dosya_adi: `dilekce-${tur}` });
    } catch (err) {
      setError(err instanceof Error ? err.message : "İndirme hatası.");
    }
  }

  return (
    <div className="grid lg:grid-cols-5 gap-6">
      <Card className="lg:col-span-2 h-fit">
        <CardHeader>
          <CardTitle>Dava Bilgileri</CardTitle>
          <CardDescription>Bilgiler ne kadar detaylı olursa dilekçe o kadar isabetli olur.</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Mod seçici */}
          <div className="grid grid-cols-2 gap-2 mb-4 p-1 rounded-lg bg-muted/50">
            <button
              type="button"
              onClick={() => setMode("sablon")}
              className={`rounded-md px-3 py-2 text-sm font-medium transition ${
                mode === "sablon" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Hızlı Şablon
              <span className="block text-[10px] font-normal text-muted-foreground">Ücretsiz</span>
            </button>
            <button
              type="button"
              onClick={() => setMode("ai")}
              className={`rounded-md px-3 py-2 text-sm font-medium transition flex flex-col items-center ${
                mode === "ai" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <span className="inline-flex items-center gap-1">
                {isPaid ? <Sparkles className="h-3.5 w-3.5 text-primary" /> : <Lock className="h-3 w-3" />}
                Yapay Zeka + Emsal
              </span>
              <span className="block text-[10px] font-normal text-primary">Pro</span>
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Dilekçe Türü</label>
              <select
                value={tur}
                onChange={(e) => setTur(e.target.value)}
                className="w-full h-10 rounded-md border bg-background px-3 text-sm"
              >
                {TURLER.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              {digerSecili && (
                <Input
                  className="mt-2"
                  value={ozelKonu}
                  onChange={(e) => setOzelKonu(e.target.value)}
                  placeholder="Dilekçe konusunu yazın (örn: Boşanma Davası, Kira Tespiti)"
                  maxLength={200}
                />
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-sm font-medium mb-1.5 block">Alacaklı</label>
                <Input value={alacakli} onChange={(e) => setAlacakli(e.target.value)} placeholder="Ad Soyad / Şirket" />
              </div>
              <div>
                <label className="text-sm font-medium mb-1.5 block">Borçlu</label>
                <Input value={borclu} onChange={(e) => setBorclu(e.target.value)} placeholder="Ad Soyad / Şirket" />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Dava Durumu</label>
              <Textarea
                value={durum}
                onChange={(e) => setDurum(e.target.value)}
                rows={10}
                placeholder="Örn: Müvekkilim, davalıya 50.000 TL borç verdi. Senet vade tarihinde ödenmedi. İcra takibi başlatıldı ancak davalı borca itiraz etti..."
              />
            </div>
            <NotHatirlatma q={durum} />
            <Button
              type="submit"
              disabled={loading || !durum.trim() || (digerSecili && !ozelKonu.trim())}
              className="w-full"
              size="lg"
            >
              {loading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : aiKilitli ? (
                <Lock className="mr-2 h-4 w-4" />
              ) : mode === "ai" ? (
                <Sparkles className="mr-2 h-4 w-4" />
              ) : (
                <FileText className="mr-2 h-4 w-4" />
              )}
              {aiKilitli ? "Pro ile Aç" : mode === "ai" ? "Yapay Zeka ile Üret" : "Şablon Üret"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="lg:col-span-3 space-y-4">
        {/* Karşılaştırma / upsell — Yapay Zeka modunda ücretsiz kullanıcıya, sonuç yokken göster */}
        {mode === "ai" && !isPaid && !sonuc && !loading && (
          <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" /> Yapay Zeka + Emsal — neden fark eder?
              </CardTitle>
              <CardDescription>
                Şablon size boş bir iskelet verir; Yapay Zeka ise dilekçeyi sizin için <strong>yazar</strong>.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <p className="leading-relaxed text-foreground/80">
                Anlattığınız olayı analiz eder, <strong>166.000+ Yargıtay ve Danıştay kararı</strong>{" "}
                arasından dosyanıza en uygun emsalleri bulur ve bunlara atıfla mahkemeyi ikna edecek{" "}
                <strong>özgün bir gerekçe</strong> kurar. Yani değişen yalnızca isimler değildir —
                vakıa anlatımınız, hukuki argümanınız ve dayandığınız içtihatlar dosyanıza özel üretilir.
                Bir avukatın saatlerce süren emsal taramasını saniyelere indirir.
              </p>
              <ul className="space-y-1.5">
                {[
                  "Dosyanıza özel emsal kararlar (gerçek esas/karar no ile atıf)",
                  "Olaya uyarlanmış, gerekçeli hukuki argüman",
                  "Word ve UYAP (.udf) olarak indirme",
                ].map((m) => (
                  <li key={m} className="flex items-start gap-2">
                    <Check className="h-4 w-4 text-primary mt-0.5 shrink-0" /> {m}
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <Button onClick={() => router.push("/fiyatlandirma")}>
                  <Sparkles className="h-4 w-4 mr-1.5" /> Pro&apos;ya geç
                </Button>
                <button
                  type="button"
                  onClick={() => setMode("sablon")}
                  className="text-sm text-muted-foreground hover:text-foreground underline"
                >
                  Şimdilik ücretsiz şablonu dene
                </button>
              </div>
            </CardContent>
          </Card>
        )}

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            ⚠️ {error}
          </div>
        )}
        {loading && !sonuc && (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin mx-auto mb-3" />
              <p>{mode === "ai" ? "Emsal kararlar bulunuyor, dilekçe yazılıyor..." : "Şablon hazırlanıyor..."}</p>
            </CardContent>
          </Card>
        )}
        {loading && sonuc && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Dilekçe yazılıyor...</span>
          </div>
        )}
        {!loading && !sonuc && !error && !(mode === "ai" && !isPaid) && (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p>Form bilgilerini doldurun, dilekçeniz burada görünecek.</p>
            </CardContent>
          </Card>
        )}
        {sonuc && (
          <>
            {sonuc.uyari && (
              <div className="rounded-lg border border-amber-300/50 bg-amber-50 dark:bg-amber-950/20 p-3 text-xs text-amber-800 dark:text-amber-200">
                {sonuc.uyari}
              </div>
            )}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle>Dilekçe Taslağı</CardTitle>
                <div className="flex gap-2">
                  <Button onClick={copyDilekce} variant="outline" size="sm" title="Panoya kopyala">
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
                <Textarea value={sonuc.dilekce_metni} readOnly rows={20} className="font-mono text-sm" />
              </CardContent>
            </Card>
            {sonuc.kullanilan_emsaller?.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Kullanılan Emsal Kararlar</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {sonuc.kullanilan_emsaller.map((em, i) => (
                    <div key={i} className="text-sm border-l-4 border-accent pl-3">
                      <div className="font-semibold flex items-center gap-1.5 flex-wrap">
                        {em.karar_id ? (
                          <Link
                            href={`/karar/${encodeURIComponent(em.karar_id)}`}
                            target="_blank"
                            className="hover:underline hover:text-primary inline-flex items-center gap-1"
                            title="Kararın detayına git"
                          >
                            {em.atif_text}
                            <ExternalLink className="h-3 w-3 shrink-0" />
                          </Link>
                        ) : (
                          em.atif_text
                        )}
                      </div>
                      <div className="text-muted-foreground text-xs mt-1">{em.ilgili_bolum}</div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
            {/* Şablon sonucu sonrası hafif upsell */}
            {!isPaid && (sonuc.kullanilan_emsaller?.length ?? 0) === 0 && (
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 text-sm flex flex-wrap items-center justify-between gap-3">
                <span className="text-foreground/80">
                  Bu taslak emsal atfı içermiyor. <strong>Yapay Zeka + Emsal</strong> ile dosyanıza özel,
                  içtihatlara dayalı gerekçe ekleyin.
                </span>
                <Button size="sm" onClick={() => router.push("/fiyatlandirma")}>
                  Pro&apos;ya geç
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
