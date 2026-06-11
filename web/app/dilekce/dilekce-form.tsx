"use client";
import { useEffect, useState } from "react";
import { Loader2, Download, Copy, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { dilekceCagir, dilekceStream, exportBelge, type DilekceSonuc } from "@/lib/api";

const TURLER = [
  { value: "itirazin_iptali", label: "İtirazın İptali (İİK 67)" },
  { value: "ihalenin_feshi", label: "İhalenin Feshi (İİK 134)" },
  { value: "menfi_tespit", label: "Menfi Tespit (İİK 72)" },
  { value: "tahsilat", label: "Tahsilat Davası" },
  { value: "genel", label: "Genel Hukuk Davası" },
];

export function DilekceForm() {
  const [durum, setDurum] = useState("");
  const [tur, setTur] = useState("itirazin_iptali");
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!durum.trim()) return;
    setLoading(true);
    setError(null);
    setSonuc(null);

    const params = {
      durum,
      dilekce_turu: tur,
      taraflar: { alacakli, borclu },
      k: 5,
    };

    // 1) Streaming dene — metin token-token akar, emsaller anında görünür.
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
      if (metin) {
        setLoading(false);
        return;
      }
      // metin boş geldiyse (eski backend vs.) klasik endpoint'e düş
    } catch {
      // stream desteklenmiyor/koptu — klasik endpoint'e düş
    }

    // 2) Fallback: klasik tek-yanıt endpoint
    try {
      const data = await dilekceCagir(params);
      setSonuc(data as unknown as DilekceSonuc);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata oluştu.");
      setSonuc(null);
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
      await exportBelge(format, {
        metin: sonuc.dilekce_metni,
        dosya_adi: `dilekce-${tur}`,
      });
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
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Dilekçe Türü</label>
              <select
                value={tur} onChange={(e) => setTur(e.target.value)}
                className="w-full h-10 rounded-md border bg-background px-3 text-sm"
              >
                {TURLER.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
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
                value={durum} onChange={(e) => setDurum(e.target.value)} rows={10}
                placeholder="Örn: Müvekkilim, davalıya 50.000 TL borç verdi. Senet vade tarihinde ödenmedi. İcra takibi başlatıldı ancak davalı borca itiraz etti..."
              />
            </div>
            <Button type="submit" disabled={loading || !durum.trim()} className="w-full" size="lg">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileText className="mr-2 h-4 w-4" />}
              Dilekçe Üret
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="lg:col-span-3 space-y-4">
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            ⚠️ {error}
          </div>
        )}
        {loading && !sonuc && (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin mx-auto mb-3" />
              <p>Emsal kararlar bulunuyor, dilekçe üretiliyor...</p>
            </CardContent>
          </Card>
        )}
        {loading && sonuc && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Dilekçe yazılıyor...</span>
          </div>
        )}
        {!loading && !sonuc && !error && (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p>Form bilgilerini doldurun, dilekçeniz burada görünecek.</p>
            </CardContent>
          </Card>
        )}
        {sonuc && (
          <>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle>Dilekçe Taslağı</CardTitle>
                <div className="flex gap-2">
                  <Button onClick={copyDilekce} variant="outline" size="sm" title="Panoya kopyala"><Copy className="h-4 w-4" /></Button>
                  <Button onClick={() => downloadAs("docx")} variant="outline" size="sm" title="Word olarak indir">
                    <Download className="h-4 w-4 mr-1" /> Word
                  </Button>
                  <Button onClick={() => downloadAs("udf")} variant="outline" size="sm" title="UYAP belgesi olarak indir">
                    <Download className="h-4 w-4 mr-1" /> UYAP
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={sonuc.dilekce_metni} readOnly rows={20}
                  className="font-mono text-sm"
                />
              </CardContent>
            </Card>
            {sonuc.kullanilan_emsaller?.length > 0 && (
              <Card>
                <CardHeader><CardTitle>Kullanılan Emsal Kararlar</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {sonuc.kullanilan_emsaller.map((em, i) => (
                    <div key={i} className="text-sm border-l-4 border-accent pl-3">
                      <div className="font-semibold">{em.atif_text}</div>
                      <div className="text-muted-foreground text-xs mt-1">{em.ilgili_bolum}</div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}
