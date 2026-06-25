"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";
import { Loader2, Download, Trash2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export function KvkkPanel() {
  const router = useRouter();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function downloadData() {
    setDownloading(true); setError(null);
    try {
      const r = await fetch("/api/proxy/me");
      const meData = await r.json();
      const r2 = await fetch("/api/proxy/me/searches?limit=200");
      const sData = await r2.json();
      const export_ = {
        exported_at: new Date().toISOString(),
        user: meData.data?.user,
        tenants: meData.data?.tenant ? [meData.data.tenant] : [],
        searches: sData.data?.searches || [],
        note: "KVKK madde 11 — veri taşınabilirliği hakkı kapsamında üretilmiştir.",
      };
      const blob = new Blob([JSON.stringify(export_, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `hukukemsal-verilerim-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "İndirme hatası");
    } finally { setDownloading(false); }
  }

  async function deleteAccount() {
    setDeleting(true); setError(null);
    try {
      const r = await fetch("/api/proxy/me/account", { method: "DELETE" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.message || "Silinemedi");
      await signOut({ redirect: false });
      router.push("/?account_deleted=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Silme hatası");
    } finally { setDeleting(false); }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Verilerinizi İndirin</CardTitle>
          <CardDescription>
            KVKK madde 11 — veri taşınabilirliği hakkınız çerçevesinde, sistemde tuttuğumuz
            kişisel verilerinizi JSON olarak indirebilirsiniz.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={downloadData} disabled={downloading} variant="outline">
            {downloading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
            Verilerimi İndir (JSON)
          </Button>
        </CardContent>
      </Card>

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="text-destructive flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" /> Hesabı Sil
          </CardTitle>
          <CardDescription>
            KVKK madde 7 — silme hakkınız. Hesabınız pasifleştirilir ve 30 gün içinde tüm
            kişisel verileriniz geri dönüşsüz silinir. UYAP dosyaları da kalıcı silinir.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {!confirmDelete ? (
            <Button onClick={() => setConfirmDelete(true)} variant="destructive">
              <Trash2 className="mr-2 h-4 w-4" /> Hesabı Sil
            </Button>
          ) : (
            <div className="space-y-3 p-4 border border-destructive/30 rounded bg-destructive/5">
              <p className="text-sm font-semibold text-destructive">
                Bu işlem geri alınamaz. Tüm geçmiş aramalarınız, yüklenen UYAP dosyalarınız ve
                üretilen dilekçeler silinir.
              </p>
              <div className="flex gap-2">
                <Button onClick={deleteAccount} disabled={deleting} variant="destructive">
                  {deleting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
                  Evet, Sil
                </Button>
                <Button onClick={() => setConfirmDelete(false)} variant="ghost">
                  Vazgeç
                </Button>
              </div>
            </div>
          )}
          {error && (
            <div className="rounded border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              ⚠ {error}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}
