import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// NextAuth v5 sürüm/ortam farklarına göre olası oturum çerezi adları — hangisi
// varsa onu temizliyoruz (var olmayanı silmeye çalışmak zararsız bir no-op).
const NEXTAUTH_COOKIE_ADAYLARI = [
  "authjs.session-token",
  "__Secure-authjs.session-token",
  "next-auth.session-token",
  "__Secure-next-auth.session-token",
];

/**
 * Hafif middleware:
 *  - Güvenlik başlıkları (CSP hariç — bu next.config'de)
 *  - Locale hint (Accept-Language Türkçe ise NEXT_LOCALE cookie)
 *  - Bot ratelimiting'e hazır (gerçek limitleme upstream API'de)
 *  - Tarayıcı tamamen kapatılıp yeniden açılınca oturumu sonlandırma
 */
export function middleware(request: NextRequest) {
  // Gercek istek yolunu server component'lere (layout) aktar — boylece auth-gate
  // SADECE gercekten /app yolundaysa calisir, /giris gibi yollarda degil.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-pathname", request.nextUrl.pathname);

  // === Tarayıcı kapanınca oturumu sonlandır ===================================
  // NextAuth'un oturum çerezi 30 gün kalıcıdır (bkz. lib/auth/config.ts
  // session.maxAge) — sekmeyi kapatıp tekrar açan kullanıcıyı hep giriş
  // yapılmış bırakırdı. Bunun önüne geçmek için giriş/kayıt sırasında
  // (oturumPenceresiAc ile) Max-Age'siz gerçek bir "tarayıcı oturumu" çerezi
  // de konuyor: bu çerez yalnızca tarayıcı PROGRAMI tamamen kapanınca silinir,
  // sekme kapatma/yenilemede silinmez. O çerez yoksa ama kalıcı NextAuth
  // çerezi hâlâ duruyorsa → tarayıcı kapatılıp yeniden açılmış demektir.
  const oturumPenceresiVar = !!request.cookies.get("oturum_penceresi");
  const eskiOturumCerezi = NEXTAUTH_COOKIE_ADAYLARI.find((ad) =>
    request.cookies.get(ad)
  );
  const tarayiciYenidenAcildi = !oturumPenceresiVar && !!eskiOturumCerezi;
  const korumaliAlan = request.nextUrl.pathname.startsWith("/panel");

  if (tarayiciYenidenAcildi && korumaliAlan) {
    // Korumalı bir sayfaya kalıcı-ama-artık-geçersiz sayılan çerezle
    // gelinmiş → girişe yönlendir ve eski çerez(ler)i temizle.
    const girisUrl = new URL("/giris", request.url);
    girisUrl.searchParams.set("callbackUrl", request.nextUrl.pathname);
    const yonlendirme = NextResponse.redirect(girisUrl);
    for (const ad of NEXTAUTH_COOKIE_ADAYLARI) {
      yonlendirme.cookies.set(ad, "", { path: "/", maxAge: 0 });
    }
    return yonlendirme;
  }

  const response = NextResponse.next({ request: { headers: requestHeaders } });

  if (tarayiciYenidenAcildi) {
    // Korumasız (herkese açık) bir sayfa — yönlendirmeye gerek yok, sadece
    // artık geçersiz sayılan eski çerezi sessizce temizle.
    for (const ad of NEXTAUTH_COOKIE_ADAYLARI) {
      response.cookies.set(ad, "", { path: "/", maxAge: 0 });
    }
  }

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
