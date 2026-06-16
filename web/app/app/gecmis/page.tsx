"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Loader2, FileText, Mail, Scale, FileSearch, Swords, FileCheck,
  Copy, ChevronDown, ChevronUp, History, Search, Calculator, Clock,
  Trash2, ShieldCheck, EyeOff,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/confirm-dialog";
import { ListSkeleton } from "@/components/list-skeleton";

type Uretim = {
  id: string;
  tool: string;
  alt_tur: string | null;
  baslik: string | null;
  girdi_ozeti: string | null;
  cikti: string | null;
  created_at: string;
};

const TOOL_META: Record<string, { label: string; icon: typeof FileText }> = {
  arama: { label: "Emsal Arama", icon: Search },
  faiz: { label: "Faiz & Tahsilat", icon: Calculator },
  zamanasimi: { label: "Zamanaşımı", icon: Clock },
  dilekce: { label: "Dilekçe", icon: FileText },
  ihtarname: { label: "İhtarname", icon: Mail },
  ozet: { label: "Karar Özeti", icon: Scale },
  denetim: { label: "Belge Denetimi", icon: FileSearch },
  karsi_argument: { label: "Karşı Argüman", icon: Swords },
  sozlesme: { label: "Sözleşme Analizi", icon: FileCheck },
};

const FILTRELER: Array<[string, string]> = [
  ["", "Tümü"],
  ["arama", "Emsal Arama"],
  ["faiz", "Faiz & Tahsilat"],
  ["zamanasimi", "Zamanaşımı"],
  ["dilekce", "Dilekçe"],
  ["ihtarname", "İhtarname"],
  ["ozet", "Karar Özeti"],
  ["denetim", "Belge Denetimi"],
  ["karsi_argument", "Karşı Argüman"],
  ["sozlesme", "Sözleşme Analizi"],
];

