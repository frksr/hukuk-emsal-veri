"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

function CikisIcerik() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [durum, setDurum] = useState<"yukleniyor" | "tamam" | "hata">("yukleniyor");

  useEffect(() => {
    if (!token) {
      setDurum("hata");
      return;
    }
    (async () => {
      try {
        const r = await fetch("/api/proxy/newsletter/cikis", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        const j = await r.json();
        setDurum(r.ok && j.ok ? "tamam" : "hata");
      } catch {
        setDurum("hata");
      }
    })();
  }, [token]);

  if (durum === "yukleniyor") {
    return (
      <div className="text-center py-8">
        <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
      </div>
    );
  }

  if (durum === "hata") {
    return (
      <div className="text-center space-y-3">
        <XCircle className="h-10 w-10 text-destructive mx-auto" />
        <h1 className="text-xl font-bold">Bağlantı geçersiz</h1>
        <p className="text-sm text-muted-foreground">
          Bu abonelikten çıkış bağlantısı geçersiz görünüyor. Yardım için{" "}
          <a href="/panel/oneri" className="underline">
            Bize Yazın
          </a>{" "}
          sayfasından ulaşabilirsiniz.
        </p>
      </div>
    );
  }

  return (
    <div className="text-center space-y-3">
      <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto" />
      <h1 className="text-xl font-bold">Abonelikten çıkış yapıldı</h1>
      <p className="text-sm text-muted-foreground">
        Artık haftalık bülten e-postalarını almayacaksınız. Fikrinizi
        değiştirirseniz{" "}
        <a href="/blog" className="underline">
          Hukuk Rehberi
        </a>{" "}
        sayfasından tekrar abone olabilirsiniz.
      </p>
    </div>
  );
}

export default function BultenCikisPage() {
  return (
    <div className="container max-w-md py-20">
      <Suspense fallback={null}>
        <CikisIcerik />
      </Suspense>
    </div>
  );
}
