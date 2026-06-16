import { NextRequest, NextResponse } from "next/server";

/**
 * iyzico abonelik (subscription) ödeme dönüş adresi.
 *
 * iyzico CheckoutForm sonucu callbackUrl'e POST (application/x-www-form-urlencoded,
 * `token` alanıyla) yapar. App Router sayfaları ham POST'u Server Action sanıp
 * "Invalid URL" hatası verdiğinden, callback'i bu route handler karşılar; token'ı
 * gövdeden (veya query'den) alıp abonelik sayfasına GET ile 303 yönlendirir.
 * Sayfadaki istemci mantığı token ile `/api/proxy/billing/callback`'i çağırıp
 * aboneliği aktifleştirir ve başarı popup'ını gösterir.
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
  const dest = new URL("/app/ayarlar/abonelik", req.nextUrl.origin);
  dest.searchParams.set("callback", "1");
  if (token) dest.searchParams.set("token", token);
  return NextResponse.redirect(dest, 303);
}

export async function POST(req: NextRequest) {
  return yonlendir(req, await tokenAl(req));
}

export async function GET(req: NextRequest) {
  return yonlendir(req, await tokenAl(req));
}
