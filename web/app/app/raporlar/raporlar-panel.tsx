"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { BarChart3, Receipt, FileText, Mail, Scale, FileSearch, Swords, FileCheck, Search, Shield, Calculator, Clock, Package, CreditCard } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { CountUp } from "@/components/count-up";

type Arac = {
  tool: string; toplam: number; son30: number; son7: number; kredi?: number;
  sinirsiz?: boolean; plan_kalan?: number | null; kalan_toplam?: number | null; gunluk_limit?: number;
};
type Rapor = {
  tier: string;
  uretim_toplam: number;
  arama_toplam: number;
  toplam_kullanim: number;
  araclar: Arac[];
  krediler?: Record<string, number>;
};
type Payment = {
  id: string; amount_try: number; currency: string; status: string;
  paid_at: string | null; invoice_number: string | null; invoice_pdf_url: string | null;
};
type AddonOrder = {
  id: string; pack_key: string; ad: string; amount_try: number;
  currency: string; status: string; created_at: string;
};
// Birleşik ödeme işlemi (abonelik + ek paket)
type Odeme = {
  id: string; tip: "abonelik" | "ek_paket"; baslik: string; tarih: string | null;
  tutar: number; currency: string; durum: string; pdf?: string | null;
};

const TOOL_META: Record<string, { label: string; icon: typeof FileText; href: string }> = {
  arama: { label: "Emsal Arama", icon: Search, href: "/emsal-arama" },
  dilekce: { label: "Dilekçe", icon: FileText, href: "/dilekce" },
  ihtarname: { label: "İhtarname", icon: Mail, href: "/ihtarname" },
  ozet: { label: "Karar Özeti", icon: Scale, href: "/karar-ozet" },
  denetim: { label: "Belge Denetimi", icon: FileSearch, href: "/belge-denetim" },
  karsi_argument: { label: "Karşı Argüman", icon: Swords, href: "/karsi-argument" },
  sozlesme: { label: "Sözleşme Analizi", icon: FileCheck, href: "/sozlesme-analizi" },
  kvkk: { label: "KVKK Checklist", icon: Shield, href: "/kvkk" },
  faiz: { label: "Faiz Hesaplama", icon: Calculator, href: "/faiz-hesaplayici" },
  zamanasimi: { label: "Zamanaşımı", icon: Clock, href: "/zamanasimi" },
};

