"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, CheckCircle2, XCircle, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/toast";

/**
 * E-posta doğrulama — iki yol:
 *  1) token (e-postadaki "Tek Tıkla Doğrula" linki) → otomatik doğrular.
 *  2) token yok → 6 haneli KOD akışı: sayfa açılınca kod gönderilir, kullanıcı girer.
 */
export function Verifier({ token, next }: { token?: string; next?: string }) {
  // Link (token) varsa tek-tık doğrulama; yoksa kod akışı. Hook'lar her zaman
  // ilgili alt bileşende çağrılır (rules-of-hooks).
  return token ? <LinkVerifier token={token} next={next} /> : <CodeVerifier next={next} />;
}

function CodeVerifier({ next }: { next?: string }) {
  const router = useRouter();
  const toast = useToast();
  const hedef = next || "/app";

  const [code, setCode] = useState("");
  const [status, setStatus] = useState<"idle" | "checking" | "ok" | "error">("idle");
  const [msg, setMsg] = useState("");
  const [info, setInfo] = useState("Doğrulama kodu e-postanıza gönderiliyor…");
  const [cooldown, setCooldown] = useState(0);
  const sentOnce = useRef(false);

  async function sendCode(initial = false) {
    try {
      const r = await fetch("/api/proxy/auth/send-code", { method: "POST" });
      const j = await r.json().catch(() => ({}));
      if (r.ok) {
        setInfo(
          j.message ||
            "E-postanıza 6 haneli bir kod gönderdik. Gelen kutunuzu (ve spam'i) kontrol edin.",
        );
        if (!initial) toast("Yeni kod gönderildi.", "success");
        setCooldown(60);
      } else if (r.status === 429) {
        setInfo(j.message || "Çok sık talep edildi, lütfen biraz bekleyin.");
        setCooldown(60);
      } else if (!initial) {
        setInfo(j.message || "Kod gönderilemedi.");
      }
    } catch {
      setInfo("Bağlantı hatası. Tekrar deneyin.");
    }
  }

  // Açılışta bir kez kod gönder (StrictMode çift-mount koruması).
  useEffect(() => {
    if (sentOnce.current) return;
    sentOnce.current = true;
    sendCode(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cooldown sayacı.
  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    if (code.trim().length !== 6) return;
    setStatus("checking");
    setMsg("");
    try {
      const r = await fetch("/api/proxy/auth/verify-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim() }),
      });
      const j = await r.json().catch(() => ({}));
      if (r.ok) {
        setStatus("ok");
        setMsg(j.message || "E-postanız doğrulandı.");
      } else {
        setStatus("error");
        setMsg(j.message || j?.detail?.message || "Kod doğrulanamadı.");
      }
    } catch {
      setStatus("error");
      setMsg("Bağlantı hatası.");
    }
  }

  if (status === "ok") {
    return (
      <Card>
        <CardContent className="p-8 space-y-4 text-center">
          <CheckCircle2 className="h-16 w-16 text-emerald-500 mx-auto animate-pop" />
          <p className="font-semibold">{msg}</p>
          <Button
            onClick={() => {
              router.push(hedef);
              router.refresh();
            }}
          >
            {hedef.includes("/abonelik") ? "Ödemeye Devam Et" : "Dashboard'a Git"}
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-8 space-y-5">
        <div className="flex flex-col items-center gap-2 text-center">
          <Mail className="h-10 w-10 text-primary" />
          <p className="text-sm text-muted-foreground">{info}</p>
        </div>

        <form onSubmit={verify} className="space-y-4">
          <Input
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="6 haneli kod"
            className="text-center text-2xl tracking-[0.5em] font-mono h-14"
            aria-label="Doğrulama kodu"
          />
          {status === "error" && (
            <div className="flex items-center justify-center gap-2 text-sm text-destructive">
              <XCircle className="h-4 w-4" /> {msg}
            </div>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={status === "checking" || code.length !== 6}
          >
            {status === "checking" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Doğrula"
            )}
          </Button>
        </form>

        <div className="text-center text-sm text-muted-foreground">
          Kod gelmedi mi?{" "}
          <button
            type="button"
            onClick={() => sendCode(false)}
            disabled={cooldown > 0}
            className="text-primary hover:underline disabled:opacity-50 disabled:no-underline"
          >
            {cooldown > 0 ? `Tekrar gönder (${cooldown})` : "Tekrar gönder"}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

/** E-postadaki linke tıklanınca token ile otomatik doğrular. */
function LinkVerifier({ token, next }: { token: string; next?: string }) {
  const hedef = next || "/app";
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetch("/api/proxy/auth/verify-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then((r) => r.json().then((j) => ({ ok: r.ok, j })))
      .then(({ ok, j }) => {
        if (ok) {
          setStatus("ok");
          setMsg(j.message || "E-postanız doğrulandı.");
        } else {
          setStatus("error");
          setMsg(j.message || "Doğrulama başarısız.");
        }
      })
      .catch(() => {
        setStatus("error");
        setMsg("Bağlantı hatası.");
      });
  }, [token]);

  return (
    <Card>
      <CardContent className="p-8 space-y-4">
        {status === "loading" && (
          <>
            <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto" />
            <p>Doğrulanıyor...</p>
          </>
        )}
        {status === "ok" && (
          <>
            <CheckCircle2 className="h-16 w-16 text-emerald-500 mx-auto animate-pop" />
            <p className="font-semibold">{msg}</p>
            <Button asChild>
              <a href={hedef}>{hedef.includes("/abonelik") ? "Ödemeye Devam Et" : "Dashboard'a Git"}</a>
            </Button>
          </>
        )}
        {status === "error" && (
          <>
            <XCircle className="h-16 w-16 text-destructive mx-auto" />
            <p className="font-semibold text-destructive">{msg}</p>
            <Button asChild variant="outline">
              <a href="/giris/dogrulama">Kod ile Doğrula</a>
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
