import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Hafif middleware:
 *  - Güvenlik başlıkları (CSP hariç — bu next.config'de)
 *  - Locale hint (Accept-Language Türkçe ise NEXT_LOCALE cookie)
 *  - Bot ratelimiting'e hazır (gerçek limitleme upstream API'de)
 */
export function middleware(request: NextRequest) {
  const response = NextResponse.next();

  // Güvenlik başlıkları (next.config headers ile çakışmaması için fark olanlar)
  response.headers.set("X-Robots-Tag", "index, follow");

  // Locale tespiti (basit)
  const acceptLanguage = request.headers.get("accept-language") || "";
  const isTurkish = /^tr\b|,\s*tr\b/i.test(acceptLanguage);
  if (isTurkish && !request.cookies.get("NEXT_LOCALE")) {
    response.cookies.set("NEXT_LOCALE", "tr-TR", {
      path: "/",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 365,
    });
  }

  // CSP — App Router için nispeten gevşek; prod sıkılaştırılabilir.
  const csp = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data: https://fonts.gstatic.com",
    "connect-src 'self' https: http://localhost:8000",
    "frame-ancestors 'self'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
  response.headers.set("Content-Security-Policy", csp);

  return response;
}

export const config = {
  // _next, statik dosyalar, API içsel rotaları hariç tüm path'lerde çalış
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml|.*\\.(?:png|jpg|jpeg|gif|webp|svg|ico|css|js|woff|woff2|ttf|eot)).*)",
  ],
};
