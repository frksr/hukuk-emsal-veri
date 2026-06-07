"use client";
import { useState } from "react";
import { Loader2, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export function SifreForm() {
  const [current, setCurrent] = useState("");
  const [nw, setNw] = useState("");
  const [nw2, setNw2] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    if (nw !== nw2) return setMsg({ type: "err", text: "Yeni şifreler eşleşmiyor." });
    if (nw.length < 8) return setMsg({ type: "err", text: "Şifre en az 8 karakter olmalı." });

    setLoading(true);
    try {
      const r = await fetch("/api/proxy/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: current, new_password: nw }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Hata");
      setMsg({ type: "ok", text: j.message || "Şifre güncellendi." });
      setCurrent(""); setNw(""); setNw2("");
    } catch (err) {
      setMsg({ type: "err", text: err instanceof Error ? err.message : "Hata" });
    } finally { setLoading(false); }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Şifre Değiştir</CardTitle>
        <CardDescription>Şifrenizi güncelleyin. Değişiklik sonrası tüm cihazlarda yeniden giriş yapmanız gerekir.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-1.5 block">Mevcut Şifre</label>
            <Input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" />
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">Yeni Şifre (min 8 karakter)</label>
            <Input type="password" value={nw} onChange={(e) => setNw(e.target.value)} required minLength={8} autoComplete="new-password" />
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">Yeni Şifre Tekrar</label>
            <Input type="password" value={nw2} onChange={(e) => setNw2(e.target.value)} required autoComplete="new-password" />
          </div>
          {msg && (
            <div className={`rounded border p-3 text-sm ${
              msg.type === "ok"
                ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                : "border-destructive/50 bg-destructive/10 text-destructive"
            }`}>
              {msg.type === "ok" ? "✓" : "⚠"} {msg.text}
            </div>
          )}
          <Button type="submit" disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}
            Şifreyi Güncelle
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
