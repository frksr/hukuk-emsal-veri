"use client";

import { usePathname } from "next/navigation";

/**
 * Header/Footer/CookieConsent gibi site krom'unu /embed/* rotalarında gizler.
 * Embed sayfaları iframe içinde üçüncü taraf sitelerde gösterilir — yalın olmalı.
 */
export function ChromeGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname?.startsWith("/embed")) return null;
  return <>{children}</>;
}