export default function GecmisPage() {
  const [items, setItems] = useState<Uretim[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtre, setFiltre] = useState("");
  const [acik, setAcik] = useState<Set<string>>(new Set());
  const [kopyalandi, setKopyalandi] = useState<string | null>(null);
  const [siliniyor, setSiliniyor] = useState(false);
  const [historyEnabled, setHistoryEnabled] = useState<boolean | null>(null);
  const [prefKaydediliyor, setPrefKaydediliyor] = useState(false);
  const { confirm, dialog } = useConfirm();

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch("/api/proxy/me", { cache: "no-store" });
        if (!r.ok) return;
        const j = await r.json();
        const user = (j?.data ?? j)?.user;
        if (alive && user) setHistoryEnabled(user.history_enabled !== false);
      } catch {
        /* tercih okunamazsa toggle gizli kalır */
      }
    })();
    return () => { alive = false; };
  }, []);

  const tercihDegistir = async (yeni: boolean) => {
    const onceki = historyEnabled;
    setHistoryEnabled(yeni); // iyimser güncelleme
    setPrefKaydediliyor(true);
    try {
      const r = await fetch("/api/proxy/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ history_enabled: yeni }),
      });
      if (!r.ok) throw new Error();
    } catch {
      setHistoryEnabled(onceki); // geri al
      setError("Tercih kaydedilemedi. Lütfen tekrar deneyin.");
    } finally {
      setPrefKaydediliyor(false);
    }
  };

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const qs = filtre ? `?tool=${encodeURIComponent(filtre)}` : "";
        const r = await fetch(`/api/proxy/me/uretimler${qs}`, { cache: "no-store" });
        if (!r.ok) throw new Error("Geçmiş yüklenemedi.");
        const j = await r.json();
        const data = (j?.data ?? j)?.uretimler ?? [];
        if (alive) setItems(data);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : "Hata");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [filtre]);

  const toggle = (id: string) => {
    const s = new Set(acik);
    s.has(id) ? s.delete(id) : s.add(id);
    setAcik(s);
  };
  const kopyala = (id: string, metin: string) => {
    navigator.clipboard.writeText(metin);
    setKopyalandi(id);
    setTimeout(() => setKopyalandi((v) => (v === id ? null : v)), 1500);
  };
  const tarih = (s: string) =>
    new Date(s).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });

  const sil = async (id: string) => {
    if (!(await confirm("Bu kayıt geçmişinizden silinsin mi?", { danger: true, title: "Kaydı sil", confirmText: "Sil" }))) return;
    try {
      const r = await fetch(`/api/proxy/me/uretimler/${id}`, { method: "DELETE" });
      if (!r.ok) throw new Error();
      setItems((prev) => (prev ? prev.filter((x) => x.id !== id) : prev));
    } catch {
      setError("Kayıt silinemedi.");
    }
  };

  const temizle = async () => {
    const etiket = filtre ? (FILTRELER.find(([v]) => v === filtre)?.[1] ?? filtre) : null;
    const mesaj = etiket
      ? `"${etiket}" kategorisindeki tüm geçmişiniz silinecek. Bu işlem geri alınamaz.`
      : "Tüm geçmişiniz (aramalar, hesaplamalar ve üretimler) silinecek. Bu işlem geri alınamaz.";
    if (!(await confirm(mesaj, { danger: true, title: "Geçmişi temizle", confirmText: "Temizle" }))) return;
    setSiliniyor(true);
    try {
      const qs = filtre ? `?tool=${encodeURIComponent(filtre)}` : "";
      const r = await fetch(`/api/proxy/me/uretimler${qs}`, { method: "DELETE" });
      if (!r.ok) throw new Error();
      setItems([]);
    } catch {
      setError("Geçmiş temizlenemedi.");
    } finally {
      setSiliniyor(false);
    }
  };

  return (
    <div className="space-y-6">
      {dialog}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <History className="h-6 w-6 text-primary" /> Geçmişim
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Aramalar, faiz/zamanaşımı hesaplamaları ve ürettiğiniz tüm belgeler burada. Yalnızca siz görürsünüz.
          </p>
        </div>
        {items && items.length > 0 && (
          <Button variant="outline" size="sm" onClick={temizle} disabled={siliniyor}
                  className="text-destructive hover:bg-destructive/10">
            {siliniyor ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            <span className="ml-1.5">{filtre ? "Bu kategoriyi temizle" : "Tümünü temizle"}</span>
          </Button>
        )}
      </div>

      {historyEnabled !== null && (
        <div
          className={`rounded-xl border p-4 transition-colors ${
            historyEnabled
              ? "border-primary/30 bg-primary/5"
              : "border-amber-500/40 bg-amber-500/5"
          }`}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div
                className={`mt-0.5 rounded-md p-2 ${
                  historyEnabled
                    ? "bg-primary/10 text-primary"
                    : "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                }`}
              >
                {historyEnabled ? <ShieldCheck className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold leading-tight">
                  Geçmişi tut
                </p>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Geçmişinizi açık tutarsanız aramalarınıza ve ürettiğiniz belgelere tekrar
                  ulaşır, çalışmanızı kolaylaştırır ve size daha iyi yardımcı olabiliriz.
                  İstediğiniz an kapatabilir veya geçmişinizi silebilirsiniz.
                </p>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={historyEnabled}
              aria-label="Geçmişi tut"
              disabled={prefKaydediliyor}
              onClick={() => tercihDegistir(!historyEnabled)}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background disabled:opacity-60 ${
                historyEnabled ? "bg-primary" : "bg-muted-foreground/30"
              }`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-background shadow transition-transform ${
                  historyEnabled ? "translate-x-5" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>
          {!historyEnabled && (
            <p className="mt-3 text-xs font-medium text-amber-700 dark:text-amber-400">
              Geçmiş tutma kapalı — yeni kullanımlar kaydedilmiyor. Eski kayıtlarınız aşağıda durmaya devam eder.
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {FILTRELER.map(([v, l]) => (
          <button
            key={v}
            onClick={() => setFiltre(v)}
            className={`rounded-full px-3 py-1.5 text-sm border transition ${
              filtre === v ? "bg-primary text-primary-foreground border-primary" : "hover:bg-secondary"
            }`}
          >
            {l}
          </button>
        ))}
      </div>

      {loading && <ListSkeleton rows={5} />}

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>
      )}

      {!loading && !error && items && items.length === 0 && (
        <Card><CardContent className="p-10 text-center text-muted-foreground">
          <History className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>Henüz bir üretiminiz yok.</p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Button asChild size="sm" variant="outline"><Link href="/dilekce">Dilekçe üret</Link></Button>
            <Button asChild size="sm" variant="outline"><Link href="/ihtarname">İhtarname üret</Link></Button>
            <Button asChild size="sm" variant="outline"><Link href="/emsal-arama">Emsal ara</Link></Button>
          </div>
        </CardContent></Card>
      )}

      {!loading && items && items.length > 0 && (
        <div className="space-y-3 stagger">
          {items.map((it) => {
            const meta = TOOL_META[it.tool] ?? { label: it.tool, icon: FileText };
            const Icon = meta.icon;
            const open = acik.has(it.id);
            return (
              <Card key={it.id} className="hover-lift">
                <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 rounded-md bg-primary/10 p-2 text-primary"><Icon className="h-4 w-4" /></div>
                    <div>
                      <CardTitle className="text-base">{it.baslik || meta.label}</CardTitle>
                      <div className="text-xs text-muted-foreground mt-1">
                        <span className="rounded-full bg-secondary px-2 py-0.5">{meta.label}</span>
                        {" · "}{tarih(it.created_at)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {it.cikti && (
                      <>
                        <Button size="sm" variant="ghost" onClick={() => kopyala(it.id, it.cikti!)} title="Kopyala">
                          <Copy className="h-4 w-4" />
                          {kopyalandi === it.id && <span className="ml-1 text-xs">Kopyalandı</span>}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => toggle(it.id)}>
                          {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </Button>
                      </>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => sil(it.id)} title="Sil"
                            className="text-muted-foreground hover:text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                {open && it.cikti && (
                  <CardContent>
                    {it.girdi_ozeti && (
                      <p className="text-xs text-muted-foreground mb-2 italic line-clamp-2">Girdi: {it.girdi_ozeti}</p>
                    )}
                    <pre className="whitespace-pre-wrap font-mono text-xs bg-muted/40 rounded-md p-3 max-h-96 overflow-auto">{it.cikti}</pre>
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
