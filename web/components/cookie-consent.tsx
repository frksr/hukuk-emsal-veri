"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const STORAGE_KEY = "kvkk_cookie_consent_v1";

type Consent = "all" | "necessary";

/**
 * KVKK uyumlu çerez onay banner'ı.
 * - Zorunlu çerezler her zaman çalışır (oturum, güvenlik).
 * - Analitik/pazarlama çerezleri yalnızca "Tümünü kabul et" seçilirse.
 * - Tercih localStorage'da saklanır; window'a `kvkkCookieConsent` olarak yayılır.
 */
export function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) {
        setVisible(true);
      } else {
        (window as unknown as { kvkkCookieConsent?: string }).kvkkCookieConsent = saved;
      }
    } catch {
      setVisible(true);
    }
  }, []);

  function decide(consent: Consent) {
    try {
      localStorage.setItem(STORAGE_KEY, consent);
      (window as unknown as { kvkkCookieConsent?: string }).kvkkCookieConsent = consent;
      // Analitik/pazarlama yükleyicileri burada tetiklenebilir (consent === "all").
      window.dispatchEvent(
        new CustomEvent("kvkk-consent", { detail: consent })
      );
    } catch {
      /* localStorage yoksa sessiz geç */
    }
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-label="Çerez tercihleri"
      aria-live="polite"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80"
    >
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          Sitemizin çalışması için <strong>zorunlu çerezler</strong> kullanılır.
          Kullanım analizi ve hizmet iyileştirme için isteğe bağlı çerezleri yalnızca
          onayınızla kullanırız. Ayrıntılar için{" "}
          <Link href="/gizlilik" className="font-medium text-primary underline">
            Gizlilik ve Çerez Politikası
          </Link>
          .
        </p>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => decide("necessary")}
            className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            Yalnızca zorunlu
          </button>
          <button
            type="button"
            onClick={() => decide("all")}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Tümünü kabul et
          </button>
        </div>
      </div>
    </div>
  );
}
