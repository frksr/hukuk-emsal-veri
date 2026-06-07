"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { Loader2, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

export function KayitForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [kvkk, setKvkk] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setError(null);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password, kvkk, marketing }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || "Kayıt başarısız");

      // Auto login
      await signIn("credentials", { email, password, redirect: false });
      router.push("/hosgeldin");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  return (
    <Card>
      <CardContent className="p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-1.5 block">Ad Soyad</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Av. Mehmet Yılmaz" />
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">E-posta</label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">Şifre (min 8 karakter)</label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" />
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={kvkk} onChange={(e) => setKvkk(e.target.checked)} required className="mt-1" />
            <span>
              <a href="/gizlilik" target="_blank" className="text-primary hover:underline">KVKK Aydınlatma Metni</a>{" "}
              ve{" "}
              <a href="/kullanim-sartlari" target="_blank" className="text-primary hover:underline">Kullanım Şartları</a>'nı
              okudum, onaylıyorum.
            </span>
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} className="mt-1" />
            <span className="text-muted-foreground">E-mail ile yeni özellik ve emsal karar bildirimleri almak istiyorum (opsiyonel).</span>
          </label>
          {error && (
            <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <Button type="submit" disabled={loading || !kvkk} className="w-full" size="lg">
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <UserPlus className="mr-2 h-4 w-4" />}
            Ücretsiz Hesap Aç
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
