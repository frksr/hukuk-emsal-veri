"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { Menu, X, Scale, LogOut, LayoutDashboard, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthUser } from "@/components/auth-context";
import { ProfileMenu } from "@/components/layout/profile-menu";
import { ThemeToggle } from "@/components/theme-toggle";

const NAV = [
  { href: "/emsal-arama", label: "Emsal Arama" },
  { href: "/dilekce", label: "Dilekçe" },
  { href: "/ihtarname", label: "İhtarname" },
  { href: "/faiz-hesaplayici", label: "Faiz" },
  { href: "/zamanasimi", label: "Zamanaşımı" },
  { href: "/kvkk", label: "KVKK" },
  { href: "/blog", label: "Blog" },
  { href: "/fiyatlandirma", label: "Fiyatlandırma" },
];

export function Header() {
  const [open, setOpen] = useState(false);
  // Giriş durumu SUNUCUDAN gelir (ilk render'da doğru) → titreme yok.
  const user = useAuthUser();
  const isLoggedIn = !!user;
  const name = user?.name ?? null;
  const email = user?.email ?? null;
  const panelHref = user?.role === "admin" ? "/panel/admin" : "/panel";
  const pathname = usePathname();
  // Menüyü yalnızca /panel (hesap) alanında gizle — orada sol sidebar var.
  // Ana sayfa ve diğer genel sayfalarda menü her zaman görünür.
  const menuGoster = !(pathname?.startsWith("/panel") ?? false);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container-main flex h-16 items-center justify-between gap-4">
        <Link
          href="/"
          className="flex items-center gap-2 font-heading text-lg font-bold text-primary-700 dark:text-primary-300 hover:text-primary-600 dark:hover:text-primary-200"
          aria-label="Hukuk Emsal anasayfa"
        >
          <Scale className="h-6 w-6 text-accent-500 shrink-0" aria-hidden="true" />
          <span className="whitespace-nowrap">Hukuk Emsal</span>
        </Link>

        <nav
          aria-label="Ana navigasyon"
          className="hidden items-center gap-0.5 md:flex flex-nowrap"
        >
          {/* Menü genel sayfalarda görünür; /panel alanında sidebar var, gizli */}
          {menuGoster && NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-2.5 py-2 text-xs font-medium text-foreground/80 transition hover:bg-secondary hover:text-foreground whitespace-nowrap"
            >
              {item.label}
            </Link>
          ))}
          {/* Tema değiştirme */}
          <ThemeToggle className="ml-1" />
          {/* Ana CTA — hero butonuyla ayni renk (bg-primary) */}
          {menuGoster && (
            <Link
              href="/emsal-arama"
              className="ml-2 inline-flex h-10 items-center justify-center rounded-md bg-primary px-5 text-sm font-semibold text-primary-foreground transition hover:bg-primary-600 whitespace-nowrap"
            >
              Ücretsiz Dene
            </Link>
          )}
          {/* Oturum durumu — SSR'dan bilindiği için doğrudan render (titreme yok).
              Pazarlama sayfalarında kimlik gösterilmez; sadece "Panele Git" (best
              practice). Hesap menüsü /panel içindedir. */}
          {isLoggedIn ? (
            menuGoster ? (
              <Link
                href={panelHref}
                className="ml-2 inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:bg-primary-600 whitespace-nowrap"
              >
                Panele Git
              </Link>
            ) : (
              <div className="ml-2">
                <ProfileMenu name={name} email={email} />
              </div>
            )
          ) : (
            <div className="ml-2 flex items-center gap-2">
              <Link
                href="/giris"
                className="inline-flex h-9 items-center justify-center rounded-md px-3 text-sm font-medium text-foreground/80 hover:bg-secondary hover:text-foreground"
              >
                Giriş
              </Link>
              <Link
                href="/kayit"
                className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary-600 whitespace-nowrap"
              >
                Kayıt Ol
              </Link>
            </div>
          )}
        </nav>

        <div className="flex items-center gap-2 md:hidden">
          <ThemeToggle className="h-10 w-10" />
          <button
            type="button"
            aria-label={open ? "Menüyü kapat" : "Menüyü aç"}
            aria-expanded={open}
            aria-controls="mobile-menu"
            onClick={() => setOpen((v) => !v)}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border text-foreground transition-colors hover:bg-secondary"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      <div
        id="mobile-menu"
        className={cn(
          "border-t border-border md:hidden",
          open ? "block animate-fade-in" : "hidden"
        )}
      >
        <nav
          aria-label="Mobil navigasyon"
          className="container-main flex flex-col gap-1 py-3"
        >
          {menuGoster && NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className="rounded-md px-3 py-2 text-base font-medium text-foreground/90 hover:bg-secondary"
            >
              {item.label}
            </Link>
          ))}
          {menuGoster && (
            <Link
              href="/emsal-arama"
              onClick={() => setOpen(false)}
              className="mt-1 inline-flex h-11 items-center justify-center rounded-md bg-primary px-6 text-base font-semibold text-primary-foreground hover:bg-primary-600"
            >
              Ücretsiz Dene
            </Link>
          )}
          <div className="mt-2 border-t border-border pt-2">
            {isLoggedIn ? (
              <>
                <Link
                  href={panelHref}
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-2 rounded-md px-3 py-2 text-base font-medium text-foreground/90 hover:bg-secondary"
                >
                  <LayoutDashboard className="h-4 w-4" /> Panelim
                </Link>
                <Link
                  href="/panel/ayarlar"
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-2 rounded-md px-3 py-2 text-base font-medium text-foreground/90 hover:bg-secondary"
                >
                  <Settings className="h-4 w-4" /> Ayarlar
                </Link>
                <button
                  type="button"
                  onClick={() => { setOpen(false); signOut({ callbackUrl: "/" }); }}
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-base font-medium text-destructive hover:bg-secondary"
                >
                  <LogOut className="h-4 w-4" /> Çıkış yap
                </button>
              </>
            ) : (
              <div className="flex gap-2">
                <Link
                  href="/giris"
                  onClick={() => setOpen(false)}
                  className="flex-1 inline-flex h-10 items-center justify-center rounded-md border border-border px-4 text-sm font-medium hover:bg-secondary"
                >
                  Giriş
                </Link>
                <Link
                  href="/kayit"
                  onClick={() => setOpen(false)}
                  className="flex-1 inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary-600 whitespace-nowrap"
                >
                  Kayıt Ol
                </Link>
              </div>
            )}
          </div>
        </nav>
      </div>
    </header>
  );
}
