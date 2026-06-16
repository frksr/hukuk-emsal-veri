"use client";
import { usePathname } from "next/navigation";

/**
 * Rota değişiminde panel içeriğini yumuşakça yeniden belirir (fade + hafif kayma).
 * `key={pathname}` her gezinmede animasyonu yeniden tetikler. Hareket-azalt
 * tercihinde globals.css otomatik olarak susturur.
 */
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div key={pathname} className="animate-slide-up">
      {children}
    </div>
  );
}
