"use client";
import { useEffect, useState } from "react";
import { Users, Download, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const PLAN_LABEL: Record<string, string> = {
  pro_solo: "Pro Solo",
  pro_solo_uyap: "Pro + UYAP",
  team: "Team",
};

type Entry = {
  id: string;
  name: string;
  email: string;
  plan: string | null;
  created_at: string;
};

export function BeklemListesiPanel() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const r = await fetch("/api/proxy/waitlist/admin");
      const j = await r.json();
      if (r.ok) {
        setEntries(j.data.entries ?? []);
        setTotal(j.data.total ?? 0);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function exportCsv() {
    const rows = [
      ["Ad Soyad", "E-posta", "Plan", "Kayıt Tarihi"],
      ...entries.map((e) => [
        e.name,
        e.email,
        e.plan ? (PLAN_LABEL[e.plan] ?? e.plan) : "-",
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

  // Plan dağılımı
  const planDist = entries.reduce<Record<string, number>>((acc, e) => {
    const k = e.plan ?? "belirtilmedi";
    acc[k] = (acc[k] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {/* Özet kartları */}
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
        {Object.entries(planDist).map(([plan, count]) => (
          <Card key={plan}>
            <CardContent className="p-4">
              <div className="text-2xl font-bold">{count}</div>
              <div className="text-xs text-muted-foreground">
                {PLAN_LABEL[plan] ?? plan}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tablo araçları */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-base">Kayıt Listesi</CardTitle>
            <div className="flex gap-2">
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
              Henüz kayıt yok.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">#</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Ad Soyad</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">E-posta</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Plan</th>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">Kayıt Tarihi</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e, i) => (
                    <tr key={e.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="px-4 py-2.5 text-muted-foreground">{i + 1}</td>
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
