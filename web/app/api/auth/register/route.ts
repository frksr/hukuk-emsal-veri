import { NextResponse } from "next/server";
import { createUser, emailTaken } from "@/lib/auth/db";

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { name, email, password, kvkk, marketing } = body;

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

    return NextResponse.json({ ok: true, data: { id: user.id, email: user.email } });
  } catch (e) {
    console.error("register error", e);
    return NextResponse.json(
      { ok: false, message: e instanceof Error ? e.message : "Kayıt başarısız." },
      { status: 500 },
    );
  }
}
