"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { LayoutDashboard, FolderClosed, Sparkles, FileText, Settings, LogOut, FileSearch } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAV = [
  { href: "/app", label: "Dashboard", icon: LayoutDashboard },
  { href: "/app/dosyalar", label: "Dosyalarım", icon: FolderClosed, badge: "Pro" },
  { href: "/app/sorgu", label: "AI Sorgu", icon: Sparkles, badge: "Pro" },
  { href: "/app/raporlar", label: "Raporlar", icon: FileText, badge: "Pro" },
  { href: "/app/gecmis", label: "Geçmiş", icon: FileSearch },
  { href: "/app/ayarlar", label: "Ayarlar", icon: Settings },
];

export function AppSidebar({ userName }: { userName: string }) {
  const path = usePathname();
  return (
    <div className="md:sticky md:top-20 md:space-y-1">
      {/* Kullanıcı satırı — mobilde çıkış butonu da burada (kompakt) */}
      <div className="px-3 py-2 mb-2 md:mb-3 text-sm flex items-center justify-between md:block">
        <div>
          <div className="font-semibold">{userName}</div>
          <div className="text-xs text-muted-foreground">Free Plan</div>
        </div>
        <Button
          onClick={() => signOut({ callbackUrl: "/" })}
          variant="ghost"
          size="sm"
          aria-label="Çıkış"
          className="md:hidden"
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>

      {/* Nav: mobilde yatay kaydırılır pill'ler, masaüstünde dikey liste */}
      <nav className="flex gap-2 overflow-x-auto pb-1 md:flex-col md:gap-1 md:overflow-visible md:pb-0">
        {NAV.map((item) => {
          const active = path === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex shrink-0 items-center gap-2 px-3 py-2 rounded-md text-sm whitespace-nowrap transition-colors md:shrink",
                active ? "bg-primary text-primary-foreground" : "bg-muted/50 md:bg-transparent hover:bg-muted",
              )}
            >
              <item.icon className="h-4 w-4" />
              <span className="md:flex-1">{item.label}</span>
              {item.badge && (
                <span className="text-[10px] uppercase tracking-wider rounded bg-accent/20 text-accent-foreground px-1.5 py-0.5">
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Masaüstü çıkış (mobilde üstte) */}
      <div className="hidden md:block pt-4 mt-4 border-t">
        <Button onClick={() => signOut({ callbackUrl: "/" })} variant="ghost" size="sm" className="w-full justify-start">
          <LogOut className="h-4 w-4 mr-2" /> Çıkış
        </Button>
      </div>
    </div>
  );
}
