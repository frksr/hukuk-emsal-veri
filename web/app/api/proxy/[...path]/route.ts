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

async function buildToken(session: Session | null) {
  if (!session?.user) return null;
  const user = session.user as { id?: string; email?: string; name?: string; role?: string };
  if (!user.id) return null;
  // Backend HS256 İMZALI düz JWT bekliyor (jwt.decode algorithms=["HS256"]).
  // NextAuth encode() JWE (şifreli) üretir → uyumsuz. Bu yüzden jose ile HS256 imzala.
  const key = new TextEncoder().encode(SECRET);
  return await new SignJWT({
    sub: user.id,
    email: user.email,
    name: user.name,
    role: user.role || "user",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("30d")
    .sign(key);
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

  const body = req.method === "GET" || req.method === "HEAD"
    ? undefined
    : await req.arrayBuffer();

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

  try {
    let r = await doFetch(target);
    let hop = 0;
    while ([301, 302, 307, 308].includes(r.status) && hop < 3) {
      const loc = r.headers.get("location");
      if (!loc) break;
      const nextUrl = loc.startsWith("http") ? loc : `${API_URL}${loc}`;
      r = await doFetch(nextUrl);
      hop++;
    }
    const contentType = r.headers.get("content-type") || "";
    // SSE (streaming dilekçe vb.) — buffer'lamadan akıt
    if (contentType.includes("text/event-stream") && r.body) {
      return new NextResponse(r.body, {
        status: r.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache, no-transform",
          Connection: "keep-alive",
        },
      });
    }
    if (contentType.includes("application/json")) {
      const data = await r.json();
      return NextResponse.json(data, { status: r.status });
    }
    const text = await r.text();
    return new NextResponse(text, {
      status: r.status,
      headers: { "Content-Type": contentType || "text/plain" },
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
