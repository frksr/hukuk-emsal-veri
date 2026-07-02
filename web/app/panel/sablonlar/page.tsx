"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { BookCopy, Copy, Check, Loader2, Plus, Trash2, X, FileText, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useConfirm } from "@/components/confirm-dialog";
import { ListSkeleton } from "@/components/list-skeleton";

type Sablon = {
  id: string;
  baslik: string;
  kategori: string;
  icerik: string;
  degiskenler: string[];
  platform: boolean;
};

const KATEGORI_ETIKET: Record<string, string> = {
  icra: "İcra",
  hukuk: "Hukuk",
  istinaf: "İstinaf",
  genel: "Genel",
};

// Değişken adlarını okunur etikete çevir ("dosya_no" → "Dosya No")
function etiket(d: string): string {
  return d
    .split("_")
    .map((k) => k.charAt(0).toLocaleUpperCase("tr-TR") + k.slice(1))
    .join(" ");
}

export default function SablonlarPage() {
  const router = useRouter();
  const [liste, setListe] = useState<Sablon[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kategori, setKategori] = useState<string>("");
  const { confirm, dialog } = useConfirm();

  // "Kullan" akışı
  const [secili, setSecili] = useState<Sablon | null>(null);
  const [degerler, setDegerler] = useState<Record<string, string>>({});
  const [sonuc, setSonuc] = useState<string | null>(null);
  const [uygulaniyor, setUygulaniyor] = useState(false);
  const [kopyalandi, setKopyalandi] = useState(false);

  // Yeni şablon formu
  const [yeniAcik, setYeniAcik] = useState(false);
  const [yeni, setYeni] = useState({ baslik: "", kategori: "genel", icerik: "" });
  const [kaydediliyor, setKaydediliyor] = useState(false);

  async function yukle() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/proxy/sablonlar/", { cache: "no-store" });
      if (!r.ok) throw new Error("Şablonlar yüklenemedi.");
      const j = await r.json();
      setListe((j?.data ?? j)?.sablonlar ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { yukle(); }, []);

  const kategoriler = useMemo(
    () => Array.from(new Set((liste ?? []).map((s) => s.kategori))),
    [liste],
  );
  const filtreli = (liste ?? []).filter((s) => !kategori || s.kategori === kategori);
  const platformlar = filtreli.filter((s) => s.platform);
  const benimkiler = filtreli.filter((s) => !s.platform);

  function kullan(s: Sablon) {
    setSecili(s);
    setDegerler({});
    setSonuc(null);
    setKopyalandi(false);
  }

  async function uygula() {
    if (!secili) return;
    setUygulaniyor(true);
    try {
      const r = await fetch(`/api/proxy/sablonlar/${secili.id}/uygula`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ degerler }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.message || "Uygulanamadı.");
      setSonuc((j?.data ?? j)?.icerik ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setUygulaniyor(false);
    }
  }

  async function kopyala() {
    if (!sonuc) return;
    await navigator.clipboard.writeText(sonuc);
    setKopyalandi(true);
    setTimeout(() => setKopyalandi(false), 2000);
  }

  function dilekceAracindaAc() {
    if (!sonuc) return;
    sessionStorage.setItem("sablon_taslak", sonuc);
    router.push("/panel/dilekce?taslak=sablon");
  }

  async function yeniKaydet() {
    if (yeni.baslik.trim().length < 3 || yeni.icerik.trim().length < 20) {
      setError("Başlık (min 3) ve içerik (min 20 karakter) gerekli.");
      return;
    }
    setKaydediliyor(true);
    setError(null);
    try {
      const r = await fetch("/api/proxy/sablonlar/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(yeni),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.message || "Kaydedilemedi.");
      setYeni({ baslik: "", kategori: "genel", icerik: "" });
      setYeniAcik(false);
      await yukle();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setKaydediliyor(false);
    }
  }

  async function sil(id: string) {
    const onay = await confirm("Bu şablon kalıcı olarak silinecek. Devam edilsin mi?", {
      title: "Şablonu sil",
      confirmText: "Sil",
      danger: true,
    });
    if (!onay) return;
    await fetch(`/api/proxy/sablonlar/${id}`, { method: "DELETE" });
    await yukle();
  }

  return (
    <div className="space-y-6">
      {dialog}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BookCopy className="h-6 w-6 text-primary" /> Dilekçe Şablonları
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Hazır şablonu seçin, değişkenleri doldurun, kopyalayın veya dilekçe aracında geliştirin.
          </p>
        </div>
        <Button size="sm" onClick={() => setYeniAcik((v) => !v)}>
          <Plus className="h-4 w-4 mr-1.5" /> Kendi Şablonum
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          ⚠️ {error}
        </div>
      )}

      {/* Yeni şablon formu */}
      {yeniAcik && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Yeni şablon</CardTitle>
            <CardDescription>
              Değişkenler için çift süslü parantez kullanın: {"{{mahkeme}}"}, {"{{dosya_no}}"} gibi.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid sm:grid-cols-2 gap-3">
              <Input
                placeholder="Şablon başlığı"
                value={yeni.baslik}
                onChange={(e) => setYeni({ ...yeni, baslik: e.target.value })}
              />
              <Input
                placeholder="Kategori (örn: icra, hukuk)"
                value={yeni.kategori}
                onChange={(e) => setYeni({ ...yeni, kategori: e.target.value })}
              />
            </div>
            <Textarea
              rows={8}
              placeholder={"Şablon metni… {{degisken}} kullanabilirsiniz."}
              value={yeni.icerik}
              onChange={(e) => setYeni({ ...yeni, icerik: e.target.value })}
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setYeniAcik(false)}>
                <X className="h-4 w-4 mr-1" /> Vazgeç
              </Button>
              <Button onClick={yeniKaydet} disabled={kaydediliyor}>
                {kaydediliyor ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Plus className="h-4 w-4 mr-1" />}
                Kaydet
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Kategori filtresi */}
      {kategoriler.length > 1 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setKategori("")}
            className={`rounded-full border px-3 py-1 text-xs ${!kategori ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground hover:text-foreground"}`}
          >
            Tümü
          </button>
          {kategoriler.map((k) => (
            <button
              key={k}
              onClick={() => setKategori(k === kategori ? "" : k)}
              className={`rounded-full border px-3 py-1 text-xs ${kategori === k ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground hover:text-foreground"}`}
            >
              {KATEGORI_ETIKET[k] ?? k}
            </button>
          ))}
        </div>
      )}

      {loading && <ListSkeleton rows={3} />}

      {!loading && platformlar.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Platform Şablonları
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 stagger">
            {platformlar.map((s) => (
              <SablonKart key={s.id} s={s} onKullan={kullan} />
            ))}
          </div>
        </section>
      )}

      {!loading && benimkiler.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Şablonlarım
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 stagger">
            {benimkiler.map((s) => (
              <SablonKart key={s.id} s={s} onKullan={kullan} onSil={sil} />
            ))}
          </div>
        </section>
      )}

      {!loading && filtreli.length === 0 && (
        <Card><CardContent className="p-8 text-center text-muted-foreground">
          <BookCopy className="h-10 w-10 mx-auto mb-3 opacity-30" />
          Bu kategoride şablon yok.
        </CardContent></Card>
      )}

      {/* Kullan modalı */}
      {secili && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-foreground/25 backdrop-blur-sm p-4 animate-fade-in"
          onClick={() => setSecili(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="w-full max-w-2xl rounded-xl border bg-background p-6 shadow-xl max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-lg font-semibold">{secili.baslik}</h3>
              <button onClick={() => setSecili(null)} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>

            {!sonuc ? (
              <>
                <p className="mt-1 text-sm text-muted-foreground">
                  Değişkenleri doldurun; boş bırakılanlar ______ olarak kalır.
                </p>
                <div className="mt-4 grid sm:grid-cols-2 gap-3">
                  {secili.degiskenler.map((d) => (
                    <div key={d}>
                      <label className="text-xs font-medium text-muted-foreground mb-1 block">
                        {etiket(d)}
                      </label>
                      <Input
                        value={degerler[d] ?? ""}
                        onChange={(e) => setDegerler({ ...degerler, [d]: e.target.value })}
                        placeholder={etiket(d)}
                      />
                    </div>
                  ))}
                </div>
                <div className="mt-5 flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setSecili(null)}>Vazgeç</Button>
                  <Button onClick={uygula} disabled={uygulaniyor}>
                    {uygulaniyor ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <FileText className="h-4 w-4 mr-1.5" />}
                    Metni Oluştur
                  </Button>
                </div>
              </>
            ) : (
              <>
                <pre className="mt-4 max-h-[50vh] overflow-auto whitespace-pre-wrap rounded-lg border bg-secondary/40 p-4 text-sm font-sans">
                  {sonuc}
                </pre>
                <div className="mt-4 flex flex-wrap justify-end gap-2">
                  <Button variant="ghost" onClick={() => setSonuc(null)}>← Değişkenlere dön</Button>
                  <Button variant="outline" onClick={kopyala}>
                    {kopyalandi ? <Check className="h-4 w-4 mr-1.5 text-emerald-600" /> : <Copy className="h-4 w-4 mr-1.5" />}
                    {kopyalandi ? "Kopyalandı" : "Kopyala"}
                  </Button>
                  <Button onClick={dilekceAracindaAc}>
                    <Sparkles className="h-4 w-4 mr-1.5" /> Dilekçe aracında geliştir
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SablonKart({
  s, onKullan, onSil,
}: {
  s: Sablon;
  onKullan: (s: Sablon) => void;
  onSil?: (id: string) => void;
}) {
  return (
    <Card className="hover-lift flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] uppercase tracking-wider rounded-full bg-primary/10 text-primary px-2 py-0.5">
            {KATEGORI_ETIKET[s.kategori] ?? s.kategori}
          </span>
          {onSil && (
            <button
              onClick={() => onSil(s.id)}
              title="Sil"
              className="text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
        <CardTitle className="text-base mt-1">{s.baslik}</CardTitle>
        <CardDescription className="line-clamp-2">
          {s.icerik.slice(0, 120)}…
        </CardDescription>
      </CardHeader>
      <CardContent className="mt-auto">
        <Button size="sm" className="w-full" onClick={() => onKullan(s)}>
          Kullan
        </Button>
      </CardContent>
    </Card>
  );
}
