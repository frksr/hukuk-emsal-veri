"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Loader2, KeyRound, Copy, Check, Trash2, AlertTriangle, Lock, Puzzle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

type TokenRow = {
  id: string;
  name: string;
  prefix: string;
  last_used_at: string | null;
  created_at: string;
  revoked: boolean;
};

function formatDate(iso: string | null): string {
  if (!iso) return "Hiç kullanılmadı";
  return new Date(iso).toLocaleString("tr-TR");
}

export function EklentiPanel() {
  const [tokens, setTokens] = useState<TokenRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);

  async function loadTokens() {
    setLoading(true); setError(null); setPlanError(null);
    try {
      const r = await fetch("/api/proxy/extension/tokens");
      const j = await r.json();
      if (r.status === 402) {
        setPlanError(j.message || "UYAP eklentili plan gerekli.");
        setTokens([]);
        return;
      }
      if (!r.ok) throw new Error(j.message || "Anahtarlar alınamadı");
      setTokens(j.data?.tokens || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setLoading(false); }
  }

  useEffect(() => { loadTokens(); }, []);

  async function generate() {
    setGenerating(true); setError(null); setNewToken(null); setCopied(false);
    try {
      const r = await fetch("/api/proxy/extension/tokens", { method: "POST" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Anahtar oluşturulamadı");
      setNewToken(j.data?.token || null);
      await loadTokens();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    } finally { setGenerating(false); }
  }

  async function revoke(id: string) {
    if (!confirm("Bu anahtarı iptal edin mi? Eklenti bu anahtarla artık bağlanamayacak.")) return;
    try {
      const r = await fetch(`/api/proxy/extension/tokens/${id}`, { method: "DELETE" });
      if (!r.ok) throw new Error("İptal edilemedi");
      await loadTokens();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hata");
    }
  }

  function copyToken() {
    if (!newToken) return;
    navigator.clipboard.writeText(newToken);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (planError) {
    return (
      <Card className="border-accent/40 bg-accent/5">
        <CardContent className="p-8 text-center">
          <Lock className="h-12 w-12 text-accent mx-auto mb-3" />
          <h2 className="text-xl font-semibold mb-2">UYAP Eklentisi Gerekli</h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto mb-4">{planError}</p>
          <Button asChild>
            <Link href="/panel/ayarlar/abonelik">Planı Yükselt</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Puzzle className="h-5 w-5" /> UYAP Tarayıcı Eklentisi
          </CardTitle>
          <CardDescription>
            Eklenti, UYAP Avukat Portal&apos;da (avukat.uyap.gov.tr) baktığınız dosyayı
            tek tıkla &quot;Dosyalarım&quot;a aktarmanızı sağlar. Eklenti kendi
            oturum bilginize erişemez — bağlantıyı kurmak için aşağıdan bir
            kişisel erişim anahtarı oluşturup eklentiye bir kez girmeniz yeterli.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ol className="text-sm text-muted-foreground list-decimal list-inside space-y-1">
            <li>Aşağıdan yeni bir anahtar oluşturun.</li>
            <li>Anahtarı kopyalayın (yalnızca bir kez gösterilir).</li>
            <li>Eklentiyi kurun, simgesine tıklayıp anahtarı yapıştırın.</li>
            <li>UYAP Avukat Portal&apos;da bir dosya açın, beliren &quot;Siteme Aktar&quot; butonuna basın.</li>
          </ol>

          {error && (
            <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive flex gap-2">
              <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" /> {error}
            </div>
          )}

          {newToken && (
            <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 space-y-2">
              <p className="font-medium">
                Yeni anahtarınız — bunu şimdi kopyalayın, bir daha gösterilmeyecek:
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 min-w-0 truncate rounded bg-white/70 border border-amber-200 px-2 py-1.5 text-xs">
                  {newToken}
                </code>
                <Button size="sm" variant="outline" onClick={copyToken}>
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                </Button>
              </div>
            </div>
          )}

          <Button onClick={generate} disabled={generating}>
            {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}
            Yeni Anahtar Oluştur
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Aktif Anahtarlar</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-sm text-muted-foreground">Yükleniyor...</div>
          ) : tokens.length === 0 ? (
            <div className="text-sm text-muted-foreground">Henüz anahtar oluşturmadınız.</div>
          ) : (
            <div className="space-y-2">
              {tokens.map((t) => (
                <div
                  key={t.id}
                  className={`flex items-center justify-between gap-3 rounded border p-3 text-sm ${
                    t.revoked ? "opacity-50" : ""
                  }`}
                >
                  <div className="min-w-0">
                    <div className="font-mono text-xs truncate">{t.prefix}…</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      Oluşturuldu: {formatDate(t.created_at)} · Son kullanım: {formatDate(t.last_used_at)}
                      {t.revoked && " · İptal edildi"}
                    </div>
                  </div>
                  {!t.revoked && (
                    <Button size="sm" variant="ghost" onClick={() => revoke(t.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
