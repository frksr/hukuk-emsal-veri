"use client";
import { useEffect, useState } from "react";
import { Loader2, BarChart3, Info } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { trendYillik } from "@/lib/api";

const COLORS = ["#1e3a5f", "#c9a961", "#5b8fb9", "#a47148", "#7a9b76"];

export function TrendPanel() {
  const [konu, setKonu] = useState("");
  const [kaynak, setKaynak] = useState("");
  const [yillik, setYillik] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchData() {
      setLoading(true); setError(null);
      try {
        const params = new URLSearchParams();
        if (konu) params.append("konu_filtresi", konu);
        if (kaynak) params.append("kaynak", kaynak);
        const data = await trendYillik(params.toString());
        if (!cancelled) setYillik(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Hata");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchData();
    return () => { cancelled = true; };
  }, [konu, kaynak]);

  // Veri normalize — backend formatı: {data: [[yıl, sayı], ...], total: N}
  const chartData = Array.isArray(yillik?.data)
    ? yillik.data.map((r: any) => Array.isArray(r) ? { yil: r[0], sayi: r[1] } : r)
    : [];

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="p-4 flex flex-wrap gap-3 items-end">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Konu</label>
            <select value={konu} onChange={(e) => setKonu(e.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
              <option value="">Tümü</option>
              <option>icra</option><option>tahsilat</option><option>ihtar</option><option>haciz</option>
              <option>ödeme emri</option><option>kambiyo</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Kaynak</label>
            <select value={kaynak} onChange={(e) => setKaynak(e.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
              <option value="">Tümü</option>
              <option value="yargitay">Yargıtay</option>
              <option value="danistay">Danıştay</option>
              <option value="hudoc">HUDOC</option>
            </select>
          </div>
          <div className="flex-1" />
          {yillik?.total !== undefined && (
            <div className="text-sm text-muted-foreground">
              Toplam: <span className="font-bold text-foreground">{yillik.total.toLocaleString("tr-TR")}</span> karar
            </div>
          )}
        </CardContent>
      </Card>

      {/* Ne gösteriyoruz — bağlam açıklaması */}
      <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground flex gap-3">
        <Info className="h-5 w-5 shrink-0 mt-0.5 text-primary" />
        <div className="space-y-1">
          <p>
            Bu panel, <strong>veritabanındaki emsal kararların yıllara göre dağılımını</strong> gösterir
            — yani hangi yıl kaç karar bulunduğunu. Üstteki <strong>Konu</strong> ve <strong>Kaynak</strong>{" "}
            filtreleriyle (örn. yalnızca &quot;icra&quot; konusu veya yalnızca Yargıtay) daralabilirsiniz.
          </p>
          <p>
            Soldaki <strong>bar grafik</strong> tüm yılların karar sayısını; sağdaki <strong>pasta</strong>{" "}
            en çok karar bulunan ilk 5 yılın payını gösterir. Sayılar, sistemdeki kararların{" "}
            <em>karar tarihine</em> göre gruplanmasıyla hesaplanır.
          </p>
          {yillik?.dummy && (
            <p className="text-amber-700 dark:text-amber-400">
              ⚠️ Şu an <strong>örnek (demo) veri</strong> gösteriliyor — veritabanında tarihli karar
              bulunamadı. Gerçek kararlar yüklendiğinde grafik otomatik güncellenir.
            </p>
          )}
        </div>
      </div>

      {error && <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">⚠️ {error}</div>}

      {loading && (
        <Card><CardContent className="p-12 text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
        </CardContent></Card>
      )}

      {!loading && chartData.length > 0 && (
        <div className="grid lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Yıllık Karar Dağılımı</CardTitle>
              <CardDescription>Her yıl için veritabanındaki karar sayısı (karar tarihine göre).</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={350}>
                <BarChart data={chartData}>
                  <XAxis dataKey="yil" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="sayi" fill="#1e3a5f" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Top 5 Yıl</CardTitle>
              <CardDescription>En çok karar bulunan ilk 5 yılın toplam içindeki payı.</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={350}>
                <PieChart>
                  <Pie data={chartData.slice(0, 5)} dataKey="sayi" nameKey="yil" label>
                    {chartData.slice(0, 5).map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}

      {!loading && chartData.length === 0 && (
        <Card><CardContent className="p-8 text-center text-muted-foreground">
          <BarChart3 className="h-12 w-12 mx-auto mb-3 opacity-30" />
          Veri yüklenemedi. Backend çalışıyor mu kontrol edin.
        </CardContent></Card>
      )}
    </div>
  );
}
