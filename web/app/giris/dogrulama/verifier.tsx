"use client";
import { useEffect, useState } from "react";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function Verifier({ token }: { token?: string }) {
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error"); setMsg("Doğrulama bağlantısı eksik.");
      return;
    }
    fetch("/api/proxy/auth/verify-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then((r) => r.json().then((j) => ({ ok: r.ok, j })))
      .then(({ ok, j }) => {
        if (ok) { setStatus("ok"); setMsg(j.message || "E-postanız doğrulandı."); }
        else { setStatus("error"); setMsg(j.message || "Doğrulama başarısız."); }
      })
      .catch(() => { setStatus("error"); setMsg("Bağlantı hatası."); });
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
            <CheckCircle2 className="h-16 w-16 text-emerald-500 mx-auto" />
            <p className="font-semibold">{msg}</p>
            <Button asChild><a href="/app">Dashboard'a Git</a></Button>
          </>
        )}
        {status === "error" && (
          <>
            <XCircle className="h-16 w-16 text-destructive mx-auto" />
            <p className="font-semibold text-destructive">{msg}</p>
            <Button asChild variant="outline"><a href="/giris">Giriş Sayfası</a></Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
