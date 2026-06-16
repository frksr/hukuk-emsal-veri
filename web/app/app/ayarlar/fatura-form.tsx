"use client";
import { useEffect, useState } from "react";
import { Loader2, Save, Receipt } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

type Fatura = {
  unvan: string; vergi_no: string; vergi_dairesi: string;
  adres: string; sehir: string; posta: string; telefon: string;
};
const BOS: Fatura = { unvan: "", vergi_no: "", vergi_dairesi: "", adres: "", sehir: "", posta: "", telefon: "" };

export function FaturaForm() {
  const [f, setF] = useState<Fatura>(BOS);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/proxy/me", { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => {
        const b = j?.data?.user?.billing;
        if (b && typeof b === "object") setF({ ...BOS, ...b });
      })
      .catch(() => {});
  }, []);

  const set = (k: keyof Fatura, v: string) => setF((s) => ({ ...s, [k]: v }));

  async function kaydet(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setSuccess(null); setError(null);
    try {
      const r = await fetch("/api/proxy/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ billing: f }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Kaydedilemedi");
      setSuccess("Fatura bilgileri kaydedildi.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Receipt className="h-5 w-5 text-primary" /> Fatura Bilgileri</CardTitle>
        <CardDescription>
          Bir kez kaydedin; abonelik ve ek paket ödemelerinde otomatik kullanılır. (Şahıs iseniz unvan yerine ad-soyad, vergi no yerine TC girebilirsiniz.)
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={kaydet} className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Unvan / Şirket adı</label>
              <Input value={f.unvan} onChange={(e) => set("unvan", e.target.value)} placeholder="Örn: Demir Hukuk Bürosu" />
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Vergi No / TC</label>
              <Input value={f.vergi_no} onChange={(e) => set("vergi_no", e.target.value)} inputMode="numeric" placeholder="Vergi no veya TC" />
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Vergi Dairesi <span className="text-muted-foreground/60">(opsiyonel)</span></label>
              <Input value={f.vergi_dairesi} onChange={(e) => set("vergi_dairesi", e.target.value)} />
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Telefon <span className="text-muted-foreground/60">(opsiyonel)</span></label>
              <Input value={f.telefon} onChange={(e) => set("telefon", e.target.value)} inputMode="tel" placeholder="05XXXXXXXXX" />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-1.5 block">Fatura adresi</label>
            <Input value={f.adres} onChange={(e) => set("adres", e.target.value)} placeholder="Mahalle, cadde, no" />
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Şehir</label>
              <Input value={f.sehir} onChange={(e) => set("sehir", e.target.value)} placeholder="İstanbul" />
            </div>
            <div>
              <label className="text-sm font-medium mb-1.5 block">Posta kodu <span className="text-muted-foreground/60">(opsiyonel)</span></label>
              <Input value={f.posta} onChange={(e) => set("posta", e.target.value)} inputMode="numeric" placeholder="34000" />
            </div>
          </div>

          {success && <div className="rounded border border-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 p-3 text-sm text-emerald-900 dark:text-emerald-300">✓ {success}</div>}
          {error && <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">⚠ {error}</div>}

          <Button type="submit" disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Fatura bilgilerini kaydet
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
