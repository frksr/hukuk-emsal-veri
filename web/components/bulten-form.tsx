"use client";
import { useState } from "react";
import { Mail, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * Haftalık bülten abonelik formu — /blog ve /blog/[slug] sayfalarına gömülür.
 * Yeni bir rehber yazısı yayınlandığında abonelere kısa bir bildirim +
 * yazıya bağlantı gönderilir (bkz. services/newsletter.py) — tam metin
 * e-postaya gömülmez (SEO/trafik için siteye yönlendirme tercih edildi).
 */
export function BultenForm({ className = "" }: { className?: string }) {
  const [email, setEmail] = useState("");
  const [onay, setOnay] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!onay) {
      setError("Devam etmek için e-posta izni onayı gereklidir.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const r = await fetch("/api/proxy/newsletter/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, consent: onay }),
      });
      const j = await r.json();
      if (!r.ok || !j.ok) throw new Error(j?.message || "Bir hata oluştu.");
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bir hata oluştu.");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className={`rounded-xl border bg-card p-6 text-center ${className}`}>
        <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
        <p className="font-semibold">Abone oldunuz!</p>
        <p className="text-sm text-muted-foreground mt-1">
          Yeni bir rehber yazısı yayınlandığında {email} adresine haber vereceğiz.
        </p>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border bg-card p-6 ${className}`}>
      <div className="flex items-center gap-2 mb-1.5">
        <Mail className="h-5 w-5 text-primary" />
        <h3 className="font-semibold">Haftalık Bültene Abone Ol</h3>
      </div>
      <p className="text-sm text-muted-foreground mb-4">
        Yeni rehber yazıları yayınlandığında haberdar olun. Spam yok, dilediğiniz
        an tek tıkla çıkabilirsiniz.
      </p>
      <form onSubmit={submit} className="space-y-3">
        <div className="flex flex-col sm:flex-row gap-2">
          <Input
            type="email"
            required
            placeholder="avukat@ornekburo.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="flex-1"
          />
          <Button type="submit" disabled={loading} className="sm:w-auto">
            {loading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
            Abone Ol
          </Button>
        </div>
        <label className="flex items-start gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={onay}
            onChange={(e) => setOnay(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            Yeni yazı bildirimleri için e-posta adresimin işlenmesine izin
            veriyorum. Dilediğim an{" "}
            <a href="/gizlilik" className="underline hover:text-foreground">
              Gizlilik Politikası
            </a>{" "}
            uyarınca abonelikten çıkabilirim.
          </span>
        </label>
        {error && <p className="text-xs text-destructive">{error}</p>}
      </form>
    </div>
  );
}
