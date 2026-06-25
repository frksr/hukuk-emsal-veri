"use client";
import { useState } from "react";
import { Gift, Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export function BetaPanel() {
  const [email, setEmail] = useState("");
  const [plan, setPlan] = useState("pro_solo_uyap");
  const [days, setDays] = useState(180);
  const [sending, setSending] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setSending(true); setError(null); setSuccess(null);
    try {
      const r = await fetch("/api/proxy/admin/beta-invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, plan_tier: plan, duration_days: days }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message);
      setSuccess(j.message);
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setSending(false); }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Gift className="h-5 w-5 text-accent" /> Beta Davetiyesi Gönder
          </CardTitle>
          <CardDescription>
            Avukat'a e-posta gönderilir. Kayıt olunca manuel olarak tenant'ı upgrade etmen gerekir
            (Kullanıcılar sayfasından hediye ikonu ile).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={send} className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-1.5 block">E-posta</label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="avukat@buro.tr" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium mb-1.5 block">Plan</label>
                <select value={plan} onChange={(e) => setPlan(e.target.value)} className="w-full h-10 rounded-md border bg-background px-3 text-sm">
                  <option value="pro_solo">Pro Solo</option>
                  <option value="pro_solo_uyap">Pro + UYAP (önerilen)</option>
                  <option value="team">Team</option>
                  <option value="team_uyap">Team + UYAP</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium mb-1.5 block">Süre (gün)</label>
                <Input type="number" value={days} onChange={(e) => setDays(Number(e.target.value))} min={30} max={365} />
              </div>
            </div>

            {success && <div className="rounded border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">✓ {success}</div>}
            {error && <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">⚠ {error}</div>}

            <Button type="submit" disabled={sending || !email}>
              {sending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
              Davetiyeyi Gönder
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card className="bg-muted/30">
        <CardContent className="p-5 text-sm space-y-2">
          <h3 className="font-semibold">Beta program akışı:</h3>
          <ol className="list-decimal pl-5 space-y-1 text-muted-foreground">
            <li>Bu form ile avukata davetiye e-postası gönder</li>
            <li>Avukat kayıt olur (free hesap)</li>
            <li>Kullanıcılar sayfasından hediye ikonu (🎁) ile 180 gün Pro+UYAP aktif et</li>
            <li>Beta sözleşmesini imzalat (KVKK + geri bildirim taahhüdü)</li>
            <li>Onboarding rehberini gönder</li>
            <li>Haftalık 15dk geri bildirim görüşmesi</li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
