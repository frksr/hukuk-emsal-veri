/**
 * Next.js → FastAPI proxy.
 *
 * Frontend'den /api/proxy/me çağrılır → bu route NextAuth session'ı alır,
 * JWT'yi backend'e Authorization header ile geçer. Backend `NEXTAUTH_SECRET`
 * ile doğrular.
 */
import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { encode } from "next-auth/jwt";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SECRET = process.env.NEXTAUTH_SECRET || "";

async function buildToken(session: Awaited<ReturnType<typeof auth>>) {
  if (!session?.user) return null;
  const user = session.user as { id?: string; email?: string; name?: string; role?: string };
  if (!user.id) return null;
  return await encode({
    token: {
      sub: user.id,
      email: user.email,
      name: user.name,
      role: user.role || "user",
    },
    secret: SECRET,
    salt: "next-auth.session-token",
  });
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

  try {
    const r = await fetch(target, {
      method: req.method,
      headers,
      body: body && body.byteLength > 0 ? Buffer.from(body) : undefined,
      cache: "no-store",
    });
    const contentType = r.headers.get("content-type") || "";
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
