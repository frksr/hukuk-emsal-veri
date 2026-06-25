"use client";
import { useEffect, useState } from "react";
import { Loader2, Save, Plus, Trash2, SlidersHorizontal, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

type TierMeta = { key: string; label: string };
type ToolMeta = { key: string; label: string };
type LimitMap = Record<string, Record<string, number | null>>;
type Pack = {
  ad: string;
  aciklama: string;
  modul: string | null;
  krediler: Record<string, number>;
  amount: number;
};
type PackMap = Record<string, Pack>;

type ConfigData = {
  tiers: TierMeta[];
  tools: ToolMeta[];
  plan_limits: LimitMap;
  etkin_limitler: LimitMap;
  credit_packs: PackMap;
};

// Editör için limit hücresini string'e çevir ("" = sınırsız).
function limitToStr(v: number | null | undefined): string {
  if (v === null || v === undefined) return "";
  return String(v);
}

export function PaketlerPanel() {
  const [cfg, setCfg] = useState<ConfigData | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingLimits, setSavingLimits] = useState(false);
  const [savingPacks, setSavingPacks] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Düzenlenebilir local state.
  const [limits, setLimits] = useState<Record<string, Record<string, string>>>({});
  const [packs, setPacks] = useState<Array<{ key: string } & Pack>>([]);

  async function load() {
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch("/api/proxy/admin/config");
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Yüklenemedi");
      const d: ConfigData = j.data;
      setCfg(d);
      // Limit grid'i: etkin limitlerle başlat (override yoksa koddan gelen efektif değer).
      const lim: Record<string, Record<string, string>> = {};
      for (const tool of d.tools) {
        lim[tool.key] = {};
        for (const tier of d.tiers) {
          lim[tool.key][tier.key] = limitToStr(d.etkin_limitler?.[tool.key]?.[tier.key]);
        }
      }
      setLimits(lim);
      // Paketleri diziye çevir.
      setPacks(
        Object.entries(d.credit_packs || {}).map(([key, p]) => ({ key, ...p }))
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Hata");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(); /* eslint-disable-next-line */
  }, []);

  function flash(m: string) {
    setMsg(m);
    setTimeout(() => setMsg(null), 3000);
  }

  // ---- Plan limitleri kaydet -------------------------------------------------
  async function saveLimits() {
    if (!cfg) return;
    setSavingLimits(true);
    setErr(null);
    try {
      const body: LimitMap = {};
      for (const tool of cfg.tools) {
        body[tool.key] = {};
        for (const tier of cfg.tiers) {
          const raw = (limits[tool.key]?.[tier.key] ?? "").trim();
          if (raw === "" || raw === "-") {
            body[tool.key][tier.key] = null; // sınırsız
          } else {
            const n = Number(raw);
            body[tool.key][tier.key] = Number.isFinite(n) ? Math.trunc(n) : null;
          }
        }
      }
      const r = await fetch("/api/proxy/admin/config/plan-limits", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Kaydedilemedi");
      flash("Plan limitleri kaydedildi.");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Hata");
    } finally {
      setSavingLimits(false);
    }
  }

  // ---- Ek paketler -----------------------------------------------------------
  function updatePack(idx: number, patch: Partial<{ key: string } & Pack>) {
    setPacks((prev) => prev.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  }
  function updatePackCredit(idx: number, modul: string, val: string) {
    setPacks((prev) =>
      prev.map((p, i) => {
        if (i !== idx) return p;
        const krediler = { ...p.krediler };
        const n = Math.trunc(Number(val));
        if (!val.trim() || !Number.isFinite(n) || n <= 0) {
          delete krediler[modul];
        } else {
          krediler[modul] = n;
        }
        return { ...p, krediler };
      })
    );
  }
  function addCreditRow(idx: number, modul: string) {
    if (!modul) return;
    setPacks((prev) =>
      prev.map((p, i) =>
        i === idx ? { ...p, krediler: { ...p.krediler, [modul]: 1 } } : p
      )
    );
  }
  function addPack() {
    setPacks((prev) => [
      ...prev,
      {
        key: `paket_${prev.length + 1}`,
        ad: "Yeni Paket",
        aciklama: "",
        modul: null,
        krediler: {},
        amount: 0,
      },
    ]);
  }
  function removePack(idx: number) {
    setPacks((prev) => prev.filter((_, i) => i !== idx));
  }

  async function savePacks() {
    if (!cfg) return;
    setSavingPacks(true);
    setErr(null);
    try {
      const body: PackMap = {};
      for (const p of packs) {
        const key = (p.key || "").trim();
        if (!key) continue;
        const krediler: Record<string, number> = {};
        for (const [m, n] of Object.entries(p.krediler || {})) {
          if (n && n > 0) krediler[m] = Math.trunc(n);
        }
        if (Object.keys(krediler).length === 0) continue;
        body[key] = {
          ad: p.ad || key,
          aciklama: p.aciklama || "",
          modul: p.modul || null,
          krediler,
          amount: Number(p.amount) || 0,
        };
      }
      const r = await fetch("/api/proxy/admin/config/credit-packs", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Kaydedilemedi");
      flash("Ek paket kataloğu kaydedildi.");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Hata");
    } finally {
      setSavingPacks(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" /> Yükleniyor…
      </div>
    );
  }
  if (!cfg) {
    return (
      <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-900">
        {err || "Konfigürasyon yüklenemedi."}
      </div>
    );
  }

  const toolKeys = cfg.tools.map((t) => t.key);

  return (
    <div className="space-y-6">
      {msg && (
        <div className="rounded border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
          ✓ {msg}
        </div>
      )}
      {err && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          {err}
        </div>
      )}

      {/* ===== Plan Limitleri ===== */}
      <Card>
        <CardContent className="p-4 space-y-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4" /> Plan Limitleri
            </h2>
            <Button onClick={saveLimits} disabled={savingLimits} size="sm">
              {savingLimits ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
              Kaydet
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Her hücre <strong>aylık</strong> kullanım hakkıdır. Boş ya da &quot;-&quot; bırakırsanız <strong>sınırsız</strong> olur.
            Değişiklik ~30 saniye içinde uygulamaya yansır.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm border-separate border-spacing-0">
              <thead>
                <tr className="text-left">
                  <th className="p-2 sticky left-0 bg-background">Araç</th>
                  {cfg.tiers.map((tier) => (
                    <th key={tier.key} className="p-2 text-xs font-medium text-muted-foreground whitespace-nowrap">
                      {tier.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cfg.tools.map((tool) => (
                  <tr key={tool.key} className="border-t">
                    <td className="p-2 font-medium whitespace-nowrap sticky left-0 bg-background">
                      {tool.label}
                    </td>
                    {cfg.tiers.map((tier) => (
                      <td key={tier.key} className="p-1">
                        <Input
                          type="text"
                          inputMode="numeric"
                          placeholder="∞"
                          value={limits[tool.key]?.[tier.key] ?? ""}
                          onChange={(e) =>
                            setLimits((prev) => ({
                              ...prev,
                              [tool.key]: { ...prev[tool.key], [tier.key]: e.target.value },
                            }))
                          }
                          className="h-8 w-20 text-center text-xs"
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* ===== Ek Paketler ===== */}
      <Card>
        <CardContent className="p-4 space-y-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Package className="h-4 w-4" /> Ek Paketler
            </h2>
            <div className="flex gap-2">
              <Button onClick={addPack} variant="outline" size="sm">
                <Plus className="h-4 w-4 mr-1" /> Paket ekle
              </Button>
              <Button onClick={savePacks} disabled={savingPacks} size="sm">
                {savingPacks ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
                Kaydet
              </Button>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Tüm katalog tek seferde kaydedilir. Kredisi olmayan paketler yok sayılır.
          </p>

          <div className="space-y-4">
            {packs.map((p, idx) => (
              <div key={idx} className="rounded-lg border p-3 space-y-3 bg-muted/20">
                <div className="flex items-start justify-between gap-2">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 flex-1">
                    <label className="text-xs">
                      <span className="text-muted-foreground">Anahtar</span>
                      <Input
                        value={p.key}
                        onChange={(e) => updatePack(idx, { key: e.target.value })}
                        className="h-8 text-xs font-mono"
                      />
                    </label>
                    <label className="text-xs">
                      <span className="text-muted-foreground">Ad</span>
                      <Input
                        value={p.ad}
                        onChange={(e) => updatePack(idx, { ad: e.target.value })}
                        className="h-8 text-xs"
                      />
                    </label>
                    <label className="text-xs sm:col-span-2">
                      <span className="text-muted-foreground">Açıklama</span>
                      <Input
                        value={p.aciklama}
                        onChange={(e) => updatePack(idx, { aciklama: e.target.value })}
                        className="h-8 text-xs"
                      />
                    </label>
                    <label className="text-xs">
                      <span className="text-muted-foreground">Modül (boş = bundle)</span>
                      <select
                        value={p.modul ?? ""}
                        onChange={(e) => updatePack(idx, { modul: e.target.value || null })}
                        className="h-8 w-full text-xs rounded border bg-background px-2"
                      >
                        <option value="">— bundle —</option>
                        {toolKeys.map((tk) => (
                          <option key={tk} value={tk}>{tk}</option>
                        ))}
                      </select>
                    </label>
                    <label className="text-xs">
                      <span className="text-muted-foreground">Fiyat (₺)</span>
                      <Input
                        type="number"
                        step="0.01"
                        value={String(p.amount)}
                        onChange={(e) => updatePack(idx, { amount: Number(e.target.value) || 0 })}
                        className="h-8 text-xs"
                      />
                    </label>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removePack(idx)}
                    title="Paketi sil"
                    className="text-red-600"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>

                {/* Krediler (modül → adet) */}
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Krediler (modül → adet)</div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(p.krediler || {}).map(([modul, adet]) => (
                      <div key={modul} className="flex items-center gap-1 rounded border bg-background px-2 py-1">
                        <span className="text-xs font-mono">{modul}</span>
                        <Input
                          type="number"
                          value={String(adet)}
                          onChange={(e) => updatePackCredit(idx, modul, e.target.value)}
                          className="h-6 w-16 text-center text-xs"
                        />
                      </div>
                    ))}
                    <select
                      value=""
                      onChange={(e) => { addCreditRow(idx, e.target.value); e.currentTarget.value = ""; }}
                      className="h-8 text-xs rounded border bg-background px-2"
                    >
                      <option value="">+ modül ekle</option>
                      {toolKeys
                        .filter((tk) => !(tk in (p.krediler || {})))
                        .map((tk) => (
                          <option key={tk} value={tk}>{tk}</option>
                        ))}
                    </select>
                  </div>
                </div>
              </div>
            ))}
            {packs.length === 0 && (
              <div className="text-center text-sm text-muted-foreground py-6">
                Henüz paket yok. &quot;Paket ekle&quot; ile başlayın.
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
