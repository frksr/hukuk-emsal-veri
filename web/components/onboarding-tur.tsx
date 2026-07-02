"use client";
/**
 * Onboarding turu — panele ilk girişte 4 adımlık tanıtım modalı.
 * Kullanıcı "Geç" ya da son adımda "Başla" dediğinde /api/proxy/me'ye
 * PATCH {onboarding_done: true} atılır ve tur bir daha gösterilmez.
 * (Backend: api/routers/me.py + infra/db/21_onboarding.sql)
 */
import { useEffect, useState } from "react";
import { Search, FileText, Bell, Gem, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const ADIMLAR = [
  {
    icon: Search,
    baslik: "Emsal Arama",
    metin:
      "10.000+ Yargıtay ve Danıştay kararı arasında doğal dille arama yapın. Sonuçları yıldızlayın, klasörleyin, yeni emsal çıkınca e-posta alın.",
  },
  {
    icon: FileText,
    baslik: "AI Dilekçe",
    metin:
      "Olayınızı anlatın; Yapay Zeka emsallere atıflı dilekçe, ihtarname ve karşı argüman taslakları üretsin. Tüm üretimleriniz geçmişinizde saklanır.",
  },
  {
    icon: Bell,
    baslik: "Notlar & Hatırlatıcılar",
    metin:
      "Dosya ve kararlarınıza not ekleyin; itiraz ve zamanaşımı sürelerini e-posta hatırlatıcısıyla asla kaçırmayın.",
  },
  {
    icon: Gem,
    baslik: "Planlar & Limitler",
    metin:
      "Ücretsiz planda her araç için günlük deneme hakkınız var; Pro'da sınırsız kullanın. Kalan haklarınızı panel ana sayfasındaki kullanım panosundan takip edebilirsiniz.",
  },
];

export function OnboardingTur() {
  const [acik, setAcik] = useState(false);
  const [adim, setAdim] = useState(0);
  const [kaydediliyor, setKaydediliyor] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch("/api/proxy/me", { cache: "no-store" });
        if (!r.ok) return; // giriş yok / hata → tur gösterme
        const j = await r.json();
        const u = (j?.data ?? j)?.user;
        if (alive && u && u.onboarding_done === false) setAcik(true);
      } catch {
        /* yok say */
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  async function tamamla() {
    setKaydediliyor(true);
    try {
      await fetch("/api/proxy/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ onboarding_done: true }),
      });
    } catch {
      /* offline olsa bile modalı kapat */
    } finally {
      setKaydediliyor(false);
      setAcik(false);
    }
  }

  if (!acik) return null;

  const A = ADIMLAR[adim];
  const son = adim === ADIMLAR.length - 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Tanıtım turu"
    >
      <div className="w-full max-w-md rounded-lg border bg-background p-6 shadow-2xl">
        <div className="flex items-start justify-between">
          <span className="rounded-xl bg-primary/10 p-3 text-primary">
            <A.icon className="h-6 w-6" />
          </span>
          <button
            onClick={tamamla}
            aria-label="Kapat"
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <h2 className="mt-4 text-lg font-bold">{A.baslik}</h2>
        <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{A.metin}</p>

        {/* İlerleme noktaları */}
        <div className="mt-6 flex items-center justify-center gap-2" aria-hidden="true">
          {ADIMLAR.map((_, i) => (
            <button
              key={i}
              onClick={() => setAdim(i)}
              className={`h-2 rounded-full transition-all ${
                i === adim ? "w-6 bg-primary" : "w-2 bg-muted-foreground/30 hover:bg-muted-foreground/50"
              }`}
            />
          ))}
        </div>

        <div className="mt-6 flex items-center justify-between">
          <Button type="button" variant="ghost" size="sm" onClick={tamamla} disabled={kaydediliyor}>
            Geç
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={kaydediliyor}
            onClick={() => (son ? tamamla() : setAdim((a) => a + 1))}
          >
            {son ? "Başla" : "Sonraki"}
          </Button>
        </div>
      </div>
    </div>
  );
}
