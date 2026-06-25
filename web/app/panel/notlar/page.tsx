"use client";
import { useEffect, useState } from "react";
import { Loader2, StickyNote, Plus, Trash2, Pencil, Pin, PinOff, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useConfirm } from "@/components/confirm-dialog";
import { TagChip } from "@/components/ui/tag-chip";
import { ListSkeleton } from "@/components/list-skeleton";
import { cn } from "@/lib/utils";

type Not = {
  id: string;
  baslik: string | null;
  icerik: string;
  etiketler: string[];
  pinned: boolean;
  updated_at: string;
};

const BOS = { id: "", baslik: "", icerik: "", etiketler: "", pinned: false };

export default function NotlarPage() {
  const [notlar, setNotlar] = useState<Not[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ ...BOS });
  const [editId, setEditId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { confirm, dialog } = useConfirm();

  async function yukle() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/proxy/notlar/", { cache: "no-store" });
      if (!r.ok) throw new Error("Notlar yüklenemedi.");
      const j = await r.json();
      setNotlar((j?.data ?? j)?.notlar ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { yukle(); }, []);

  function reset() {
    setForm({ ...BOS });
    setEditId(null);
  }

  async function kaydet(e: React.FormEvent) {
    e.preventDefault();
    if (!form.icerik.trim()) return;
    setSaving(true);
    setError(null);
    const body = {
      baslik: form.baslik || null,
      icerik: form.icerik,
      etiketler: form.etiketler.split(",").map((s) => s.trim()).filter(Boolean),
      pinned: form.pinned,
    };
    try {
      const url = editId ? `/api/proxy/notlar/${editId}` : "/api/proxy/notlar/";
      const r = await fetch(url, {
        method: editId ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error("Kaydedilemedi.");
      reset();
      await yukle();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setSaving(false);
    }
  }

  function duzenle(n: Not) {
    setEditId(n.id);
    setForm({
      id: n.id,
      baslik: n.baslik || "",
      icerik: n.icerik,
      etiketler: (n.etiketler || []).join(", "),
      pinned: n.pinned,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function sil(id: string) {
    const onay = await confirm("Bu not kalıcı olarak silinecek. Devam edilsin mi?", {
      title: "Notu sil",
      confirmText: "Sil",
      danger: true,
    });
    if (!onay) return;
    await fetch(`/api/proxy/notlar/${id}`, { method: "DELETE" });
    if (editId === id) reset();
    await yukle();
  }

  async function pinDegistir(n: Not) {
    await fetch(`/api/proxy/notlar/${n.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ baslik: n.baslik, icerik: n.icerik, etiketler: n.etiketler, pinned: !n.pinned }),
    });
    await yukle();
  }

  return (
    <div className="space-y-6">
      {dialog}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <StickyNote className="h-6 w-6 text-primary" /> Notlarım
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Kişisel notlarınız. Dava/konu etiketi ekleyin; ilgili araçta çalışırken size hatırlatma olarak gösterilir.
        </p>
      </div>

      {/* Ekle / düzenle formu */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{editId ? "Notu düzenle" : "Yeni not"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={kaydet} className="space-y-3">
            <Input
              placeholder="Başlık (opsiyonel)"
              value={form.baslik}
              onChange={(e) => setForm({ ...form, baslik: e.target.value })}
            />
            <Textarea
              rows={4}
              placeholder="Notunuz... (örn: 'İcra dosyasında emekli maaşı haczinde Yargıtay 12. HD karşı görüşüne dikkat')"
              value={form.icerik}
              onChange={(e) => setForm({ ...form, icerik: e.target.value })}
            />
            <Input
              placeholder="Etiketler (virgülle): icra, haciz, müvekkil-x"
              value={form.etiketler}
              onChange={(e) => setForm({ ...form, etiketler: e.target.value })}
            />
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.pinned} onChange={(e) => setForm({ ...form, pinned: e.target.checked })} />
                Sabitle (üstte göster)
              </label>
              <div className="flex gap-2">
                {editId && (
                  <Button type="button" variant="ghost" onClick={reset}>
                    <X className="h-4 w-4 mr-1" /> İptal
                  </Button>
                )}
                <Button type="submit" disabled={saving || !form.icerik.trim()}>
                  {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Plus className="h-4 w-4 mr-1" />}
                  {editId ? "Güncelle" : "Ekle"}
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>}

      {loading && <ListSkeleton rows={4} cols={2} />}

      {!loading && notlar && notlar.length === 0 && (
        <Card><CardContent className="p-10 text-center text-muted-foreground">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-secondary">
            <StickyNote className="h-7 w-7 opacity-50" />
          </div>
          <p className="font-medium text-foreground">Henüz notunuz yok</p>
          <p className="mt-1 text-sm">Yukarıdaki formdan ilk notunuzu ekleyin.</p>
        </CardContent></Card>
      )}

      {!loading && notlar && notlar.length > 0 && (
        <div className="grid sm:grid-cols-2 gap-3 stagger">
          {notlar.map((n) => (
            <Card
              key={n.id}
              className={cn(
                "hover-lift",
                n.pinned && "border-primary/40 shadow-sm"
              )}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-semibold">{n.baslik || "Not"}</div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={() => pinDegistir(n)} title={n.pinned ? "Sabiti kaldır" : "Sabitle"} className="text-muted-foreground hover:text-primary">
                      {n.pinned ? <Pin className="h-4 w-4 fill-current" /> : <PinOff className="h-4 w-4" />}
                    </button>
                    <button onClick={() => duzenle(n)} title="Düzenle" className="text-muted-foreground hover:text-foreground">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button onClick={() => sil(n.id)} title="Sil" className="text-muted-foreground hover:text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <p className="text-sm text-foreground/80 mt-1 whitespace-pre-wrap">{n.icerik}</p>
                {n.etiketler?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {n.etiketler.map((t) => (
                      <TagChip key={t} etiket={t} />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
