"use client";
import { useEffect, useRef } from "react";
import { signOut } from "next-auth/react";
import { usePlan } from "@/lib/use-plan";

// Hareketsizlik süresi — bu kadar süre işlem olmazsa oturum kapanır.
const TIMEOUT_MS = 30 * 60 * 1000; // 30 dakika

/**
 * Belirli süre hareketsizlik sonrası otomatik oturum kapatma.
 * Sadece giriş yapılmışken çalışır. Aktivite (fare/klavye/dokunma/scroll) süreyi sıfırlar.
 */
export function InactivityLogout() {
  const { isLoggedIn } = usePlan();
  const sonAktivite = useRef<number>(Date.now());

  useEffect(() => {
    if (!isLoggedIn) return;

    const isaretle = () => {
      sonAktivite.current = Date.now();
    };
    const olaylar = ["mousemove", "keydown", "click", "scroll", "touchstart"];
    olaylar.forEach((e) => window.addEventListener(e, isaretle, { passive: true }));

    // 30 sn'de bir kontrol — mousemove'da timer kurmak yerine zaman damgası karşılaştır.
    const interval = setInterval(() => {
      if (Date.now() - sonAktivite.current > TIMEOUT_MS) {
        clearInterval(interval);
        signOut({ callbackUrl: "/giris?expired=1" });
      }
    }, 30_000);

    return () => {
      olaylar.forEach((e) => window.removeEventListener(e, isaretle));
      clearInterval(interval);
    };
  }, [isLoggedIn]);

  return null;
}
