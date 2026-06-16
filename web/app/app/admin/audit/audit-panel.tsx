"use client";
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

type Log = {
  id: number;
  user_id: string | null;
  user_email: string | null;
  user_name: string | null;
  tenant_id: string | null;
  action: string;
  resource: string | null;
  ip_address: string | null;
  success: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
};

// Aksiyon kodu → okunabilir Türkçe etiket. Bilinmeyenler humanize() ile çevrilir.
const ACTION_LABEL: Record<string, string> = {
  "login": "Giriş yapıldı",
  "logout": "Çıkış yapıldı",
  "profile.updated": "Profil güncellendi",
  "password.changed": "Şifre değiştirildi",
  "password.reset_requested": "Şifre sıfırlama istendi",
  "password.reset_completed": "Şifre sıfırlandı",
  "password.change_failed": "Şifre değişimi başarısız",
  "email.verified": "E-posta doğrulandı",
  "email.code_sent": "Doğrulama kodu gönderildi",
  "email.verification_resent": "Doğrulama e-postası yeniden gönderildi",
  "email.verify_failed": "Doğrulama kodu hatalı",
  "account.deleted": "Hesap silindi",
  "history.cleared": "Geçmiş temizlendi",
  "apikey.created": "API anahtarı oluşturuldu",
  "apikey.revoked": "API anahtarı iptal edildi",
  "billing.checkout_initiated": "Ödeme başlatıldı",
  "billing.subscription_activated": "Abonelik aktifleştirildi",
  "billing.subscription_failed": "Abonelik ödemesi başarısız",
  "billing.addon_granted": "Ek paket tanımlandı",
  "billing.addon_granted_dev": "Ek paket tanımlandı (dev)",
  "billing.addon_failed": "Ek paket ödemesi başarısız",
  "billing.subscription_canceled": "Abonelik iptal edildi",
  "billing.manual_upgrade": "Manuel plan yükseltme",
  "document.uploaded": "Belge yüklendi",
  "document.deleted": "Belge silindi",
  "feedback.updated": "Geri bildirim güncellendi",
  "beta.invited": "Beta davet gönderildi",
};

function humanize(action: string): string {
  if (ACTION_LABEL[action]) return ACTION_LABEL[action];
  // Bilinmeyen: "x.y_z" → "X y z"
  const t = action.replace(/[._]/g, " ").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function kullaniciEtiket(l: Log): string {
  if (l.user_email) return l.user_email;
  if (l.user_name) return l.user_name;
  if (l.user_id) return l.user_id.slice(0, 8) + "…";
  return "Sistem";
}

export function AuditPanel() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const qs = actionFilter ? `?action=${encodeURIComponent(actionFilter)}` : "";
      const r = await fetch(`/api/proxy/admin/audit-log${qs}`);
      const j = await r.json();
      if (r.ok) setLogs(j.data.logs || []);
    } finally { setLoading(false); }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-4 flex gap-2">
          <Input
            placeholder="İşlem koduyla filtrele (örn: login, billing.subscription_activated)"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
          />
          <Button onClick={load} disabled={loading}>Ara</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-left border-b bg-muted/30 text-xs">
              <tr>
                <th className="p-2">Tarih</th>
                <th className="p-2">İşlem</th>
                <th className="p-2">Kullanıcı</th>
                <th className="p-2">IP</th>
                <th className="p-2">Sonuç</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="p-2 whitespace-nowrap text-xs text-muted-foreground">
                    {new Date(l.created_at).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" })}
                  </td>
                  <td className="p-2">
                    <div className="font-medium">{humanize(l.action)}</div>
                    <div className="text-[10px] font-mono text-muted-foreground" title={l.action}>
                      {l.action}{l.resource ? ` · ${l.resource}` : ""}
                    </div>
                  </td>
                  <td className="p-2">
                    <span className={l.user_email || l.user_name ? "" : "text-muted-foreground italic"}>
                      {kullaniciEtiket(l)}
                    </span>
                  </td>
                  <td className="p-2 font-mono text-xs text-muted-foreground">{l.ip_address || "—"}</td>
                  <td className="p-2">
                    {l.success ? (
                      <span className="text-emerald-600">✓ Başarılı</span>
                    ) : (
                      <span className="text-destructive">✗ Başarısız</span>
                    )}
                  </td>
                </tr>
              ))}
              {logs.length === 0 && !loading && (
                <tr><td colSpan={5} className="p-8 text-center text-muted-foreground">Kayıt yok</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
