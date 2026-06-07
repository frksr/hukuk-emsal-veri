"use client";
import { useState } from "react";
import { Loader2, Timer, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { zamanasimiHesapla } from "@/lib/api";

const KATEGORILER: Record<string, { label: string; altTipler: { value: string; label: string }[] }> = {
  alacak: {
    label: "Alacak",
    altTipler: [
      { value: "genel", label: "Genel alacak (10 yıl - TBK 146)" },
      { value: "kira", label: "Kira (5 yıl - TBK 147/1)" },
      { value: "ucret", label: "Ücret (5 yıl - TBK 147/3)" },
      { value: "isci_ucreti", label: "İşçi ücreti (5 yıl - İş K 32)" },
      { value: "kambiyo_senedi", label: "Kambiyo senedi (3 yıl - TTK 778)" },
      { value: "cek", label: "Çek (3 yıl - TTK 814)" },
    ],
  },
  vergi: {
    label: "Vergi",
    altTipler: [
      { value: "amme_alacagi", label: "Amme alacağı (5 yıl - AATUHK 102)" },
      { value: "vergi_alacagi", label: "Vergi alacağı (5 yıl - VUK 114)" },
    ],
  },
  haksiz_fiil: {
    label: "Haksız Fiil",
    altTipler: [
      { value: "maddi", label: "Maddi (2/10 yıl - TBK 72)" },
      { value: "manevi", label: "Manevi (2/10 yıl - TBK 72)" },
    ],
  },
  ticari: { label: "Ticari", altTipler: [{ value: "sirket_borc", label: "Şirket borcu (10 yıl - TBK 146)" }] },
  is_kazasi: { label: "İş Kazası", altTipler: [{ value: "tazminat", label: "Tazminat (10 yıl - TBK 146)" }] },
  haksiz_iktisap: { label: "Sebepsiz Zenginleşme", altTipler: [{ value: "genel", label: "Genel (2/10 yıl - TBK 82)" }] },
  kira: { label: "Kira", altTipler: [{ value: "tahliye", label: "Tahliye davası (1 yıl - TBK 339)" }] },
  icra: { label: "İcra", altTipler: [{ value: "ilamsiz_takip", label: "İlamsız takip (10 yıl - İİK 39)" }, { value: "ilamli_takip", label: "İlamlı takip (10 yıl - İİK 39)" }] },
  nafaka: { label: "Nafaka", altTipler: [{ value: "yardim", label: "Yardım nafakası (5 yıl - TBK 147/4)" }] },
  aile: { label: "Aile", altTipler: [{ value: "bosanma", label: "Boşanma tazminatı (10 yıl - TMK 178)" }] },
};

export function ZamanasimiForm() {
  const [kategori, setKategori] = useState("alacak");
  const [altTip, setAltTip] = useState("genel");
  const [olayTarihi, setOlayTarihi] = useState(new Date().toISOString().slice(0, 10));
  const [kesilmeler, setKesilmeler] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [sonuc, setSonuc] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const altTipler = KATEGORILER[kategori]?.altTipler || [];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setError(null);
    try {
      const data = await zamanasimiHesapla({
        kategori, alt_tip: altTip, olay_tarihi: olayTarihi,
        kesilme_tarihleri: kesilmeler.filter(Boolean),
      });
      setSonuc(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  const durumRengi = (durum: string) => {
    if (durum === "asıldı") return "bg-destructive text-destructive-foreground";
    if (durum === "kritik") return "bg-red-100 text-red-900 border-red-300";
    if (durum === "yaklasan") return "bg-amber-100 text-amber-900 border-amber-300";
    return "bg-emerald-100 text-emerald-900 border-emerald-300";
  };

  return (
    <div className="grid lg:grid-cols-5 gap-6">
      <Card className="lg:col-span-2 h-fit">
        <CardHeader><CardTitle>Dava Bilgileri</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Kategori</label>
              <select value={kategori} onChange={(e) => { setKategori(e.target.value); setAltTip(KATEGORILER[e.target.value].altTipler[0].value); }}
                className="w-full h-10 rounded-md border bg-background px-3 text-sm">
                {Object.entries(KATEGORILER).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Alt Tür</label>
              <select value={altTip} onChange={(e) => setAltTip(e.target.value)}
                className="w-full h-10 rounded-md border bg-background px-3 text-sm">
                {altTipler.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Olay Tarihi</label>
              <Input type="date" value={olayTarihi} onChange={(e) => setOlayTarihi(e.target.value)} />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium">Kesilme Tarihleri (opsiyonel)</label>
                <Button type="button" variant="outline" size="sm" onClick={() => setKesilmeler([...kesilmeler, ""])}>
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              {kesilmeler.map((d, i) => (
                <div key={i} className="flex gap-2 mb-2">
                  <Input type="date" value={d} onChange={(e) => {
                    const arr = [...kesilmeler]; arr[i] = e.target.value; setKesilmeler(arr);
                  }} />
                  <Button type="button" variant="ghost" size="icon" onClick={() => setKesilmeler(kesilmeler.filter((_, j) => j !== i))}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Timer className="mr-2 h-4 w-4" />}
              Hesapla
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="lg:col-span-3 space-y-4">
        {error && <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>}
        {sonuc && (
          <>
            <Card className={`border-2 ${durumRengi(sonuc.durum)}`}>
              <CardContent className="p-6 text-center">
                <div className="text-sm uppercase tracking-wider">{sonuc.durum?.toUpperCase()}</div>
                <div className="text-5xl font-bold my-3">{sonuc.kalan_gun ?? "—"}</div>
                <div className="text-sm">gün kaldı</div>
              </CardContent>
            </Card>
            <div className="grid grid-cols-2 gap-3">
              <Card><CardContent className="p-4">
                <div className="text-xs text-muted-foreground">Yasal Süre</div>
                <div className="text-lg font-bold">{sonuc.zamanasimi_yil} yıl</div>
              </CardContent></Card>
              <Card><CardContent className="p-4">
                <div className="text-xs text-muted-foreground">Bitiş Tarihi</div>
                <div className="text-lg font-bold">{sonuc.bitis_tarihi}</div>
              </CardContent></Card>
            </div>
            <Card>
              <CardHeader><CardTitle className="text-base">{sonuc.kanun}</CardTitle></CardHeader>
              <CardContent className="text-sm text-muted-foreground">{sonuc.aciklama}</CardContent>
            </Card>
            {sonuc.uyarilar?.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm space-y-2">
                {sonuc.uyarilar.map((u: string, i: number) => <div key={i}>⚠️ {u}</div>)}
              </div>
            )}
            {(sonuc.durum === "yaklasan" || sonuc.durum === "kritik") && (
              <Card className="bg-primary text-primary-foreground">
                <CardContent className="p-5">
                  <div className="font-semibold mb-2">Sonraki Adım</div>
                  <p className="text-sm opacity-90 mb-3">Zamanaşımını kesmek için ihtarname göndermeniz önerilir.</p>
                  <Button asChild variant="accent"><a href="/ihtarname">İhtarname Üret →</a></Button>
                </CardContent>
              </Card>
            )}
          </>
        )}
        {!sonuc && !loading && !error && (
          <Card><CardContent className="p-8 text-center text-muted-foreground">
            <Timer className="h-12 w-12 mx-auto mb-3 opacity-30" />
            Dava bilgilerini girin, hesap burada görünecek.
          </CardContent></Card>
        )}
      </div>
    </div>
  );
}
