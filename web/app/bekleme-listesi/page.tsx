"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const PLAN_LABELS: Record<string, string> = {
  pro_solo: "Pro Solo",
  pro_solo_uyap: "Pro + UYAP",
  team: "Team",
};

function BeklemeForms() {
  const params = useSearchParams();
  const planKey = params.get("plan") ?? "";
  const planLabel = PLAN_LABELS[planKey] ?? null;

  const [ad, setAd] = useState("");
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/proxy/waitlist/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: ad, email, plan: planKey || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.message || "Bir hata oluştu.");
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bir hata oluştu.");
    } finally {
      setLoading(false);
    }
  }

  if (submitted) {
    return (
      <div className="text-center space-y-4">
        <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto" />
        <h2 className="text-2xl font-bold">Listeye alındınız!</h2>
        <p className="text-muted-foreground text-sm max-w-sm mx-auto">
          Erişim davetiniz hazır olduğunda <strong>{email}</strong> adresine
          bildireceğiz. Sabırsızlıkla bekliyoruz.
        </p>
        <a href="/" className="text-primary text-sm hover:underline block pt-2">
          Ana sayfaya dön
        </a>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {planLabel && (
        <div className="bg-primary/10 text-primary text-sm font-medium rounded-lg px-4 py-2 text-center">
          {planLabel} planı için erken erişim
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="ad">Ad Soyad</Label>
        <Input
          id="ad"
          placeholder="Adınız Soyadınız"
          value={ad}
          onChange={(e) => setAd(e.target.value)}
          required
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="email">E-posta</Label>
        <Input
          id="email"
          type="email"
          placeholder="avukat@ornekburo.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </div>

      {error && (
        <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? "Kaydediliyor…" : "Bekleme Listesine Katıl"}
      </Button>

      <p className="text-xs text-muted-foreground text-center">
        Spam yok. Yalnızca erken erişim daveti geldiğinde haberdar ederiz.
      </p>
    </form>
  );
}

export default function BeklemePage() {
  return (
    <div className="container max-w-md py-16">
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 bg-primary/10 text-primary text-xs font-semibold px-3 py-1 rounded-full mb-4 uppercase tracking-wide">
          Davetli Beta
        </div>
        <h1 className="text-3xl font-bold mb-3">Erken Erişim İste</h1>
        <p className="text-muted-foreground text-sm">
          Hukuk Emsal seçili avukat ve hukuk bürolarına öncelikli erişim sunuyor.
          Listeye katılın, davetiniz hazır olduğunda size ulaşalım.
        </p>
      </div>

      <Suspense fallback={null}>
        <BeklemeForms />
      </Suspense>
    </div>
  );
}