export function RaporlarPanel() {
  const [rapor, setRapor] = useState<Rapor | null>(null);
  const [odemeler, setOdemeler] = useState<Odeme[]>([]);
  const [loading, setLoading] = useState(true);

  async function yukle() {
    try {
      const [rR, pR, oR] = await Promise.all([
        fetch("/api/proxy/me/rapor", { cache: "no-store" }),
        fetch("/api/proxy/billing/invoices", { cache: "no-store" }).catch(() => null),
        fetch("/api/proxy/billing/addons/orders", { cache: "no-store" }).catch(() => null),
      ]);
      if (rR.ok) setRapor((await rR.json())?.data ?? null);

      const liste: Odeme[] = [];
      if (pR && pR.ok) {
        const payments: Payment[] = (await pR.json())?.data?.payments || [];
        for (const p of payments) {
          liste.push({
            id: p.id, tip: "abonelik",
            baslik: p.invoice_number ? `Abonelik · ${p.invoice_number}` : "Abonelik ödemesi",
            tarih: p.paid_at, tutar: p.amount_try, currency: p.currency || "TRY",
            durum: p.status, pdf: p.invoice_pdf_url,
          });
        }
      }
      if (oR && oR.ok) {
        const orders: AddonOrder[] = (await oR.json())?.data?.orders || [];
        for (const o of orders) {
          liste.push({
            id: o.id, tip: "ek_paket", baslik: o.ad,
            tarih: o.created_at, tutar: o.amount_try, currency: o.currency || "TRY",
            durum: o.status,
          });
        }
      }
      liste.sort((a, b) => (new Date(b.tarih ?? 0).getTime()) - (new Date(a.tarih ?? 0).getTime()));
      setOdemeler(liste);
    } catch {
      /* sessiz */
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { yukle(); }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid sm:grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-[76px]" />)}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const araclar = rapor?.araclar ?? [];
  const maxToplam = Math.max(1, ...araclar.map((a) => a.toplam));

  return (
    <div className="space-y-6">
      {/* Özet kartlar */}
      <div className="grid sm:grid-cols-3 gap-3 stagger">
        <Card className="hover-lift"><CardContent className="p-4">
          <div className="text-xs text-muted-foreground">Toplam İşlem</div>
          <div className="text-3xl font-bold tabular-nums"><CountUp value={rapor?.toplam_kullanim ?? 0} /></div>
        </CardContent></Card>
        <Card className="hover-lift"><CardContent className="p-4">
          <div className="text-xs text-muted-foreground">Üretim (dilekçe/ihtarname/özet…)</div>
          <div className="text-3xl font-bold tabular-nums"><CountUp value={rapor?.uretim_toplam ?? 0} /></div>
        </CardContent></Card>
        <Card className="hover-lift"><CardContent className="p-4">
          <div className="text-xs text-muted-foreground">Emsal Arama</div>
          <div className="text-3xl font-bold tabular-nums"><CountUp value={rapor?.arama_toplam ?? 0} /></div>
        </CardContent></Card>
      </div>

      {/* Araç bazlı kullanım — dinamik */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><BarChart3 className="h-5 w-5" /> Araç Kullanımı</CardTitle>
          <CardDescription>Bir özelliği kullandığınızda anında buraya yansır. Plan: <strong>{rapor?.tier || "?"}</strong></CardDescription>
        </CardHeader>
        <CardContent>
          {araclar.every((a) => a.toplam === 0) ? (
            <p className="text-sm text-muted-foreground">
              Henüz kullanım yok. <Link href="/emsal-arama" className="text-primary underline">Bir araç deneyin</Link>.
            </p>
          ) : (
            <div className="space-y-3">
              {araclar.map((a) => {
                const meta = TOOL_META[a.tool] ?? { label: a.tool, icon: FileText, href: "#" };
                const Icon = meta.icon;
                return (
                  <div key={a.tool}>
                    <div className="flex items-center justify-between gap-2 text-sm mb-1">
                      <div className="flex items-center gap-2 min-w-0">
                        <Link href={meta.href} className="flex items-center gap-2 hover:underline">
                          <Icon className="h-4 w-4 text-primary" /> {meta.label}
                        </Link>
                        {(() => {
                          // Aylık plan hakkı (her ay yenilenir) ile süresiz ek-paket
                          // kredisi AYRI gösterilir — tek bir toplamda birleştirmek
                          // yanıltıcı olurdu (aylık hak ≠ kalıcı kredi).
                          const limit = a.gunluk_limit ?? 0;
                          const planKalan = a.plan_kalan ?? 0;
                          const kredi = a.kredi ?? 0;
                          const baseCls = "text-[10px] rounded-full border px-2 py-0.5 whitespace-nowrap shrink-0";
                          if (a.sinirsiz) {
                            return <span className={`${baseCls} bg-secondary/60 text-muted-foreground`}>Sınırsız</span>;
                          }
                          if (limit === 0 && kredi === 0) {
                            return (
                              <span title="Bu araç ücretsiz planına dahil değil — Pro veya ek paket gerekir."
                                    className={`${baseCls} uppercase tracking-wider border-amber-400/40 bg-amber-400/20 text-amber-700 dark:text-amber-300`}>
                                PRO
                              </span>
                            );
                          }
                          const kullanilabilir = planKalan > 0 || kredi > 0;
                          const renk = kullanilabilir
                            ? "border-emerald-400/30 bg-emerald-400/15 text-emerald-700 dark:text-emerald-300"
                            : "border-amber-400/30 bg-amber-400/15 text-amber-700 dark:text-amber-300";
                          return (
                            <span
                              title="Aylık plan hakkı her ay yenilenir; ek paket kredileri süresizdir."
                              className={`${baseCls} ${renk}`}
                            >
                              Bu ay: {planKalan}/{limit}
                              {kredi > 0 ? ` · ${kredi} kredi` : ""}
                            </span>
                          );
                        })()}
                      </div>
                      <span className="text-muted-foreground text-xs whitespace-nowrap">
                        Toplam <strong className="text-foreground">{a.toplam}</strong> · 30g {a.son30} · 7g {a.son7}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                      <div className="h-full bg-primary transition-all" style={{ width: `${Math.round((a.toplam / maxToplam) * 100)}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Ödeme işlemleri — abonelik + ek paket alımları birlikte */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Receipt className="h-5 w-5" /> Ödeme İşlemleri</CardTitle>
          <CardDescription>Abonelik ve ek paket alımlarınız.</CardDescription>
        </CardHeader>
        <CardContent>
          {odemeler.length === 0 ? (
            <p className="text-sm text-muted-foreground">Henüz ödeme kaydı yok.</p>
          ) : (
            <div className="space-y-2">
              {odemeler.map((o) => (
                <div key={o.id} className="flex items-center gap-3 rounded-lg border p-3">
                  <div className={`rounded-md p-2 shrink-0 ${o.tip === "ek_paket" ? "bg-primary/10 text-primary" : "bg-accent/15 text-accent"}`}>
                    {o.tip === "ek_paket" ? <Package className="h-4 w-4" /> : <CreditCard className="h-4 w-4" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">{o.baslik}</div>
                    <div className="text-xs text-muted-foreground">
                      {o.tip === "ek_paket" ? "Ek paket" : "Abonelik"}
                      {" · "}
                      {o.tarih ? new Date(o.tarih).toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" }) : "—"}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="font-semibold">
                      {new Intl.NumberFormat("tr-TR", { style: "currency", currency: o.currency }).format(o.tutar)}
                    </div>
                    <span className={`inline-block mt-0.5 text-[10px] px-2 py-0.5 rounded-full ${
                      o.durum === "success" || o.durum === "paid"
                        ? "bg-emerald-400/15 text-emerald-700 dark:text-emerald-300 border border-emerald-400/30"
                        : o.durum === "pending"
                        ? "bg-amber-400/15 text-amber-700 dark:text-amber-300 border border-amber-400/30"
                        : "bg-destructive/10 text-destructive border border-destructive/30"
                    }`}>
                      {o.durum === "success" || o.durum === "paid" ? "Başarılı"
                        : o.durum === "pending" ? "Beklemede"
                        : o.durum === "failed" ? "Başarısız" : o.durum}
                    </span>
                  </div>
                  {o.pdf && (
                    <a href={o.pdf} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline text-xs shrink-0">PDF</a>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
