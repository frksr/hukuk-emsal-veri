"use client";
import { useEffect, useState } from "react";
import { BellRing, Plus, Trash2, Loader2, Clock, Mail, Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useConfirm } from "@/components/confirm-dialog";
import { usePlan } from "@/lib/use-plan";
import { AracYukleniyor } from "@/components/arac-yukleniyor";
import { ProUpsell } from "@/components/pro-upsell";
import { ListSkeleton } from "@/components/list-skeleton";

type Alarm = {
  id: string;
  sorgu: string;
  aktif: boolean;
  son_kontrol: string | null;
  son_bildirim: string | null;
  created_at: string;
};

export default function AlarmlarPage() {
  const { loading: planLoading, isLoggedIn, isPaid } = usePlan();
  const [liste, setListe] = useState<Alarm[] | null>(null);
  const [max, setMax] = useState(10);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sorgu, setSorgu] = useState("");
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const { confirm, dialog } = useConfirm();

  async function yukle() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/proxy/alarmlar/", { cache: "no-store" });
      if (!r.ok) throw new Error("Alarmlar yüklenemedi.");
      const j = await r.json();
      const d = j?.data ?? j;
      setListe(d?.alarmlar ?? []);
      setMax(d?.max ?? 10);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!planLoading && isPaid) yukle();
  }, [planLoading, isPaid]);

  async function olustur(e: React.FormEvent) {
    e.preventDefault();
    if (sorgu.trim().length < 3) return;
    setKaydediliyor(true);
    setError(null);
    try {
      const r = await fetch("/api/proxy/alarmlar/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sorgu: sorgu.trim() }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.message || "Alarm oluşturulamadı.");
      setSorgu("");
      await yukle();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setKaydediliyor(false);
    }
  }

  async function toggle(a: Alarm) {
    await fetch(`/api/proxy/alarmlar/${a.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aktif: !a.aktif }),
    });
    await yukle();
  }

  async function sil(id: string) {
    const onay = await confirm("Bu alarm kalıcı olarak silinecek. Devam edilsin mi?", {
      title: "Alarmı sil",
      confirmText: "Sil",
      danger: true,
    });
    if (!onay) return;
    await fetch(`/api/proxy/alarmlar/${id}`, { method: "DELETE" });
    await yukle();
  }

  if (planLoading) return <AracYukleniyor />;

  if (!isPaid) {
    return (
      <ProUpsell
        isLoggedIn={isLoggedIn}
        baslik="Emsal Alarmları"
        aciklama="Takip ettiğiniz konuda yeni emsal karar eklendiğinde e-posta ile ilk siz öğrenin."
        ozellikler={[
          "Sorgu bazlı takip — 'kira tespit davası zamanaşımı' gibi",
          "Yeni karar eklendiğinde otomatik e-posta bildirimi",
          "10 alarma kadar; dilediğiniz an durdurup açabilirsiniz",
        ]}
      />
    );
  }

  const tarih = (iso: string | null) =>
    iso
      ? new Date(iso).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" })
      : "—";

  return (
    <div className="space-y-6">
      {dialog}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BellRing className="h-6 w-6 text-primary" /> Emsal Alarmları
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Takip ettiğiniz konularda veritabanına yeni karar eklendiğinde e-posta ile haber veririz.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Yeni alarm</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={olustur} className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder='Takip edilecek sorgu — örn: "işçilik alacağı faiz başlangıcı"'
                value={sorgu}
                onChange={(e) => setSorgu(e.target.value)}
                maxLength={500}
              />
            </div>
            <Button type="submit" disabled={kaydediliyor || sorgu.trim().length < 3}>
              {kaydediliyor ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <Plus className="h-4 w-4 mr-1.5" />}
              Alarm Kur
            </Button>
          </form>
          <p className="text-xs text-muted-foreground mt-2">
            {(liste?.length ?? 0)}/{max} alarm kullanılıyor.
          </p>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          ⚠️ {error}
        </div>
      )}

      {loading && <ListSkeleton rows={3} />}

      {!loading && liste && liste.length === 0 && (
        <Card><CardContent className="p-8 text-center text-muted-foreground">
          <BellRing className="h-10 w-10 mx-auto mb-3 opacity-30" />
          Henüz alarmınız yok. Yukarıdan takip etmek istediğiniz konuyu yazın.
        </CardContent></Card>
      )}

      {!loading && (liste ?? []).length > 0 && (
        <div className="space-y-2 stagger">
          {(liste ?? []).map((a) => (
            <Card key={a.id} className={`hover-lift ${a.aktif ? "" : "opacity-60"}`}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-semibold truncate flex items-center gap-2">
                      <Search className="h-4 w-4 text-primary shrink-0" />
                      {a.sorgu}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" /> Son kontrol: {tarih(a.son_kontrol)}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Mail className="h-3.5 w-3.5" /> Son bildirim: {tarih(a.son_bildirim)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <Switch checked={a.aktif} onChange={() => toggle(a)} label={a.aktif ? "Aktif" : "Durduruldu"} />
                    <button
                      onClick={() => sil(a.id)}
                      title="Sil"
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
