"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { History, StickyNote, Search, ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const TOOL_LABEL: Record<string, string> = {
  dilekce: "Dilekçe", ihtarname: "İhtarname", ozet: "Karar Özeti",
  denetim: "Belge Denetimi", karsi_argument: "Karşı Argüman", sozlesme: "Sözleşme Analizi",
};

async function getData<T>(path: string): Promise<T[]> {
  try {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) return [];
    const j = await r.json();
    const d = j?.data ?? j;
    return (d?.uretimler ?? d?.notlar ?? d?.searches ?? []) as T[];
  } catch {
    return [];
  }
}

export function WorkspacePanel() {
  const [uretimler, setUretimler] = useState<any[]>([]);
  const [notlar, setNotlar] = useState<any[]>([]);
  const [aramalar, setAramalar] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [u, n, a] = await Promise.all([
        getData<any>("/api/proxy/me/uretimler?limit=6"),
        getData<any>("/api/proxy/notlar/?limit=6"),
        getData<any>("/api/proxy/me/searches?limit=6"),
      ]);
      if (!alive) return;
      setUretimler(u); setNotlar(n); setAramalar(a);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, []);

  const tarih = (s: string) => new Date(s).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });

  if (loading) {
    return (
      <div className="grid lg:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <Card key={i}>
            <CardHeader><Skeleton className="h-5 w-32" /></CardHeader>
            <CardContent className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-4/5" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid lg:grid-cols-3 gap-4 stagger">
      {/* Son üretimler */}
      <Card className="hover-lift">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base flex items-center gap-2"><History className="h-4 w-4 text-primary" /> Son Üretimlerim</CardTitle>
          <Link href="/app/gecmis" className="text-xs text-primary hover:underline flex items-center gap-0.5">Tümü <ArrowRight className="h-3 w-3" /></Link>
        </CardHeader>
        <CardContent className="space-y-2">
          {uretimler.length === 0 ? (
            <p className="text-sm text-muted-foreground">Henüz üretim yok. <Link href="/dilekce" className="text-primary underline">Dilekçe üret</Link></p>
          ) : uretimler.map((u) => (
            <Link key={u.id} href="/app/gecmis" className="block rounded-md border p-2 hover:bg-secondary text-sm">
              <div className="font-medium truncate">{u.baslik || TOOL_LABEL[u.tool] || u.tool}</div>
              <div className="text-xs text-muted-foreground">{TOOL_LABEL[u.tool] || u.tool} · {tarih(u.created_at)}</div>
            </Link>
          ))}
        </CardContent>
      </Card>

      {/* Notlar */}
      <Card className="hover-lift">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base flex items-center gap-2"><StickyNote className="h-4 w-4 text-primary" /> Notlarım</CardTitle>
          <Link href="/app/notlar" className="text-xs text-primary hover:underline flex items-center gap-0.5">Tümü <ArrowRight className="h-3 w-3" /></Link>
        </CardHeader>
        <CardContent className="space-y-2">
          {notlar.length === 0 ? (
            <p className="text-sm text-muted-foreground">Henüz not yok. <Link href="/app/notlar" className="text-primary underline">Not ekle</Link></p>
          ) : notlar.map((n) => (
            <Link key={n.id} href="/app/notlar" className="block rounded-md border p-2 hover:bg-secondary text-sm">
              <div className="font-medium truncate">{n.baslik || "Not"}</div>
              <div className="text-xs text-muted-foreground truncate">{n.icerik}</div>
            </Link>
          ))}
        </CardContent>
      </Card>

      {/* Son aramalar */}
      <Card className="hover-lift">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base flex items-center gap-2"><Search className="h-4 w-4 text-primary" /> Son Aramalarım</CardTitle>
          <Link href="/emsal-arama" className="text-xs text-primary hover:underline flex items-center gap-0.5">Ara <ArrowRight className="h-3 w-3" /></Link>
        </CardHeader>
        <CardContent className="space-y-2">
          {aramalar.length === 0 ? (
            <p className="text-sm text-muted-foreground">Henüz arama yok. <Link href="/emsal-arama" className="text-primary underline">Emsal ara</Link></p>
          ) : aramalar.map((a) => (
            <Link key={a.id} href={`/emsal-arama`} className="block rounded-md border p-2 hover:bg-secondary text-sm">
              <div className="truncate">{a.query}</div>
              <div className="text-xs text-muted-foreground">{a.result_count ?? 0} sonuç · {tarih(a.created_at)}</div>
            </Link>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
