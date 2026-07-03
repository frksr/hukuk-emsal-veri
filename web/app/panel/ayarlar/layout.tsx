"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/panel/ayarlar", label: "Profil" },
  { href: "/panel/ayarlar/guvenlik", label: "Güvenlik" },
  { href: "/panel/ayarlar/kvkk", label: "KVKK & Veriler" },
];

export default function AyarlarLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Ayarlar</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Profil, güvenlik ve KVKK haklarınızı yönetin.
        </p>
      </div>
      <nav className="flex gap-1 p-1 rounded-lg bg-muted/70 w-fit max-w-full overflow-x-auto">
        {TABS.map((t) => {
          const active = pathname === t.href;
          return (
            <Link
              key={t.href}
              href={t.href}
              className={cn(
                "px-4 py-1.5 rounded-md text-sm transition-all whitespace-nowrap",
                active
                  ? "bg-card text-primary font-medium shadow-sm"
                  : "text-muted-foreground hover:text-foreground hover:bg-card/60"
              )}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>
      <div>{children}</div>
    </div>
  );
}
