"use client";
/**
 * NPS mini anketi — sağ altta küçük, kapatılabilir kart.
 * Yalnızca uygun kullanıcılara gösterilir (GET /api/proxy/feedback/nps/eligible:
 * kayıt >= 7 gün + henüz yanıt yok). Kapatma localStorage'da 30 gün saklanır
 * (anahtar: nps_dismissed). Gönderim: POST /api/proxy/feedback/nps.
 */
import { useEffect, useState } from "react";
import { Loader2, Send, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const DISMISS_KEY = "nps_dismissed";
const DISMISS_SURE_MS = 30 * 24 * 60 * 60 * 1000; // 30 gün

function sonradanErtelendiMi(): boolean {
  try {
    const v = localStorage.getItem(DISMISS_KEY);
    if (!v) return false;
    const t = parseInt(v, 10);
    if (isNaN(t)) return false;
    return Date.now() - t < DISMISS_SURE_MS;
  } catch {
    return false;
  }
}

function ertele() {
  try {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  } catch {
    /* yok say */
  }
}

export function NpsAnket() {
  const [gorunur, setGorunur] = useState(false);
  const [skor, setSkor] = useState<number | null>(null);
  const [yorum, setYorum] = useState("");
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [tesekkur, setTesekkur] = useState(false);

  useEffect(() => {
    if (sonradanErtelendiMi()) return;
    let alive = true;
    (async () => {
      try {
        const r = await fetch("/api/proxy/feedback/nps/eligible", { cache: "no-store" });
        if (!r.ok) return;
        const j = await r.json();
        if (alive && (j?.data ?? j)?.eligible === true) setGorunur(true);
      } catch {
        /* yok say */
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  function kapat() {
    ertele();
    setGorunur(false);
  }

  async function gonder() {
    if (skor === null) return;
    setGonderiliyor(true);
    try {
      const r = await fetch("/api/proxy/feedback/nps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score: skor, comment: yorum.trim() || null }),
      });
      if (r.ok) {
        ertele();
        setTesekkur(true);
        setTimeout(() => setGorunur(false), 2500);
      }
    } catch {
      /* yok say */
    } finally {
      setGonderiliyor(false);
    }
  }

  if (!gorunur) return null;

  return (
    <div className="fixed bottom-20 right-5 z-40 w-[360px] max-w-[calc(100vw-2rem)] rounded-lg border bg-background p-4 shadow-2xl">
      {tesekkur ? (
        <div className="py-4 text-center">
          <div className="text-3xl mb-1">✓</div>
          <p className="font-semibold">Teşekkürler!</p>
          <p className="text-sm text-muted-foreground mt-1">Görüşünüz bizim için çok değerli.</p>
        </div>
      ) : (
        <>
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium leading-snug">
              Hukuk Emsal&apos;i bir meslektaşınıza tavsiye etme olasılığınız?
            </p>
            <button
              onClick={kapat}
              aria-label="Kapat"
              className="shrink-0 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-3 grid grid-cols-11 gap-1">
            {Array.from({ length: 11 }).map((_, i) => (
              <button
                key={i}
                onClick={() => setSkor(i)}
                className={`h-8 rounded text-xs font-medium transition-colors ${
                  skor === i
                    ? "bg-primary text-primary-foreground"
                    : "border bg-secondary/50 text-foreground hover:bg-secondary"
                }`}
                aria-label={`${i} puan`}
              >
                {i}
              </button>
            ))}
          </div>
          <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
            <span>Hiç olası değil</span>
            <span>Kesinlikle tavsiye ederim</span>
          </div>

          {skor !== null && (
            <div className="mt-3 space-y-2">
              <Textarea
                rows={2}
                placeholder="Eklemek istediğiniz bir şey var mı? (opsiyonel)"
                value={yorum}
                onChange={(e) => setYorum(e.target.value)}
              />
              <Button onClick={gonder} disabled={gonderiliyor} size="sm" className="w-full">
                {gonderiliyor ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Send className="mr-2 h-4 w-4" />
                )}
                Gönder
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
