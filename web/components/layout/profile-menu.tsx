"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { signOut } from "next-auth/react";
import { LayoutDashboard, Settings, LogOut } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";

/**
 * Standart hesap menüsü: sağ üstte avatar (baş harf), tıklayınca dropdown.
 * İçerik: kullanıcı adı/e-posta + Panelim (dashboard) + Ayarlar + Çıkış yap.
 */
export function ProfileMenu({ name, email }: { name?: string | null; email?: string | null }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const etiket = (name || email || "").trim();
  const basHarf = (etiket || "?").charAt(0).toUpperCase();

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const ogeClass =
    "flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-secondary transition-colors";

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Hesap menüsü"
        aria-expanded={open}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground ring-offset-background transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        {basHarf}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-60 overflow-hidden rounded-lg border bg-background shadow-lg animate-fade-in">
          <div className="border-b px-3 py-2.5">
            <div className="font-medium truncate">{name || "Hesabım"}</div>
            {email && <div className="text-xs text-muted-foreground truncate">{email}</div>}
          </div>
          <div className="py-1">
            <Link href="/panel" onClick={() => setOpen(false)} className={ogeClass}>
              <LayoutDashboard className="h-4 w-4 text-muted-foreground" /> Panelim
            </Link>
            <Link href="/panel/ayarlar" onClick={() => setOpen(false)} className={ogeClass}>
              <Settings className="h-4 w-4 text-muted-foreground" /> Ayarlar
            </Link>
          </div>
          <div className="border-t py-1">
            <ThemeToggle variant="menu" />
          </div>
          <div className="border-t py-1">
            <button
              type="button"
              onClick={() => { setOpen(false); signOut({ callbackUrl: "/" }); }}
              className={`${ogeClass} text-destructive`}
            >
              <LogOut className="h-4 w-4" /> Çıkış yap
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
