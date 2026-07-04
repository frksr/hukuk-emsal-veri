/**
 * Next.js → FastAPI proxy.
 *
 * Frontend'den /api/proxy/me çağrılır → bu route NextAuth session'ı alır,
 * JWT'yi backend'e Authorization header ile geçer. Backend `NEXTAUTH_SECRET`
 * ile doğrular.
 */
import { NextResponse } from "next/server";
import type { Session } from "next-auth";
import { auth } from "@/auth";
import { SignJWT } from "jose";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Sunucu tarafı fetch için: Node 18 'localhost'u IPv6 (::1) çözebilir; uvicorn IPv4
// (127.0.0.1) dinler → "fetch failed". Bu yüzden localhost'u 127.0.0.1'e zorla.
const API_URL = (
  process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010"
).replace("//localhost", "//127.0.0.1");
const SECRET = process.env.NEXTAUTH_SECRET || "";

// JWT'yi kullanıcı başına cache'le (5 dk) — her istekte crypto işlemi yapmayı önler.
const _tokenCache = new Map<string, { token: string; exp: number }>();

async function buildToken(session: Session | null) {
  if (!session?.user) return null;
  const user = session.user as { id?: string; email?: string; name?: string; role?: string };
  if (!user.id) return null;

  const cached = _tokenCache.get(user.id);
  if (cached && cached.exp > Date.now()) return cached.token;

  const key = new TextEncoder().encode(SECRET);
  const token = await new SignJWT({
    sub: user.id,
    email: user.email,
    name: user.name,
    role: user.role || "user",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("30d")
    .sign(key);

  // 5 dakika cache — backend token 30 gün geçerli, cache erken temizlenir.
  _tokenCache.set(user.id, { token, exp: Date.now() + 5 * 60 * 1000 });
  return token;
}

async function handle(req: Request, params: { path: string[] }) {
  const session = await auth();
  const token = await buildToken(session);

  const path = params.path.join("/");
  const url = new URL(req.url);
  const target = `${API_URL}/api/${path}${url.search}`;

  const headers: Record<string, string> = {};
  req.headers.forEach((v, k) => {
    // Sadece güvenli header'ları forward et
    if (["content-type", "accept", "x-tenant-id"].includes(k.toLowerCase())) {
      headers[k] = v;
    }
  });
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const contentType = req.headers.get("content-type") || "";
  const isMultipart = contentType.includes("multipart/form-data");
  const hasBody = !(req.method === "GET" || req.method === "HEAD");

  try {
    let r: Response;
    if (isMultipart && hasBody && req.body) {
      // Dosya yüklemede tüm body'yi arrayBuffer() ile belleğe almak büyük
      // dosyalarda (Cloud Run konteyner belleği sınırlı) bağlantının
      // ERR_CONNECTION_RESET ile kopmasına yol açabiliyordu. Bu yüzden
      // multipart body'yi buffer'lamadan doğrudan stream ediyoruz.
      // Not: stream tek kullanımlık — redirect retry burada uygulanmaz
      // (upload endpoint'i zaten trailing-slash redirect'e girmiyor).
      r = await fetch(target, {
        method: req.method,
        headers,
        body: req.body,
        // @ts-expect-error - Node'un undici fetch'i stream body için gerektirir
        duplex: "half",
        cache: "no-store",
        redirect: "manual",
      });
    } else {
      const body = hasBody ? await req.arrayBuffer() : undefined;

      // Node fetch (undici), POST/PATCH/DELETE için 307/308 redirect'i takip ETMEZ
      // (FastAPI trailing-slash redirect'i → "fetch failed"). Bu yüzden elle takip et.
      const doFetch = (u: string) =>
        fetch(u, {
          method: req.method,
          headers,
          body: body && body.byteLength > 0 ? Buffer.from(body) : undefined,
          cache: "no-store",
          redirect: "manual",
        });

      r = await doFetch(target);
      let hop = 0;
      while ([301, 302, 307, 308].includes(r.status) && hop < 3) {
        const loc = r.headers.get("location");
        if (!loc) break;
        const nextUrl = loc.startsWith("http") ? loc : `${API_URL}${loc}`;
        r = await doFetch(nextUrl);
        hop++;
      }
    }
    const respContentType = r.headers.get("content-type") || "";
    // SSE (streaming dilekçe vb.) — buffer'lamadan akıt
    if (respContentType.includes("text/event-stream") && r.body) {
      return new NextResponse(r.body, {
        status: r.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache, no-transform",
          Connection: "keep-alive",
        },
      });
    }
    if (respContentType.includes("application/json")) {
      const data = await r.json();
      return NextResponse.json(data, { status: r.status });
    }
    const text = await r.text();
    return new NextResponse(text, {
      status: r.status,
      headers: { "Content-Type": respContentType || "text/plain" },
    });
  } catch (e) {
    return NextResponse.json(
      { ok: false, message: "Backend erişilemiyor.", error: String(e) },
      { status: 502 },
    );
  }
}

export async function GET(req: Request, ctx: { params: { path: string[] } }) {
  return handle(req, ctx.params);
}
export async function POST(req: Request, ctx: { params: { path: string[] } }) {
  return handle(req, ctx.params);
}
export async function PATCH(req: Request, ctx: { params: { path: string[] } }) {
  return handle(req, ctx.params);
}
export async function DELETE(req: Request, ctx: { params: { path: string[] } }) {
  return handle(req, ctx.params);
}
export async function PUT(req: Request, ctx: { params: { path: string[] } }) {
  return handle(req, ctx.params);
}
