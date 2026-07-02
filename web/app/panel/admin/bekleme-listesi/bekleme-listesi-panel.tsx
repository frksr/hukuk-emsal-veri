"use client";
import { useCallback, useEffect, useState } from "react";
import { Users, Download, RefreshCw, Send, Loader2, Search, MailCheck, UserCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfirm } from "@/components/confirm-dialog";

const PLAN_LABEL: Record<string, string> = {
  pro_solo: "Pro Solo",
  pro_solo_uyap: "Pro + UYAP",
  team: "Team",
};

const DURUM_LABEL: Record<string, string> = {
  bekliyor: "Bekliyor",
  davet_edildi: "Davet Edildi",
  kayit_oldu: "Kayıt Oldu",
};

const DURUM_STIL: Record<string, string> = {
  bekliyor: "bg-muted text-muted-foreground",
  davet_edildi: "bg-amber-400/15 text-amber-700 dark:text-amber-300 border border-amber-400/40",
  kayit_oldu: "bg-emerald-400/15 text-emerald-700 dark:text-emerald-300 border border-emerald-400/40",
};

type Entry = {
  id: string;
  name: string;
  email: string;
  plan: string | null;
  status: string;
  invited_at: string | null;
  invite_code: string | null;
  created_at: string;
};

export function BeklemListesiPanel() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [total, setTotal] = useState(0);
  const [durumlar, setDurumlar] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [mesaj, setMesaj] = useState<string | null>(null);
  // Filtreler
  const [plan, setPlan] = useState("");
  const [durum, setDurum] = useState("");
  const [arama, setArama] = useState("");
  // Çoklu seçim + davet
  const [secili, setSecili] = useState<Set<string>>(new Set());
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const { confirm, dialog } = useConfirm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (plan) params.set("plan", plan);
      if (durum) params.set("status", durum);
      if (arama.trim()) params.set("arama", arama.trim());
      const r = await fetch(`/api/proxy/waitlist/admin?${params}`);
      const j = await r.json();
      if (r.ok) {
        setEntries(j.data.entries ?? []);
        setTotal(j.data.total ?? 0);
        setDurumlar(j.data.durumlar ?? {});
      }
    } finally {
      setLoading(false);
    }
  }, [plan, durum, arama]);

  useEffect(() => { load(); }, [load]);

  function toggleSec(id: string) {
    setSecili((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  // Davet edilebilirler: kayıt olmamış herkes (tekrar davet = aynı link)
  const davetEdilebilir = entries.filter((e) => e.status !== "kayit_oldu");
  const tumunuSec = () => {
    setSecili((s) =>
      s.size === davetEdilebilir.length
        ? new Set()
        : new Set(davetEdilebilir.map((e) => e.id)),
    );
  };

  async function davetGonder() {
    if (secili.size === 0) return;
    const onay = await confirm(
      `${secili.size} kişiye erken erişim davet e-postası gönderilecek. Devam edilsin mi?`,
      { title: "Davet Gönder", confirmText: "Gönder" },
    );
    if (!onay) return;
    setGonderiliyor(true);
    setMesaj(null);
    try {
      const r = await fetch("/api/proxy/waitlist/admin/davet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: Array.from(secili) }),
      });
      const j = await r.json();
      setMesaj(j?.message || (r.ok ? "Davetler gönderildi." : "Davet gönderilemedi."));
      setSecili(new Set());
      await load();
    } catch {
      setMesaj("Davet gönderimi sırasında hata oluştu.");
    } finally {
      setGonderiliyor(false);
    }
  }

  function exportCsv() {
    const rows = [
      ["Ad Soyad", "E-posta", "Plan", "Durum", "Davet Tarihi", "Kayıt Tarihi"],
      ...entries.map((e) => [
        e.name,
        e.email,
        e.plan ? (PLAN_LABEL[e.plan] ?? e.plan) : "-",
        DURUM_LABEL[e.status] ?? e.status,
        e.invited_at ? new Date(e.invited_at).toLocaleString("tr-TR") : "-",
        new Date(e.created_at).toLocaleString("tr-TR"),
      ]),
    ];
    const csv = rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bekleme-listesi-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      {dialog}
      {/* Özet kartları — dönüşüm hunisi */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Users className="h-8 w-8 text-primary shrink-0" />
            <div>
              <div className="text-2xl font-bold">{total}</div>
              <div className="text-xs text-muted-foreground">Toplam kayıt</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Users className="h-8 w-8 text-muted-foreground/50 shrink-0" />
            <div>
              <div className="text-2xl font-bold">{durumlar.bekliyor ?? 0}</div>
              <div className="text-xs text-muted-foreground">Bekliyor</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <MailCheck className="h-8 w-8 text-amber-500 shrink-0" />
            <div>
              <div className="text-2xl font-bold">{durumlar.davet_edildi ?? 0}</div>
              <div className="text-xs text-muted-foreground">Davet edildi</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <UserCheck className="h-8 w-8 text-emerald-500 shrink-0" />
            <div>
              <div className="text-2xl font-bold">{durumlar.kayit_oldu ?? 0}</div>
              <div className="text-xs text-muted-foreground">Kayıt oldu</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {mesaj && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
          {mesaj}
        </div>
      )}

      {/* Tablo araçları */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-base">Kayıt Listesi</CardTitle>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={davetGonder}
                disabled={secili.size === 0 || gonderiliyor}
              >
                {gonderiliyor ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : (
                  <Send className="h-4 w-4 mr-1" />
                )}
                Davet Gönder{secili.size > 0 ? ` (${secili.size})` : ""}
              </Button>
              <Button variant="outline" size="sm" onClick={load} disabled={loading}>
                <RefreshCw className={`h-4 w-4 mr-1 ${loading ? "animate-spin" : ""}`} />
                Yenile
              </Button>
              <Button variant="outline" size="sm" onClick={exportCsv} disabled={entries.length === 0}>
                <Download className="h-4 w-4 mr-1" />
                CSV İndir
              </Button>
            </div>
          </div>
          {/* Filtreler */}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                className="h-8 pl-8 w-56 text-sm"
                placeholder="İsim veya e-posta ara…"
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
              <option value="bekliyor">Bekliyor</option>
              <option value="davet_edildi">Davet edildi</option>
              <option value="kayit_oldu">Kayıt oldu</option>
            </select>
            <select
              className="h-8 rounded-md border border-input bg-background px-2 text-sm"
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
            >
              <option value="">Tüm planlar</option>
              <option value="pro_solo">Pro Solo</option>
              <option value="pro_solo_uyap">Pro + UYAP</option>
              <option value="team">Team</option>
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
                    <th className="px-4 py-2">
                      <input
                        type="checkbox"
                        checked={davetEdilebilir.length > 0 && secili.size === davetEdilebilir.length}
                        onChange={tumunuSec}
                        title="Tümünü seç (kayıt olmamışlar)"
                      />
                    </th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Ad Soyad</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">E-posta</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Plan</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Durum</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Davet</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Kayıt Tarihi</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr key={e.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="px-4 py-2.5">
                        <input
                          type="checkbox"
                          checked={secili.has(e.id)}
                          onChange={() => toggleSec(e.id)}
                          disabled={e.status === "kayit_oldu"}
                        />
                      </td>
                      <td className="px-4 py-2.5 font-medium">{e.name}</td>
                      <td className="px-4 py-2.5">
                        <a href={`mailto:${e.email}`} className="text-primary hover:underline">
                          {e.email}
                        </a>
                      </td>
                      <td className="px-4 py-2.5">
                        {e.plan ? (
                          <span className="bg-primary/10 text-primary text-xs px-2 py-0.5 rounded-full">
                            {PLAN_LABEL[e.plan] ?? e.plan}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${DURUM_STIL[e.status] ?? DURUM_STIL.bekliyor}`}>
                          {DURUM_LABEL[e.status] ?? e.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground text-xs">
                        {e.invited_at ? new Date(e.invited_at).toLocaleDateString("tr-TR") : "—"}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {new Date(e.created_at).toLocaleString("tr-TR")}
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
