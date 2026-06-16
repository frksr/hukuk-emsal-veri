import { NextRequest, NextResponse } from "next/server";

/**
 * iyzico tek seferlik (ek paket) ödeme dönüş adresi.
 *
 * iyzico CheckoutForm sonucu callbackUrl'e POST (application/x-www-form-urlencoded,
 * `token` alanıyla) yapar. App Router sayfaları ham POST'u Server Action sanıp
 * "Invalid URL" hatası verdiğinden, callback'i bu route handler karşılar; token'ı
 * gövdeden (veya query'den) alıp ek paketler sayfasına GET ile 303 yönlendirir.
 * Sayfadaki istemci mantığı token ile `/api/proxy/billing/addons/callback`'i çağırıp
 * kredileri yükler.
 */
async function tokenAl(req: NextRequest): Promise<string | null> {
  const q = req.nextUrl.searchParams.get("token");
  if (q) return q;
  try {
    const form = await req.formData();
    const t = form.get("token");
    if (typeof t === "string" && t) return t;
  } catch {
    /* gövde yok / parse edilemedi */
  }
  return null;
}

function yonlendir(req: NextRequest, token: string | null) {
  const dest = new URL("/app/ayarlar/ek-paketler", req.nextUrl.origin);
  dest.searchParams.set("callback", "1");
  if (token) dest.searchParams.set("token", token);
  // 303 → tarayıcı POST'tan GET'e döner.
  return NextResponse.redirect(dest, 303);
}

export async function POST(req: NextRequest) {
  return yonlendir(req, await tokenAl(req));
}

export async function GET(req: NextRequest) {
  return yonlendir(req, await tokenAl(req));
}
