import { NextResponse } from "next/server";
import { SignJWT } from "jose";
import { createUser, emailTaken, getPool } from "@/lib/auth/db";

export const runtime = "nodejs";

// Sunucu tarafı fetch için: Node 18 'localhost'u IPv6 (::1) çözebilir; uvicorn IPv4
// (127.0.0.1) dinler → "fetch failed" (bkz. api/proxy/[...path]/route.ts).
const API_URL = (
  process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010"
).replace("//localhost", "//127.0.0.1");

/**
 * Yeni kayıt olan kullanıcı için sistem admin'ine bilgilendirme maili tetikler.
 * Backend `NEXTAUTH_SECRET` ile imzalanmış JWT bekliyor (proxy/route.ts'teki
 * imzalama deseniyle aynı) — bu yüzden burada da kısa ömürlü bir token üretilir.
 * Bildirim, kayıt akışını asla bozmamalı: hata yutulur, sadece loglanır.
 */
async function notifyAdminOfRegistration(user: { id: string; email: string; name: string | null }) {
  try {
    const secret = process.env.NEXTAUTH_SECRET || "";
    if (!secret) return;
    const key = new TextEncoder().encode(secret);
    const token = await new SignJWT({
      sub: user.id,
      email: user.email,
      name: user.name,
      role: "user",
    })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt()
      .setExpirationTime("5m")
      .sign(key);

    await fetch(`${API_URL}/api/auth/notify-registration`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });
  } catch (e) {
    console.warn("Kayıt admin bildirimi gönderilemedi", e);
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { name, email, password, kvkk, marketing, davet } = body;

    if (!email || !password) {
      return NextResponse.json({ ok: false, message: "E-posta ve şifre zorunlu." }, { status: 400 });
    }
    if (!kvkk) {
      return NextResponse.json({ ok: false, message: "KVKK onayı zorunlu." }, { status: 400 });
    }
    if (password.length < 8) {
      return NextResponse.json({ ok: false, message: "Şifre en az 8 karakter olmalı." }, { status: 400 });
    }
    if (await emailTaken(email)) {
      return NextResponse.json({ ok: false, message: "Bu e-posta zaten kayıtlı." }, { status: 409 });
    }

    const user = await createUser({
      email, password,
      name: name || null,
      kvkkAccepted: !!kvkk,
      marketingConsent: !!marketing,
    });

    // Sistem admin'ine yeni kayıt bildirimi. Cloud Run gibi request-scoped
    // ortamlarda yanıt döndükten sonra arka plan işi CPU throttle'a takılıp
    // hiç tamamlanmayabilir — bu yüzden fire-and-forget yerine awaited
    // (fonksiyon içinde try/catch var, kayıt akışını asla bozmaz/geciktirmez
    // hata fırlatmaz, sadece birkaç yüz ms ekler).
    await notifyAdminOfRegistration({ id: user.id, email: user.email, name: user.name });

    // Bekleme listesi daveti ile geldiyse (kayit?davet=<kod>) CRM durumunu işaretle.
    // Kod eşleşmezse sessizce geç — kayıt akışını asla engelleme.
    if (davet && typeof davet === "string" && davet.length <= 64) {
      try {
        await getPool().query(
          `UPDATE waitlist SET status = 'kayit_oldu'
           WHERE invite_code = $1 AND status <> 'kayit_oldu'`,
          [davet],
        );
      } catch (e) {
        console.warn("waitlist davet isaretlenemedi", e);
      }
    }

    return NextResponse.json({ ok: true, data: { id: user.id, email: user.email } });
  } catch (e) {
    console.error("register error", e);
    return NextResponse.json(
      { ok: false, message: e instanceof Error ? e.message : "Kayıt başarısız." },
      { status: 500 },
    );
  }
}
