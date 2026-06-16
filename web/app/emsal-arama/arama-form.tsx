"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, Loader2, ExternalLink, Star, FileText, Scale, Bell, BellRing } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { alarmOlustur, aramaCagir, aramaStats, kararKaydet, type EmsalKarar } from "@/lib/api";
import { usePlan, actionGateHref } from "@/lib/use-plan";
import { useKayitDavet } from "@/components/kayit-davet";
import { NotHatirlatma } from "@/components/not-hatirlatma";

// Son arama anlık görüntüsü — modül seviyesinde tutulur.
// SPA içinde gezinmede (karara gidip geri gelince) KORUNUR,
// tam sayfa yenilemede (F5) modül yeniden yüklendiği için SIFIRLANIR.
type AramaSnapshot = {
  query: string;
  source: string;
  chamber: string;
  k: number;
  results: EmsalKarar[];
};
let sonArama: AramaSnapshot | null = null;

export function AramaForm() {
  const router = useRouter();
  const plan = usePlan();
  const { davetGoster, dialog: kayitDialog } = useKayitDavet();
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<string>("");
  const [chamber, setChamber] = useState<string>("");
  const [k, setK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<EmsalKarar[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dbHazirDegil, setDbHazirDegil] = useState(false);
  const [kaydedilenler, setKaydedilenler] = useState<Set<string>>(new Set());
  const [kayitMesaj, setKayitMesaj] = useState<string | null>(null);
  const [takipte, setTakipte] = useState(false);

  // Bir karara gidip geri gelince son aramayı geri yükle.
  // (Modül değişkeni tam sayfa yenilemede sıfırlandığı için F5'te temiz başlar.)
  useEffect(() => {
    if (!sonArama) return;
    setQuery(sonArama.query);
    setSource(sonArama.source);
    setChamber(sonArama.chamber);
    setK(sonArama.k);
    setResults(sonArama.results);
  }, []);

  async function handleTakip() {
    try {
      await alarmOlustur({
        query,
        filters: { source: source || null, court_chamber: chamber || null },
      });
      setTakipte(true);
      setKayitMesaj(null);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 401 || status === 403) {
        setKayitMesaj("Aramayı takip etmek için ücretsiz hesap açın — yeni emsal çıkınca e-posta alırsınız.");
      } else {
        setKayitMesaj(err instanceof Error ? err.message : "Takip hatası.");
      }
    }
  }

  // Koleksiyon hazır mı? (seed edilmemişse kullanıcıya açıkla)
  useEffect(() => {
    aramaStats()
      .then((s) => setDbHazirDegil(!s?.data?.available))
      .catch(() => {
        /* stats erişilemiyorsa banner gösterme — arama yine denenir */
      });
  }, []);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    // Kullanmak için kayıt şart (ücretsiz). Girişsiz → kayıt sayfasına.
    const gate = actionGateHref(plan, false);
    if (gate === "/kayit") { davetGoster(); return; }
    if (gate) { router.push(gate); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await aramaCagir({ query, k, source: source || null, court_chamber: chamber || null });
      setResults(data);
      sonArama = { query, source, chamber, k, results: data };
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
      setResults(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleKaydet(r: EmsalKarar) {
    const key = r.chunk_id;
    try {
      await kararKaydet({
        decision_id: r.decision_id || r.chunk_id,
        chunk_id: r.chunk_id,
        baslik: `${r.court_chamber || "?"} · ${r.case_no || "?"} → ${r.decision_no || "?"}`,
        ozet: (r.text || "").slice(0, 2000),
        meta: {
          source: r.source,
          court_chamber: r.court_chamber,
          case_no: r.case_no,
          decision_no: r.decision_no,
          decision_date: r.decision_date,
          source_url: r.source_url,
        },
      });
      setKaydedilenler((prev) => new Set(prev).add(key));
      setKayitMesaj(null);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 401 || status === 403) {
        setKayitMesaj("Kararları kaydetmek için ücretsiz hesap açın — kayıtlar dava dosyanıza göre klasörlenir.");
      } else {
        setKayitMesaj(err instanceof Error ? err.message : "Kaydetme hatası.");
      }
    }
  }

  return (
    <div className="space-y-6">
      {kayitDialog}
      {dbHazirDegil && (
        <div className="rounded-lg border border-amber-400/50 bg-amber-50 dark:bg-amber-950/30 p-4 text-sm text-amber-800 dark:text-amber-200">
          Karar veritabanı şu anda hazırlanıyor (indeksleme devam ediyor). Arama
          sonuçları eksik veya boş dönebilir — kısa süre sonra tekrar deneyin.
        </div>
      )}

      <form onSubmit={handleSearch} className="space-y-4">
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Örn: İcra takibinde emekli maaşının haczi"
            className="flex-1 h-12 text-base"
            aria-label="Arama sorgusu"
          />
          <Button type="submit" size="lg" disabled={loading || !query.trim()}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            <span className="ml-2">Ara</span>
          </Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <select value={source} onChange={(e) => setSource(e.target.value)} className="h-10 rounded-md border bg-background px-3">
            <option value="">Tüm Kaynaklar</option>
            <option value="yargitay">Yargıtay</option>
            <option value="danistay">Danıştay</option>
            <option value="hudoc">HUDOC (AİHM)</option>
          </select>
          <select value={chamber} onChange={(e) => setChamber(e.target.value)} className="h-10 rounded-md border bg-background px-3">
            <option value="">Tüm Daireler</option>
            <option>12. Hukuk Dairesi</option>
            <option>8. Hukuk Dairesi</option>
            <option>13. Hukuk Dairesi</option>
            <option>19. Hukuk Dairesi</option>
            <option>3. Daire</option>
            <option>9. Daire</option>
            <option>Vergi Dava Daireleri Kurulu</option>
            <option>İdare Dava Daireleri Kurulu</option>
          </select>
          <select value={k} onChange={(e) => setK(Number(e.target.value))} className="h-10 rounded-md border bg-background px-3">
            {[5, 10, 15, 20].map((n) => <option key={n} value={n}>{n} sonuç</option>)}
          </select>
        </div>
      </form>

      <NotHatirlatma q={query} />

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          ⚠️ {error}
        </div>
      )}

      {kayitMesaj && (
        <div className="rounded-lg border border-primary/40 bg-primary/5 p-4 text-sm flex items-center justify-between gap-3">
          <span>{kayitMesaj}</span>
          <Button asChild size="sm" variant="outline">
            <Link href="/kayit">Ücretsiz Kayıt</Link>
          </Button>
        </div>
      )}

      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 rounded-lg border bg-muted/30 animate-pulse" />
          ))}
        </div>
      )}

      {results && results.length === 0 && !loading && (
        <div className="text-center py-12 text-muted-foreground">
          Bu sorguya uyan emsal karar bulunamadı. Daha geniş bir arama deneyin.
        </div>
      )}

      {results && results.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="text-sm text-muted-foreground">{results.length} emsal karar bulundu.</div>
            <div className="flex gap-2">
              <Button asChild size="sm" variant="outline" title="Bu sorguyla Yapay Zeka dilekçe taslağı oluştur">
                <Link href={`/dilekce?durum=${encodeURIComponent(query)}`}>
                  <FileText className="h-3.5 w-3.5 mr-1.5" /> Bu konuda dilekçe yaz
                </Link>
              </Button>
              <Button asChild size="sm" variant="outline" title="Bu teze karşı argümanları gör">
                <Link href={`/karsi-argument?tez=${encodeURIComponent(query)}`}>
                  <Scale className="h-3.5 w-3.5 mr-1.5" /> Karşı argüman üret
                </Link>
              </Button>
              <Button
                size="sm"
                variant={takipte ? "default" : "outline"}
                onClick={handleTakip}
                disabled={takipte}
                title="Bu konuda yeni emsal çıkınca e-posta al"
              >
                {takipte ? (
                  <><BellRing className="h-3.5 w-3.5 mr-1.5" /> Takipte</>
                ) : (
                  <><Bell className="h-3.5 w-3.5 mr-1.5" /> Takip et</>
                )}
              </Button>
            </div>
          </div>
          {results.map((r, i) => (
            <Card key={r.chunk_id}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h3 className="font-semibold text-base">
                      #{i + 1} — {r.court_chamber || "?"} · {r.case_no || "?"} → {r.decision_no || "?"}
                    </h3>
                    <div className="text-xs text-muted-foreground mt-1">
                      {r.decision_date || ""} · {r.source} · benzerlik: {(r.similarity * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => handleKaydet(r)}
                      title={kaydedilenler.has(r.chunk_id) ? "Kaydedildi" : "Kararı kaydet"}
                      className="text-muted-foreground hover:text-amber-500 transition-colors"
                      aria-label="Kararı kaydet"
                    >
                      <Star
                        className="h-4 w-4"
                        fill={kaydedilenler.has(r.chunk_id) ? "currentColor" : "none"}
                        color={kaydedilenler.has(r.chunk_id) ? "#f59e0b" : undefined}
                      />
                    </button>
                    {r.decision_id && (
                      <Link href={`/karar/${encodeURIComponent(r.decision_id)}`} className="text-xs text-primary hover:underline flex items-center gap-1">
                        Kararı incele <FileText className="h-3 w-3" />
                      </Link>
                    )}
                    {r.source_url && (
                      <a href={r.source_url} target="_blank" rel="noopener noreferrer" title="Resmî kaynak (Yargıtay)" className="text-xs text-muted-foreground hover:underline flex items-center gap-1">
                        Kaynak <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                </div>
                <p className="text-sm text-foreground/80 leading-relaxed line-clamp-4">{r.text}</p>
                {r.topic_tags && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {r.topic_tags.split(",").filter(Boolean).slice(0, 6).map((tag) => (
                      <span key={tag} className="text-xs rounded-full bg-secondary px-2 py-0.5 text-secondary-foreground">
                        {tag.trim()}
                      </span>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
