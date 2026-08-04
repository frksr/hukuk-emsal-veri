"use client";
import { useCallback, useEffect, useState } from "react";
import { Mail, RefreshCw, Search, UserX, Ban, RotateCcw, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfirm } from "@/components/confirm-dialog";

const DURUM_LABEL: Record<string, string> = {
  active: "Aktif",
  unsubscribed: "Abonelikten Çıktı",
  blocked: "Engellendi",
};

const DURUM_STIL: Record<string, string> = {
  active: "bg-emerald-400/15 text-emerald-700 dark:text-emerald-300 border border-emerald-400/40",
  unsubscribed: "bg-muted text-muted-foreground",
  blocked: "bg-red-400/15 text-red-700 dark:text-red-300 border border-red-400/40",
};

type Entry = {
  id: string;
  email: string;
  status: string;
  has_account: boolean;
  consent_at: string | null;
  unsubscribed_at: string | null;
  blocked_at: string | null;
  blocked_reason: string | null;
  last_sent_at: string | null;
  created_at: string;
};

export function BultenPanel() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [total, setTotal] = useState(0);
  const [durumlar, setDurumlar] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [mesaj, setMesaj] = useState<string | null>(null);
  const [durum, setDurum] = useState("");
  const [arama, setArama] = useState("");
  const [isleniyor, setIsleniyor] = useState<string | null>(null);
  const { confirm, dialog } = useConfirm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (durum) params.set("status", durum);
      if (arama.trim()) params.set("arama", arama.trim());
      const r = await fetch(`/api/proxy/newsletter/admin?${params}`);
      const j = await r.json();
      if (r.ok) {
        setEntries(j.data.entries ?? []);
        setTotal(j.data.total ?? 0);
        setDurumlar(j.data.durumlar ?? {});
      }
    } finally {
      setLoading(false);
    }
  }, [durum, arama]);

  useEffect(() => { load(); }, [load]);

  async function unsubscribe(e: Entry) {
    const onay = await confirm(
      `${e.email} adresi bültenden çıkarılacak. Devam edilsin mi?`,
      { title: "Abonelikten Çıkar", confirmText: "Çıkar" },
    );
    if (!onay) return;
    setIsleniyor(e.id);
    try {
      const r = await fetch(`/api/proxy/newsletter/admin/${e.id}/unsubscribe`, { method: "POST" });
      const j = await r.json();
      setMesaj(j?.message ?? null);
      await load();
    } finally {
      setIsleniyor(null);
    }
  }

  async function block(e: Entry) {
    const onay = await confirm(
      `${e.email} adresine bülten gönderimi kalıcı olarak engellenecek. Devam edilsin mi?`,
      { title: "Gönderimi Engelle", confirmText: "Engelle", danger: true },
    );
    if (!onay) return;
    const reason = window.prompt("Engelleme nedeni (isteğe bağlı):", "") ?? "";
    setIsleniyor(e.id);
    try {
      const r = await fetch(`/api/proxy/newsletter/admin/${e.id}/block`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: reason.trim() || null }),
      });
      const j = await r.json();
      setMesaj(j?.message ?? null);
      await load();
    } finally {
      setIsleniyor(null);
    }
  }

  async function reactivate(e: Entry) {
    const onay = await confirm(
      `${e.email} tekrar aktif edilecek ve bültene devam edecek. Devam edilsin mi?`,
      { title: "Tekrar Aktif Et", confirmText: "Aktif Et" },
    );
    if (!onay) return;
    setIsleniyor(e.id);
    try {
      const r = await fetch(`/api/proxy/newsletter/admin/${e.id}/reactivate`, { method: "POST" });
      const j = await r.json();
      setMesaj(j?.message ?? null);
      await load();
    } finally {
      setIsleniyor(null);
    }
  }

  return (
    <div className="space-y-6">
      {dialog}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Users className="h-8 w-8 text-primary shrink-0" />
            <div>
              <div className="text-2xl font-bold">{total}</div>
              <div className="text-xs text-muted-foreground">Toplam abone</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Mail className="h-8 w-8 text-emerald-500 shrink-0" />
            <div>
              <div className="text-2xl font-bold">{durumlar.active ?? 0}</div>
              <div className="text-xs text-muted-foreground">Aktif</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <UserX className="h-8 w-8 text-muted-foreground/50 shrink-0" />
            <div>
              <div className="text-2xl font-bold">{durumlar.unsubscribed ?? 0}</div>
              <div className="text-xs text-muted-foreground">Çıkış yaptı</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Ban className="h-8 w-8 text-red-500 shrink-0" />
            <div>
              <div className="text-2xl font-bold">{durumlar.blocked ?? 0}</div>
              <div className="text-xs text-muted-foreground">Engellendi</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {mesaj && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
          {mesaj}
        </div>
      )}

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-base">Bülten Aboneleri</CardTitle>
            <Button variant="outline" size="sm" onClick={load} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-1 ${loading ? "animate-spin" : ""}`} />
              Yenile
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                className="h-8 pl-8 w-56 text-sm"
                placeholder="E-posta ara…"
                value={arama}
                onChange={(e) => setArama(e.target.value)}
              />
            </div>
            <select
              className="h-8 rounded-md border border-input bg-background px-2 text-sm"
              value={durum}
              onChange={(e) => setDurum(e.target.value)}
            >
              <option value="">Tüm durumlar</option>
              <option value="active">Aktif</option>
              <option value="unsubscribed">Abonelikten çıktı</option>
              <option value="blocked">Engellendi</option>
            </select>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-10 rounded bg-muted animate-pulse" />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">
              Filtreye uyan kayıt yok.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">E-posta</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Durum</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Son Bildirim</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Kayıt Tarihi</th>
                    <th className="text-right px-4 py-2 font-medium text-muted-foreground">İşlemler</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr key={e.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="px-4 py-2.5 font-medium">
                        {e.email}
                        {e.has_account && (
                          <span className="ml-1.5 text-xs text-muted-foreground">(hesaplı)</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${DURUM_STIL[e.status] ?? ""}`}>
                          {DURUM_LABEL[e.status] ?? e.status}
                        </span>
                        {e.status === "blocked" && e.blocked_reason && (
                          <div className="mt-0.5 text-xs text-muted-foreground">{e.blocked_reason}</div>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground text-xs">
                        {e.last_sent_at ? new Date(e.last_sent_at).toLocaleDateString("tr-TR") : "—"}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {new Date(e.created_at).toLocaleDateString("tr-TR")}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex justify-end gap-1.5">
                          {e.status === "active" && (
                            <>
                              <Button
                                size="sm" variant="outline"
                                disabled={isleniyor === e.id}
                                onClick={() => unsubscribe(e)}
                              >
                                <UserX className="h-3.5 w-3.5 mr-1" />
                                Çıkar
                              </Button>
                              <Button
                                size="sm" variant="destructive"
                                disabled={isleniyor === e.id}
                                onClick={() => block(e)}
                              >
                                <Ban className="h-3.5 w-3.5 mr-1" />
                                Engelle
                              </Button>
                            </>
                          )}
                          {e.status !== "active" && (
                            <Button
                              size="sm" variant="outline"
                              disabled={isleniyor === e.id}
                              onClick={() => reactivate(e)}
                            >
                              <RotateCcw className="h-3.5 w-3.5 mr-1" />
                              Tekrar Aktif Et
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
