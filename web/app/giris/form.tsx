"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { Loader2, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

export function GirisForm() {
  const router = useRouter();
  const sp = useSearchParams();
  const callbackUrl = sp.get("callbackUrl") || "/app";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const res = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });
    if (res?.error) {
      setLoading(false);
      setError("E-posta veya şifre hatalı.");
      return;
    }
    // Varsayılan hedefte (belirli bir callbackUrl yoksa) admin'i doğrudan
    // admin paneline yönlendir; diğer kullanıcıları panele.
    let hedef = callbackUrl;
    if (callbackUrl === "/app") {
      try {
        const r = await fetch("/api/proxy/me", { cache: "no-store" });
        if (r.ok) {
          const j = await r.json();
          if (j?.data?.user?.role === "admin") hedef = "/app/admin";
        }
      } catch { /* yok say → panele */ }
    }
    setLoading(false);
    router.push(hedef);
    router.refresh();
  }

  return (
    <Card>
      <CardContent className="p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-1.5 block">E-posta</label>
            <Input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="avukat@ornek.com"
            />
          </div>
          <div>
            <div className="flex justify-between mb-1.5">
              <label className="text-sm font-medium">Şifre</label>
              <a href="/sifre-sifirla" className="text-xs text-muted-foreground hover:text-foreground">
                Şifremi unuttum
              </a>
            </div>
            <Input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          {error && (
            <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <Button type="submit" disabled={loading} className="w-full" size="lg">
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LogIn className="mr-2 h-4 w-4" />}
            Giriş Yap
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
