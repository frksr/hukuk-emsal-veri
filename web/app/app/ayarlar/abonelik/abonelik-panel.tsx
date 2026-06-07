"use client";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, ArrowRight, Loader2, Crown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const PLANS = [
  { key: "free", name: "Free", price: "₺0", desc: "Bireysel deneme",
    features: ["40 emsal arama/gün", "6 dilekçe/gün", "Hesaplayıcılar sınırsız", "Geçmiş kayıt"] },
  { key: "pro_solo", name: "Pro Solo", price: "₺499/ay", desc: "Bireysel avukat",
    features: ["Sınırsız genel araçlar", "AI dilekçe + denetim sınırsız", "Geçmiş tam metin arama"] },
  { key: "pro_solo_uyap", name: "Pro + UYAP", price: "₺799/ay", desc: "UYAP eklentili",
    features: ["Pro Solo'nun her şeyi", "50 UYAP dosyası", "200 AI sorgu/ay", "Kendi dosyalarınızda RAG"],
    popular: true },
  { key: "team", name: "Team", price: "₺1.499/ay", desc: "5 kullanıcı",
    features: ["5 kullanıcı", "Rol bazlı erişim", "Ortak dosyalar", "Beyaz etiket"] },
  { key: "team_uyap", name: "Team + UYAP", price: "₺1.999/ay", desc: "Büro + UYAP",
    features: ["Team'in her şeyi", "250 UYAP dosyası", "1.000 sorgu/ay"] },
  { key: "enterprise", name: "Enterprise", price: "Görüşelim", desc: "Büyük büro",
    features: ["Sınırsız UYAP", "SSO", "Self-hosted opsiyonu", "SLA"] },
];

type Current = { plan: string; status: string; period_end: string | null; cancel_at_period_end: boolean };

export function AbonelikPanel() {
  const router = useRouter();
  const sp = useSearchParams();
  const [current, setCurrent] = useState<Current | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadCurrent();
    // Callback handling
    const callback = sp.get("callback");
    const token = sp.get("token");
    if (callback && token) handleCallback(token);
    if (sp.get("mock") === "1") {
      setSuccess("DEV MODE — Mock checkout başarılı görünür. Production'da iyzico'ya yönlendirilir.");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadCurrent() {
    try {
      const r = await fetch("/api/proxy/billing/current");
      const j = await r.json();
      if (r.ok) setCurrent(j.data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }

  async function handleCallback(token: string) {
    try {
      const r = await fetch("/api/proxy/billing/callback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const j = await r.json();
      if (r.ok && j.ok) {
        setSuccess(j.message || "Aboneliğiniz aktif!");
        await loadCurrent();
        router.replace("/app/ayarlar/abonelik");
      } else {
        setError(j.message || "Ödeme onaylanamadı.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    }
  }

  async function startCheckout(planKey: string) {
    setCheckingOut(planKey); setError(null);
    try {
      const r = await fetch("/api/proxy/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_tier: planKey }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Checkout başlatılamadı");
      if (j.data?.payment_page_url) {
        window.location.href = j.data.payment_page_url;
      } else {
        setError("Ödeme sayfası alınamadı.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setCheckingOut(null); }
  }

  async function cancelSub() {
    if (!confirm("Aboneliğiniz dönem sonunda iptal edilecek. Onaylıyor musunuz?")) return;
    try {
      const r = await fetch("/api/proxy/billing/cancel", { method: "POST" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "İptal edilemedi");
      setSuccess(j.message || "Abonelik iptal edildi.");
      await loadCurrent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    }
  }

  const activePlan = current?.plan || "free";

  return (
    <>
      {success && (
        <Card className="bg-emerald-50 border-emerald-300">
          <CardContent className="p-4 text-sm text-emerald-900">✓ {success}</CardContent>
        </Card>
      )}
      {error && (
        <Card className="bg-destructive/10 border-destructive/50">
          <CardContent className="p-4 text-sm text-destructive">⚠ {error}</CardContent>
        </Card>
      )}

      <Card className="bg-primary/5 border-primary/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Crown className="h-5 w-5 text-primary" /> Mevcut Plan: {PLANS.find(p => p.key === activePlan)?.name || activePlan}
          </CardTitle>
          {current?.period_end && (
            <CardDescription>
              {current.cancel_at_period_end
                ? `Dönem sonu: ${new Date(current.period_end).toLocaleDateString("tr-TR")} (iptal edilecek)`
                : `Sonraki yenileme: ${new Date(current.period_end).toLocaleDateString("tr-TR")}`}
            </CardDescription>
          )}
        </CardHeader>
        {current && current.plan !== "free" && !current.cancel_at_period_end && (
          <CardContent>
            <Button onClick={cancelSub} variant="outline" size="sm">Aboneliği İptal Et</Button>
          </CardContent>
        )}
      </Card>

      {loading ? (
        <div className="grid md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-80 rounded-lg bg-muted animate-pulse" />)}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {PLANS.map((p) => {
            const isCurrent = p.key === activePlan;
            return (
              <Card key={p.key} className={p.popular ? "border-accent shadow-md" : isCurrent ? "border-primary" : ""}>
                <CardHeader>
                  {p.popular && (
                    <span className="text-xs bg-accent text-accent-foreground px-2 py-0.5 rounded uppercase tracking-wider self-start mb-2">
                      Popüler
                    </span>
                  )}
                  {isCurrent && (
                    <span className="text-xs bg-primary text-primary-foreground px-2 py-0.5 rounded self-start mb-2">
                      Aktif Plan
                    </span>
                  )}
                  <CardTitle>{p.name}</CardTitle>
                  <div className="text-3xl font-bold mt-2">{p.price}</div>
                  <CardDescription>{p.desc}</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 text-sm mb-6">
                    {p.features.map((f) => (
                      <li key={f} className="flex gap-2">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                  {p.key === "enterprise" ? (
                    <Button asChild className="w-full" variant="outline">
                      <a href="mailto:satis@hukukemsal.tr?subject=Enterprise%20paket">İletişime Geç</a>
                    </Button>
                  ) : isCurrent ? (
                    <Button disabled className="w-full" variant="outline">Aktif Plan</Button>
                  ) : (
                    <Button
                      onClick={() => startCheckout(p.key)}
                      disabled={checkingOut === p.key || p.key === "free"}
                      variant={p.popular ? "default" : "outline"}
                      className="w-full"
                    >
                      {checkingOut === p.key ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <>{p.key === "free" ? "—" : "Bu Plana Geç"} {p.key !== "free" && <ArrowRight className="ml-2 h-4 w-4" />}</>
                      )}
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Card className="bg-muted/30">
        <CardContent className="p-6 text-sm text-muted-foreground space-y-2">
          <p><strong>Ödeme:</strong> Iyzico güvenli ödeme altyapısı. Türk lirası, kart veya havale.</p>
          <p><strong>İade:</strong> İlk 14 gün koşulsuz iade.</p>
          <p><strong>Faturalama:</strong> Şirket adı ve vergi no bilgilerinizi billing email'inden iletebilirsiniz.</p>
        </CardContent>
      </Card>
    </>
  );
}
