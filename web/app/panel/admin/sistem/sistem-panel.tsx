"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Activity, Database, Sparkles, Search, CreditCard, Mail, Bell, RefreshCw,
  CheckCircle2, XCircle, AlertTriangle, Loader2, Receipt, Webhook, ShieldAlert, Package,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Health = {
  checked_at: string;
  db: { ok: boolean; latency_ms: number | null; error: string | null };
  llm: { available?: boolean; default?: string; [k: string]: unknown };
  rag: { available?: boolean; chunk_count?: number; [k: string]: unknown };
  iyzico: { configured: boolean };
  mail: { configured: boolean };
  reminders: { pending: number | null; overdue: number | null };
};
type Issues = {
  ozet: {
    failed_payments_7d: number; failed_reminders: number; webhook_errors: number;
    pending_orders: number; audit_failures_24h: number;
  };
  failed_payments: { id: string; amount_try: number; status: string; created_at: string }[];
  failed_reminders: { id: string; baslik: string; status: string; remind_at: string; created_at: string }[];
  webhook_errors: { id: string; event_type: string; process_error: string | null; processed: boolean; created_at: string }[];
  pending_orders: { id: string; pack_key: string; amount_try: number; created_at: string }[];
  audit_failures: { id: string | number; action: string; ip_address: string | null; created_at: string }[];
};

const tarih = (s: string) => new Date(s).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });

