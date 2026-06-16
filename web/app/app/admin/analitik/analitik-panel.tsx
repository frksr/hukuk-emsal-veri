"use client";
import { useCallback, useEffect, useState } from "react";
import {
  BarChart3, Users, UserPlus, Activity, TrendingUp, Wallet, Package,
  Coins, Sparkles, Wrench, Cpu, Receipt, RefreshCw, Crown,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Analytics = {
  generated_at: string;
  musteriler: {
    toplam_aktif: number; yeni_24s: number; yeni_7g: number; yeni_30g: number;
    dau: number; mau: number;
    plan_dagilimi: { plan: string; adet: number }[];
  };
  gelir: {
    abonelik_adet: number; abonelik_toplam_try: number;
    ek_paket_adet: number; ek_paket_toplam_try: number;
    tahmini_aylik_gelir_try: number;
    en_cok_satilan_paketler: { pack_key: string; adet: number; toplam_try: number }[];
  };
  krediler: { module: string; etiket: string; satin_alinan: number; tuketilen: number }[];
  ai_istekleri: {
    toplam: number; son_30g: number;
    gunluk_trend_7g: { tarih: string; adet: number }[];
  };
  araclar: { event_type: string; etiket: string; toplam: number; son_30g: number }[];
  en_aktif_musteriler: {
    user_id: string; email: string | null; name: string | null;
    islem_sayisi: number; son_islem: string | null;
  }[];
  tahmini_maliyet: {
    tahmini: boolean; para_birimi: string;
    toplam: { toplam_try: number; kalemler: MaliyetKalem[] };
    son_30g: { toplam_try: number; kalemler: MaliyetKalem[] };
  };
  saglayici_dagilimi: {
    toplam: { provider: string; adet: number }[];
    son_30g: { provider: string; adet: number }[];
  };
};
type MaliyetKalem = {
  event_type: string; etiket: string; adet: number; birim_try: number; tutar_try: number;
};

const PLAN_ETIKET: Record<string, string> = {
  free: "Ücretsiz", pro_solo: "Pro Solo", pro_solo_uyap: "Pro Solo + UYAP",
  team: "Team", team_uyap: "Team + UYAP", enterprise: "Enterprise",
};
const SAGLAYICI_ETIKET: Record<string, string> = {
  anthropic: "Anthropic (Claude)", gemini: "Google Gemini", bilinmiyor: "Bilinmiyor (eski kayıt)",
};

const tl = (n: number) => n.toLocaleString("tr-TR", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const tarih = (s: string | null) =>
  s ? new Date(s).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" }) : "—";

// Yatay CSS bar — en yüksek değere göre orantılı.
function Bar({ label, value, max, suffix }: { label: string; value: number; max: number; suffix?: string }) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="truncate text-foreground">{label}</span>
        <span className="text-muted-foreground tabular-nums ml-2 whitespace-nowrap">
          {value.toLocaleString("tr-TR")}{suffix ?? ""}
        </span>
      </div>
      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Metrik({ icon: Icon, etiket, deger, alt }: {
  icon: typeof Users; etiket: string; deger: string | number; alt?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <Icon className="h-3.5 w-3.5" /> {etiket}
        </div>
        <div className="text-2xl font-bold mt-0.5 tabular-nums">{deger}</div>
        {alt && <div className="text-xs text-muted-foreground mt-0.5">{alt}</div>}
      </CardContent>
    </Card>
  );
}

export function AnalitikPanel() {
  const [d, setD] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const yukle = useCallback(async () => {
    setError(null);
    try {
      const r = await fetch("/api/proxy/admin/analytics", { cache: "no-store" });
      if (!r.ok) throw new Error("Analitik verisi alınamadı (admin yetkisi gerekli).");
      setD((await r.json())?.data ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hata");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { yukle(); }, [yukle]);

  if (loading) {
    return (
      <div className="grid md:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />)}
      </div>
    );
  }
  if (error || !d) {
    return <Card><CardContent className="p-6 text-destructive">⚠ {error ?? "Veri yok"}</CardContent></Card>;
  }

  const m = d.musteriler;
  const g = d.gelir;
  const trendMax = Math.max(1, ...d.ai_istekleri.gunluk_trend_7g.map((x) => x.adet));
  const araclar = [...d.araclar].slice(0, 12);
  const araclarMax = Math.max(1, ...araclar.map((a) => a.toplam));
  const planMax = Math.max(1, ...m.plan_dagilimi.map((p) => p.adet));
  const krediler = [...d.krediler].filter((k) => k.satin_alinan > 0 || k.tuketilen > 0).slice(0, 12);
  const krediMax = Math.max(1, ...krediler.map((k) => Math.max(k.satin_alinan, k.tuketilen)));
  const provMax = Math.max(1, ...d.saglayici_dagilimi.toplam.map((p) => p.adet));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-primary" /> Analitik
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Son güncelleme: {tarih(d.generated_at)} · gerçek verilerden hesaplanır
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={yukle}>
          <RefreshCw className="h-4 w-4 mr-1.5" /> Yenile
        </Button>
      </div>

      {/* a) Müşteriler */}
      <section className="space-y-3">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Users className="h-4 w-4 text-primary" /> Müşteriler</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <Metrik icon={Users} etiket="Toplam aktif" deger={m.toplam_aktif} />
          <Metrik icon={Activity} etiket="DAU (24s)" deger={m.dau} />
          <Metrik icon={Activity} etiket="MAU (30g)" deger={m.mau} />
          <Metrik icon={UserPlus} etiket="Yeni (24s)" deger={m.yeni_24s} />
          <Metrik icon={UserPlus} etiket="Yeni (7g)" deger={m.yeni_7g} />
          <Metrik icon={UserPlus} etiket="Yeni (30g)" deger={m.yeni_30g} />
        </div>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Plan (tier) dağılımı</CardTitle></CardHeader>
          <CardContent className="space-y-2.5">
            {m.plan_dagilimi.length === 0
              ? <p className="text-sm text-muted-foreground">Kayıt yok.</p>
              : m.plan_dagilimi.map((p) => (
                  <Bar key={p.plan} label={PLAN_ETIKET[p.plan] ?? p.plan} value={p.adet} max={planMax} />
                ))}
          </CardContent>
        </Card>
      </section>

      {/* b) Gelir & paket alımları */}
      <section className="space-y-3">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Wallet className="h-4 w-4 text-primary" /> Gelir & Paket Alımları <span className="text-xs font-normal text-muted-foreground">(son 30 gün)</span></h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Metrik icon={Receipt} etiket="Abonelik ödemeleri" deger={`${tl(g.abonelik_toplam_try)} ₺`} alt={`${g.abonelik_adet} ödeme`} />
          <Metrik icon={Package} etiket="Ek paket alımları" deger={`${tl(g.ek_paket_toplam_try)} ₺`} alt={`${g.ek_paket_adet} sipariş`} />
          <Metrik icon={TrendingUp} etiket="Tahmini aylık gelir" deger={`${tl(g.tahmini_aylik_gelir_try)} ₺`} alt="abonelik + ek paket" />
        </div>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">En çok satılan ek paketler</CardTitle></CardHeader>
          <CardContent>
            {g.en_cok_satilan_paketler.length === 0
              ? <p className="text-sm text-muted-foreground">Henüz ek paket satışı yok.</p>
              : <div className="divide-y">
                  {g.en_cok_satilan_paketler.map((p) => (
                    <div key={p.pack_key} className="flex items-center justify-between gap-3 py-2 text-sm">
                      <span className="truncate font-mono text-xs">{p.pack_key}</span>
                      <span className="text-muted-foreground whitespace-nowrap">
                        {p.adet} adet · <span className="text-foreground">{tl(p.toplam_try)} ₺</span>
                      </span>
                    </div>
                  ))}
                </div>}
          </CardContent>
        </Card>
      </section>

      {/* c) Kredi kullanımları */}
      <section className="space-y-3">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Coins className="h-4 w-4 text-primary" /> Kredi Kullanımları <span className="text-xs font-normal text-muted-foreground">(modül bazlı, tüm zamanlar)</span></h3>
        <Card>
          <CardContent className="p-4 space-y-3">
            {krediler.length === 0
              ? <p className="text-sm text-muted-foreground">Kredi hareketi yok.</p>
              : krediler.map((k) => (
                  <div key={k.module} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-foreground">{k.etiket}</span>
                      <span className="text-muted-foreground tabular-nums">
                        <span className="text-emerald-600 dark:text-emerald-400">+{k.satin_alinan.toLocaleString("tr-TR")}</span>
                        {" satın alınan · "}
                        <span className="text-destructive">−{k.tuketilen.toLocaleString("tr-TR")}</span>
                        {" tüketilen"}
                      </span>
                    </div>
                    <div className="flex gap-1 h-2">
                      <div className="flex-1 rounded-full bg-muted overflow-hidden">
                        <div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.max(2, (k.satin_alinan / krediMax) * 100)}%` }} />
                      </div>
                      <div className="flex-1 rounded-full bg-muted overflow-hidden">
                        <div className="h-full rounded-full bg-destructive" style={{ width: `${Math.max(2, (k.tuketilen / krediMax) * 100)}%` }} />
                      </div>
                    </div>
                  </div>
                ))}
          </CardContent>
        </Card>
      </section>

      {/* d) Yapay Zeka istek sayısı + trend */}
      <section className="space-y-3">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Sparkles className="h-4 w-4 text-primary" /> Yapay Zeka İstekleri</h3>
        <div className="grid grid-cols-2 sm:grid-cols-2 gap-3">
          <Metrik icon={Sparkles} etiket="Toplam AI isteği" deger={d.ai_istekleri.toplam} />
          <Metrik icon={Sparkles} etiket="Son 30 gün" deger={d.ai_istekleri.son_30g} />
        </div>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Günlük AI isteği — son 7 gün</CardTitle></CardHeader>
          <CardContent>
            {d.ai_istekleri.gunluk_trend_7g.length === 0
              ? <p className="text-sm text-muted-foreground">Son 7 günde AI isteği yok.</p>
              : <div className="flex items-end gap-2 h-32">
                  {d.ai_istekleri.gunluk_trend_7g.map((x) => (
                    <div key={x.tarih} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                      <div className="text-[10px] text-muted-foreground tabular-nums">{x.adet}</div>
                      <div className="w-full bg-primary/80 rounded-t" style={{ height: `${Math.max(4, (x.adet / trendMax) * 100)}%` }} />
                      <div className="text-[9px] text-muted-foreground whitespace-nowrap">
                        {new Date(x.tarih + "T00:00:00").toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" })}
                      </div>
                    </div>
                  ))}
                </div>}
          </CardContent>
        </Card>
      </section>

      {/* e) En çok kullanılan araçlar */}
      <section className="space-y-3">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Wrench className="h-4 w-4 text-primary" /> En Çok Kullanılan Araçlar</h3>
        <Card>
          <CardContent className="p-4 space-y-2.5">
            {araclar.length === 0
              ? <p className="text-sm text-muted-foreground">Kullanım kaydı yok.</p>
              : araclar.map((a) => (
                  <Bar key={a.event_type} label={`${a.etiket}`} value={a.toplam} max={araclarMax}
                       suffix={` · 30g: ${a.son_30g.toLocaleString("tr-TR")}`} />
                ))}
          </CardContent>
        </Card>
      </section>

      {/* h) Sağlayıcı dağılımı */}
      <section className="space-y-3">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Cpu className="h-4 w-4 text-primary" /> Yapay Zeka Sağlayıcı Dağılımı</h3>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Hangi sağlayıcıya kaç istek (AI olayları)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {d.saglayici_dagilimi.toplam.length === 0
              ? <p className="text-sm text-muted-foreground">AI olayı yok.</p>
              : <>
                  {d.saglayici_dagilimi.toplam.map((p) => (
                    <Bar key={p.provider} label={SAGLAYICI_ETIKET[p.provider] ?? p.provider} value={p.adet} max={provMax} />
                  ))}
                  <p className="text-[11px] text-muted-foreground pt-1">
                    Not: Sağlayıcı, isteğin yapıldığı andaki varsayılan LLM&apos;den kaydedilir.
                    Bu özellik öncesi olaylar &quot;Bilinmiyor&quot; altında toplanır.
                  </p>
                </>}
          </CardContent>
        </Card>
      </section>

      {/* g) Tahmini maliyet */}
      <section className="space-y-3">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Receipt className="h-4 w-4 text-primary" /> Tahmini Yapay Zeka Maliyeti</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Metrik icon={Receipt} etiket="Tahmini maliyet (son 30g)" deger={`≈ ${tl(d.tahmini_maliyet.son_30g.toplam_try)} ₺`} alt="TAHMİNİ — gerçek fatura değil" />
          <Metrik icon={Receipt} etiket="Tahmini maliyet (toplam)" deger={`≈ ${tl(d.tahmini_maliyet.toplam.toplam_try)} ₺`} alt="TAHMİNİ — gerçek fatura değil" />
        </div>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Araç başına tahmini maliyet (toplam)</CardTitle>
          </CardHeader>
          <CardContent>
            {d.tahmini_maliyet.toplam.kalemler.length === 0
              ? <p className="text-sm text-muted-foreground">Maliyet kaydı yok.</p>
              : <div className="divide-y">
                  {d.tahmini_maliyet.toplam.kalemler.map((k) => (
                    <div key={k.event_type} className="flex items-center justify-between gap-3 py-2 text-sm">
                      <span className="truncate">{k.etiket}</span>
                      <span className="text-muted-foreground whitespace-nowrap tabular-nums">
                        {k.adet.toLocaleString("tr-TR")} istek × {tl(k.birim_try)} ₺ = <span className="text-foreground">≈ {tl(k.tutar_try)} ₺</span>
                      </span>
                    </div>
                  ))}
                </div>}
            <p className="text-[11px] text-muted-foreground pt-2">
              Birim maliyetler yapılandırılabilir tahminlerdir (backend: TAHMINI_MALIYET_TRY).
              Gerçek sağlayıcı faturasını yansıtmaz.
            </p>
          </CardContent>
        </Card>
      </section>

      {/* f) En aktif müşteriler */}
      <section className="space-y-3">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Crown className="h-4 w-4 text-primary" /> En Aktif Müşteriler</h3>
        <Card>
          <CardContent className="p-0">
            {d.en_aktif_musteriler.length === 0
              ? <p className="text-sm text-muted-foreground p-4">Kayıt yok.</p>
              : <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs text-muted-foreground border-b">
                      <tr>
                        <th className="text-left font-medium px-4 py-2">#</th>
                        <th className="text-left font-medium px-4 py-2">Müşteri</th>
                        <th className="text-right font-medium px-4 py-2">İşlem</th>
                        <th className="text-right font-medium px-4 py-2 whitespace-nowrap">Son işlem</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {d.en_aktif_musteriler.map((u, i) => (
                        <tr key={u.user_id}>
                          <td className="px-4 py-2 text-muted-foreground tabular-nums">{i + 1}</td>
                          <td className="px-4 py-2 min-w-0">
                            <div className="truncate font-medium">{u.name || u.email || u.user_id.slice(0, 8)}</div>
                            {u.name && u.email && <div className="truncate text-xs text-muted-foreground">{u.email}</div>}
                          </td>
                          <td className="px-4 py-2 text-right tabular-nums font-semibold">{u.islem_sayisi.toLocaleString("tr-TR")}</td>
                          <td className="px-4 py-2 text-right text-xs text-muted-foreground whitespace-nowrap">{tarih(u.son_islem)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
