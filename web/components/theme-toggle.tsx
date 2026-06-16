"use client";

import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";
import { cn } from "@/lib/utils";

type Tema = "light" | "dark";

/**
 * Tema durumunu okur/yazar. localStorage anahtarı: "tema".
 * İlk yüklemede layout'taki inline script zaten doğru sınıfı uygulamış olur;
 * burada yalnızca mevcut durumu okuyup butonu senkronlarız (FOUC olmaz).
 */
function mevcutTema(): Tema {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

function temaUygula(tema: Tema) {
  const kok = document.documentElement;
  if (tema === "dark") kok.classList.add("dark");
  else kok.classList.remove("dark");
  try {
    localStorage.setItem("tema", tema);
  } catch {
    /* yoksay */
  }
}

export function ThemeToggle({
  className,
  variant = "icon",
}: {
  className?: string;
  /** "icon": yalnızca ikon (header). "menu": metinli satır (profil menüsü). */
  variant?: "icon" | "menu";
}) {
  const [tema, setTema] = useState<Tema>("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setTema(mevcutTema());
    setMounted(true);
  }, []);

  function degistir() {
    const yeni: Tema = tema === "dark" ? "light" : "dark";
    setTema(yeni);
    temaUygula(yeni);
  }

  const koyuAktif = tema === "dark";
  const etiket = koyuAktif ? "Açık temaya geç" : "Koyu temaya geç";

  if (variant === "menu") {
    return (
      <button
        type="button"
        onClick={degistir}
        aria-label={etiket}
        className={cn(
          "flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-secondary",
          className
        )}
      >
        {/* mounted olana kadar ay ikonunu varsayılan gösterme — hydration uyumu için suppress */}
        {mounted && koyuAktif ? (
          <Sun className="h-4 w-4 text-muted-foreground" />
        ) : (
          <Moon className="h-4 w-4 text-muted-foreground" />
        )}
        <span>{mounted && koyuAktif ? "Açık tema" : "Koyu tema"}</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={degistir}
      aria-label={etiket}
      title={etiket}
      className={cn(
        "relative inline-flex h-9 w-9 items-center justify-center rounded-md border border-border text-foreground/80 transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className
      )}
    >
      <Sun
        className={cn(
          "absolute h-[1.15rem] w-[1.15rem] transition-all duration-200",
          mounted && koyuAktif ? "scale-100 rotate-0 opacity-100" : "scale-0 -rotate-90 opacity-0"
        )}
        aria-hidden="true"
      />
      <Moon
        className={cn(
          "absolute h-[1.15rem] w-[1.15rem] transition-all duration-200",
          mounted && koyuAktif ? "scale-0 rotate-90 opacity-0" : "scale-100 rotate-0 opacity-100"
        )}
        aria-hidden="true"
      />
    </button>
  );
}