function Durum({ ok, warn, label }: { ok: boolean; warn?: boolean; label: string }) {
  const renk = warn ? "text-amber-600 dark:text-amber-400" : ok ? "text-emerald-600 dark:text-emerald-400" : "text-destructive";
  const Icon = warn ? AlertTriangle : ok ? CheckCircle2 : XCircle;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${renk}`}>
      <Icon className="h-3.5 w-3.5" /> {label}
    </span>
  );
}

function SaglikKart({ icon: Icon, ad, ok, warn, detay }: {
  icon: typeof Database; ad: string; ok: boolean; warn?: boolean; detay?: string;
}) {
  return (
    <Card className={warn ? "border-amber-400/40" : ok ? "" : "border-destructive/40"}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Icon className="h-4 w-4 text-primary" /> {ad}
          </div>
          <Durum ok={ok} warn={warn} label={warn ? "Dikkat" : ok ? "Çalışıyor" : "Sorun"} />
        </div>
        {detay && <div className="mt-1.5 text-xs text-muted-foreground">{detay}</div>}
      </CardContent>
    </Card>
  );
}

export function SistemPanel() {
  const [health, setHealth] = useState<Health | null>(null);
  const [issues, setIssues] = useState<Issues | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const yukle = useCallback(async () => {
    setError(null);
    try {
      const [hR, iR] = await Promise.all([
        fetch("/api/proxy/admin/health", { cache: "no-store" }),
        fetch("/api/proxy/admin/issues", { cache: "no-store" }),
      ]);
      if (!hR.ok) throw new Error("Sağlık verisi alınamadı (admin yetkisi gerekli).");
      setHealth((await hR.json())?.data ?? null);
      if (iR.ok) setIssues((await iR.json())?.data ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    yukle();
    const t = setInterval(yukle, 30_000); // 30 sn'de bir otomatik yenile
    return () => clearInterval(t);
  }, [yukle]);

  if (loading) {
    return <div className="grid md:grid-cols-3 gap-4">{[1, 2, 3, 4, 5, 6].map((i) => <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />)}</div>;
  }
  if (error) {
    return <Card><CardContent className="p-6 text-destructive">⚠ {error}</CardContent></Card>;
  }

  const overdue = (health?.reminders.overdue ?? 0) > 0;
  const oz = issues?.ozet;
  const toplamSorun = oz ? oz.failed_payments_7d + oz.failed_reminders + oz.webhook_errors + oz.pending_orders + oz.audit_failures_24h : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2"><Activity className="h-5 w-5 text-primary" /> Sistem Sağlığı</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {health ? `Son kontrol: ${tarih(health.checked_at)} · otomatik yenileniyor` : ""}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={yukle}>
          <RefreshCw className="h-4 w-4 mr-1.5" /> Yenile
        </Button>
      </div>

      {/* Genel durum bandı */}
      <div className={`rounded-lg border p-3 text-sm flex items-center gap-2 ${
        toplamSorun === 0 && health?.db.ok && !overdue
          ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-800 dark:text-emerald-300"
          : "border-amber-400/40 bg-amber-400/10 text-amber-800 dark:text-amber-300"
      }`}>
        {toplamSorun === 0 && health?.db.ok && !overdue
          ? <><CheckCircle2 className="h-4 w-4" /> Tüm sistemler normal görünüyor.</>
          : <><AlertTriangle className="h-4 w-4" /> {toplamSorun} açık sorun / dikkat noktası var (aşağıda).</>}
      </div>

      {/* Sağlık kartları */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <SaglikKart icon={Database} ad="Veritabanı" ok={!!health?.db.ok}
          detay={health?.db.ok ? `Yanıt: ${health?.db.latency_ms ?? "?"} ms` : (health?.db.error ?? "Bağlantı yok")} />
        <SaglikKart icon={Sparkles} ad="Yapay Zeka (LLM)" ok={!!health?.llm.available}
          detay={health?.llm.available ? `Sağlayıcı: ${String(health?.llm.default ?? "—")}` : "Sağlayıcı erişilemiyor"} />
        <SaglikKart icon={Search} ad="Emsal Arama (RAG)" ok={!!health?.rag.available}
          detay={health?.rag.available ? `${health?.rag.chunk_count ?? "?"} kayıt` : "Koleksiyon hazır değil"} />
        <SaglikKart icon={CreditCard} ad="Ödeme (iyzico)" ok={!!health?.iyzico.configured}
          detay={health?.iyzico.configured ? "Yapılandırılmış (canlı)" : "Dev/yapılandırılmamış"} />
        <SaglikKart icon={Mail} ad="E-posta (SMTP)" ok={!!health?.mail.configured}
          detay={health?.mail.configured ? "Yapılandırılmış" : "SMTP ayarı yok"} />
        <SaglikKart icon={Bell} ad="Hatırlatıcı Gönderim" ok={!overdue} warn={overdue}
          detay={`Bekleyen: ${health?.reminders.pending ?? 0}${overdue ? ` · ${health?.reminders.overdue} geç kalmış!` : ""}`} />
      </div>

      {/* Hata akışı özeti */}
      <div>
        <h3 className="text-sm font-semibold mb-2 flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-primary" /> Hata & Aksaklık Akışı</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {[
            { k: "Başarısız ödeme (7g)", v: oz?.failed_payments_7d ?? 0, icon: Receipt },
            { k: "Başarısız hatırlatıcı", v: oz?.failed_reminders ?? 0, icon: Bell },
            { k: "Webhook hatası", v: oz?.webhook_errors ?? 0, icon: Webhook },
            { k: "Askıda sipariş (>1s)", v: oz?.pending_orders ?? 0, icon: Package },
            { k: "Audit hatası (24s)", v: oz?.audit_failures_24h ?? 0, icon: ShieldAlert },
          ].map((c) => (
            <Card key={c.k} className={c.v > 0 ? "border-destructive/40" : ""}>
              <CardContent className="p-3">
                <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground"><c.icon className="h-3.5 w-3.5" /> {c.k}</div>
                <div className={`text-2xl font-bold ${c.v > 0 ? "text-destructive" : ""}`}>{c.v}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Detay listeleri */}
      <HataListe baslik="Başarısız ödemeler (7 gün)" bos={!issues?.failed_payments.length}>
        {issues?.failed_payments.map((p) => (
          <Satir key={p.id} sol={`${p.amount_try.toLocaleString("tr-TR")} ₺ · ${p.status}`} sag={tarih(p.created_at)} />
        ))}
      </HataListe>

      <HataListe baslik="İşlenememiş / hatalı webhook'lar" bos={!issues?.webhook_errors.length}>
        {issues?.webhook_errors.map((w) => (
          <Satir key={w.id} sol={`${w.event_type}${w.processed ? "" : " · işlenmedi"}`} alt={w.process_error ?? undefined} sag={tarih(w.created_at)} />
        ))}
      </HataListe>

      <HataListe baslik="Askıda kalan ek paket siparişleri (>1 saat)" bos={!issues?.pending_orders.length}>
        {issues?.pending_orders.map((o) => (
          <Satir key={o.id} sol={`${o.pack_key} · ${o.amount_try.toLocaleString("tr-TR")} ₺`} sag={tarih(o.created_at)} />
        ))}
      </HataListe>

      <HataListe baslik="Başarısız hatırlatıcılar" bos={!issues?.failed_reminders.length}>
        {issues?.failed_reminders.map((r) => (
          <Satir key={r.id} sol={r.baslik} sag={tarih(r.created_at)} />
        ))}
      </HataListe>

      <HataListe baslik="Başarısız işlemler (audit, 24 saat)" bos={!issues?.audit_failures.length}>
        {issues?.audit_failures.map((a) => (
          <Satir key={String(a.id)} sol={a.action} alt={a.ip_address ?? undefined} sag={tarih(a.created_at)} />
        ))}
      </HataListe>
    </div>
  );
}

function HataListe({ baslik, bos, children }: { baslik: string; bos: boolean; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-2"><CardTitle className="text-sm">{baslik}</CardTitle></CardHeader>
      <CardContent>
        {bos ? <p className="text-sm text-muted-foreground flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Kayıt yok.</p>
          : <div className="divide-y">{children}</div>}
      </CardContent>
    </Card>
  );
}

function Satir({ sol, alt, sag }: { sol: string; alt?: string; sag: string }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2 text-sm">
      <div className="min-w-0">
        <div className="truncate">{sol}</div>
        {alt && <div className="text-xs text-destructive/80 truncate">{alt}</div>}
      </div>
      <div className="text-xs text-muted-foreground whitespace-nowrap">{sag}</div>
    </div>
  );
}
