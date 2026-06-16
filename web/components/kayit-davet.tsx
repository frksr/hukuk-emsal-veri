"use client";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, UserPlus, Clock, ShieldCheck, X } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Kayıtsız kullanıcı bir aracı kullanmak istediğinde, sert bir yönlendirme yerine
 * sıcak ve "çok kolay" hissi veren bir davet popup'ı gösterir.
 *
 * Kullanım:
 *   const { davetGoster, dialog } = useKayitDavet();
 *   ...
 *   if (!isLoggedIn) { davetGoster(); return; }
 *   ...
 *   return (<>{dialog} ...</>);
 */
export function useKayitDavet() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const davetGoster = useCallback(() => setOpen(true), []);
  const kapat = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const dialog = open ? (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 animate-fade-in"
      onClick={kapat}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-md rounded-2xl border bg-background p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div className="rounded-full bg-primary/10 p-2.5 text-primary">
            <Sparkles className="h-5 w-5" />
          </div>
          <button
            type="button"
            onClick={kapat}
            aria-label="Kapat"
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <h3 className="mt-3 text-lg font-semibold">Bir adım kaldı — üstelik ücretsiz</h3>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Bu aracı kullanmak için ücretsiz bir hesap açman yeterli. Yalnızca
          30 saniye sürer ve kart bilgisi istemez. Hesabınla aramalarını ve
          ürettiklerini de saklayıp istediğin an kaldığın yerden devam edebilirsin.
        </p>

        <ul className="mt-4 space-y-2 text-sm">
          <li className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary shrink-0" /> 30 saniyede, e-posta ile kayıt
          </li>
          <li className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary shrink-0" /> Kart bilgisi yok, tamamen ücretsiz
          </li>
        </ul>

        <div className="mt-5 space-y-2">
          <Button className="w-full" onClick={() => router.push("/kayit")}>
            <UserPlus className="h-4 w-4 mr-1.5" /> Ücretsiz kayıt ol
          </Button>
          <div className="flex items-center justify-between text-sm">
            <button
              type="button"
              onClick={() => router.push("/giris")}
              className="text-muted-foreground underline hover:text-foreground"
            >
              Zaten üyeyim, giriş yap
            </button>
            <button
              type="button"
              onClick={kapat}
              className="text-muted-foreground hover:text-foreground"
            >
              Şimdi değil
            </button>
          </div>
        </div>
      </div>
    </div>
  ) : null;

  return { davetGoster, dialog };
}
