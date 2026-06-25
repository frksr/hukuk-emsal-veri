"use client";
import { useEffect, useState } from "react";
import { Loader2, Save, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export function ProfilForm({
  initialName,
  initialEmail,
}: {
  initialName: string;
  initialEmail: string;
}) {
  const [name, setName] = useState(initialName);
  const [marketing, setMarketing] = useState(false);
  // null = henüz bilinmiyor (yüklenirken). Yanlış "Doğrulanmamış"ı önce
  // göstermemek için yüklenene kadar nötr durum gösterilir.
  const [emailVerified, setEmailVerified] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Profil bilgilerini fetch
  useEffect(() => {
    fetch("/api/proxy/me")
      .then((r) => r.json())
      .then((j) => {
        if (j?.data?.user) {
          setMarketing(!!j.data.user.marketing_consent);
          setEmailVerified(!!j.data.user.email_verified);
        }
      })
      .catch(() => {});
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setSuccess(null); setError(null);
    try {
      const r = await fetch("/api/proxy/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, marketing_consent: marketing }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Kaydedilemedi");
      setSuccess("Profil güncellendi.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally {
      setLoading(false);
    }
  }

  async function resendVerification() {
    setResending(true);
    try {
      const r = await fetch("/api/proxy/auth/resend-verification", { method: "POST" });
      const j = await r.json();
      setSuccess(j.message || "Doğrulama e-postası gönderildi.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gönderilemedi");
    } finally {
      setResending(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profil Bilgileri</CardTitle>
        <CardDescription>Hesap bilgilerinizi yönetin.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={save} className="space-y-5">
          <div>
            <label className="text-sm font-medium mb-1.5 block">Ad Soyad</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">E-posta</label>
            <Input value={initialEmail} disabled />
            <div className="mt-2 flex items-center justify-between text-xs min-h-[20px]">
              {emailVerified === null ? (
                <span className="text-muted-foreground flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin" /> Doğrulama durumu kontrol ediliyor…
                </span>
              ) : emailVerified ? (
                <span className="text-emerald-600 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" /> Doğrulanmış
                </span>
              ) : (
                <>
                  <span className="text-amber-600">⚠ Doğrulanmamış</span>
                  <button
                    type="button"
                    onClick={resendVerification}
                    disabled={resending}
                    className="text-primary hover:underline"
                  >
                    {resending ? "Gönderiliyor..." : "Doğrulama e-postası gönder"}
                  </button>
                </>
              )}
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} />
            <span>Yeni özellik ve emsal karar bildirimleri için e-mail almak istiyorum.</span>
          </label>

          {success && <div className="rounded border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">✓ {success}</div>}
          {error && <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">⚠ {error}</div>}

          <Button type="submit" disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Kaydet
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
