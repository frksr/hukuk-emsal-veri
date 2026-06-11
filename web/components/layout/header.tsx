"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X, Scale } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/emsal-arama", label: "Emsal Arama" },
  { href: "/dilekce", label: "Dilekçe" },
  { href: "/ihtarname", label: "İhtarname" },
  { href: "/faiz-hesaplayici", label: "Faiz" },
  { href: "/zamanasimi", label: "Zamanaşımı" },
  { href: "/kvkk", label: "KVKK" },
  { href: "/fiyatlandirma", label: "Fiyatlandırma" },
];

export function Header() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container-main flex h-16 items-center justify-between gap-4">
        <Link
          href="/"
          className="flex items-center gap-2 font-heading text-lg font-bold text-primary-700 hover:text-primary-600"
          aria-label="Hukuk Emsal anasayfa"
        >
          <Scale className="h-6 w-6 text-accent-500" aria-hidden="true" />
          <span>Hukuk Emsal</span>
        </Link>

        <nav
          aria-label="Ana navigasyon"
          className="hidden items-center gap-1 md:flex"
        >
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm font-medium text-foreground/80 transition hover:bg-secondary hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
          <Link
            href="/emsal-arama"
            className="ml-2 inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:bg-primary-600"
          >
            Hemen Ara
          </Link>
        </nav>

        <button
          type="button"
          aria-label={open ? "Menüyü kapat" : "Menüyü aç"}
          aria-expanded={open}
          aria-controls="mobile-menu"
          onClick={() => setOpen((v) => !v)}
          className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border text-foreground md:hidden"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
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
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className="rounded-md px-3 py-2 text-base font-medium text-foreground/90 hover:bg-secondary"
            >
              {item.label}
            </Link>
          ))}
          <Link
            href="/emsal-arama"
            onClick={() => setOpen(false)}
            className="mt-2 inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary-600"
          >
            Hemen Ara
          </Link>
        </nav>
      </div>
    </header>
  );
}
