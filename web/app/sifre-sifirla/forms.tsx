"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, KeyRound, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

export function ForgotForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await fetch("/api/proxy/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const j = await r.json();
      setMsg(j.message || "Eğer kayıtlıysa bağlantı gönderildi.");
    } catch (err) {
      setMsg("Bir hata oluştu, tekrar deneyin.");
    } finally { setLoading(false); }
  }

  return (
    <Card>
      <CardContent className="p-6">
        <p className="text-sm text-muted-foreground mb-4">
          Hesabınıza ait e-posta adresini girin. Şifre sıfırlama bağlantısı e-postanıza gönderilir.
        </p>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-1.5 block">E-posta</label>
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          {msg && <div className="rounded border border-blue-300 bg-blue-50 p-3 text-sm text-blue-900">{msg}</div>}
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
            Sıfırlama Bağlantısı Gönder
          </Button>
        </form>
        <div className="mt-4 text-center text-sm">
          <a href="/giris" className="text-primary hover:underline">Giriş sayfasına dön</a>
        </div>
      </CardContent>
    </Card>
  );
}

export function ResetForm({ token }: { token: string }) {
  const router = useRouter();
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (pw !== pw2) return setError("Şifreler eşleşmiyor.");
    if (pw.length < 8) return setError("Şifre en az 8 karakter olmalı.");
    setLoading(true);
    try {
      const r = await fetch("/api/proxy/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: pw }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Hata");
      setSuccess(true);
      setTimeout(() => router.push("/giris"), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  if (success) {
    return (
      <Card><CardContent className="p-6 text-center space-y-3">
        <div className="text-emerald-600 text-3xl">✓</div>
        <p className="font-semibold">Şifreniz güncellendi.</p>
        <p className="text-sm text-muted-foreground">Giriş sayfasına yönlendiriliyorsunuz...</p>
      </CardContent></Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-6">
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-1.5 block">Yeni Şifre (min 8 karakter)</label>
            <Input type="password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" />
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">Yeni Şifre Tekrar</label>
            <Input type="password" required value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" />
          </div>
          {error && <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">⚠ {error}</div>}
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}
            Şifreyi Belirle
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
