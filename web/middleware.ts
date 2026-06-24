import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Hafif middleware:
 *  - Güvenlik başlıkları (CSP hariç — bu next.config'de)
 *  - Locale hint (Accept-Language Türkçe ise NEXT_LOCALE cookie)
 *  - Bot ratelimiting'e hazır (gerçek limitleme upstream API'de)
 */
export function middleware(request: NextRequest) {
  console.log("[DBG-MW]", request.method, request.nextUrl.pathname, "->next()");
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
  // Backend origin'i env'den türet ki port değişince (örn. 8010) CSP bozulmasın.
  const apiOrigin = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010";
  // iyzico gömülü ödeme formu (checkoutFormContent) iyzico alan adlarından script,
  // iframe (3DS) ve form-post yükler → CSP'de izin ver.
  const iyzico = "https://*.iyzipay.com";
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline' 'unsafe-eval' ${iyzico}`,
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "img-src 'self' data: blob: https:",
    `font-src 'self' data: https://fonts.gstatic.com ${iyzico}`,
    // https: prod domainleri, localhost:* lokalde hangi portta backend olursa olsun kapsar
    `connect-src 'self' https: ${apiOrigin} http://localhost:* http://127.0.0.1:*`,
    `frame-src 'self' ${iyzico}`,
    "frame-ancestors 'self'",
    "base-uri 'self'",
    `form-action 'self' ${iyzico}`,
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
