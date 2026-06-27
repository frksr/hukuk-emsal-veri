"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { LayoutDashboard, FolderClosed, Sparkles, FileText, Settings, LogOut, FileSearch, StickyNote, Calculator, Clock, Package, Bell, CreditCard, MessageSquarePlus, ShieldCheck, BarChart3, Activity, Users, SlidersHorizontal, MessageSquare, FileWarning, Gift, ListOrdered, Newspaper } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { usePlan } from "@/lib/use-plan";

type NavItem = { href: string; label: string; icon: LucideIcon; badge?: string };

const PLAN_AD: Record<string, string> = {
  free: "Free Plan",
  pro_solo: "Pro Solo",
  pro_solo_uyap: "Pro + UYAP",
  team: "Team",
  team_uyap: "Team + UYAP",
  enterprise: "Enterprise",
};

const NAV: NavItem[] = [
  { href: "/panel", label: "Dashboard", icon: LayoutDashboard },
  { href: "/panel/notlar", label: "Notlarım", icon: StickyNote },
  { href: "/panel/hatirlaticilar", label: "Hatırlatıcılar", icon: Bell, badge: "Pro" },
  { href: "/panel/dosyalar", label: "Dosyalarım", icon: FolderClosed, badge: "Pro" },
  { href: "/panel/sorgu", label: "Yapay Zeka Sorgu", icon: Sparkles, badge: "Pro" },
  { href: "/panel/raporlar", label: "Raporlar", icon: FileText },
  { href: "/panel/gecmis", label: "Geçmiş", icon: FileSearch },
  { href: "/panel/ayarlar/ek-paketler", label: "Ek Paketler", icon: Package },
  { href: "/panel/ayarlar/abonelik", label: "Abonelik", icon: CreditCard },
  { href: "/panel/ayarlar", label: "Ayarlar", icon: Settings },
  { href: "/panel/oneri", label: "Bize Yazın", icon: MessageSquarePlus },
];

// Admin menüsü — admin kullanıcıda kullanıcı sekmeleri yerine bunlar görünür.
// (İzleme/takip konumlu: sistem, müşteri, paket, kredi.)
const ADMIN_NAV: NavItem[] = [
  { href: "/panel/admin", label: "Genel Bakış", icon: LayoutDashboard },
  { href: "/panel/admin/analitik", label: "Analitik", icon: BarChart3 },
  { href: "/panel/admin/sistem", label: "Sistem", icon: Activity },
  { href: "/panel/admin/kullanicilar", label: "Kullanıcılar", icon: Users },
  { href: "/panel/admin/paketler", label: "Paketler & Limitler", icon: SlidersHorizontal },
  { href: "/panel/admin/icerik", label: "İçerik / Blog", icon: Newspaper },
  { href: "/panel/admin/feedback", label: "Geri Bildirim", icon: MessageSquare },
  { href: "/panel/admin/audit", label: "Audit Log", icon: FileWarning },
  { href: "/panel/admin/beta", label: "Beta Davet", icon: Gift },
  { href: "/panel/admin/bekleme-listesi", label: "Bekleme Listesi", icon: ListOrdered },
  { href: "/panel/ayarlar", label: "Ayarlar", icon: Settings },
];

// Sınırsız ücretsiz araçlar — panelden hızlı erişim.
// (Emsal arama free planda aylık limitli olduğu için buraya konmaz; üst menüden erişilir.)
const ARACLAR = [
  { href: "/faiz-hesaplayici", label: "Faiz & Tahsilat", icon: Calculator },
  { href: "/zamanasimi", label: "Zamanaşımı", icon: Clock },
];

export function AppSidebar({ userName }: { userName: string }) {
  const path = usePathname();
  const plan = usePlan();
  const planAd = plan.loading
    ? "…"
    : plan.isAdmin
    ? "Yönetici"
    : PLAN_AD[plan.plan ?? "free"] ?? "Free Plan";
  return (
    <div className="md:sticky md:top-20 md:space-y-1">
      {/* Kullanıcı satırı — mobilde çıkış butonu da burada (kompakt) */}
      <div className="px-3 py-2 mb-2 md:mb-3 text-sm flex items-center justify-between md:block">
        <div>
          <div className="font-semibold">{userName}</div>
          <span
            className={cn(
              "mt-0.5 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
              plan.isAdmin
                ? "bg-primary/15 text-primary border border-primary/30"
                : plan.isPaid
                ? "bg-amber-400/15 text-amber-700 dark:text-amber-300 border border-amber-400/30"
                : "bg-muted text-muted-foreground border border-border",
            )}
          >
            {plan.isAdmin ? <ShieldCheck className="h-3 w-3" /> : plan.isPaid ? <Sparkles className="h-3 w-3" /> : null}
            {planAd}
          </span>
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

      {/* Nav: admin'de admin bölümleri, normal kullanıcıda araç sekmeleri. */}
      <nav className="flex gap-2 overflow-x-auto pb-1 md:flex-col md:gap-1 md:overflow-visible md:pb-0">
        {(plan.isAdmin ? ADMIN_NAV : NAV).map((item) => {
          // Sondaki "/"'ı normalize edip TAM eşleşme (trailingSlash olsa da çalışır,
          // parent rotayı çocuk sayfada yanlışlıkla aktifleştirmez).
          const norm = (path || "/").replace(/\/+$/, "") || "/";
          const active = norm === item.href;
          // "Pro" etiketi yalnızca erişimi OLMAYAN (ücretsiz) kullanıcıya gösterilir;
          // ücretli/admin kullanıcı zaten kullanabildiği için etiket kaldırılır.
          const badge = plan.isPaid || plan.isAdmin ? undefined : item.badge;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group relative flex shrink-0 items-center gap-2 px-3 py-2 rounded-md text-sm whitespace-nowrap transition-all md:shrink md:whitespace-normal",
                active
                  ? "bg-primary text-primary-foreground md:bg-primary/10 md:text-primary md:font-medium"
                  : "bg-muted/50 md:bg-transparent hover:bg-muted",
              )}
            >
              {active && (
                <span className="hidden md:block absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-primary" />
              )}
              <item.icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-transform group-hover:scale-110",
                  active && "md:text-primary",
                )}
              />
              <span className="md:flex-1">{item.label}</span>
              {badge && (
                <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wider rounded bg-amber-400 text-amber-950 px-1.5 py-0.5">
                  {badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Ücretsiz araçlar — panelden hızlı erişim (admin'de gizli) */}
      {!plan.isAdmin && (
      <div className="pt-3 mt-3 border-t">
        <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Ücretsiz Araçlar
        </div>
        <nav className="flex gap-2 overflow-x-auto pb-1 md:flex-col md:gap-1 md:overflow-visible md:pb-0">
          {ARACLAR.map((item) => {
            const active = path === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group flex shrink-0 items-center gap-2 px-3 py-2 rounded-md text-sm whitespace-nowrap transition-all md:shrink md:whitespace-normal",
                  active ? "bg-primary text-primary-foreground" : "bg-muted/50 md:bg-transparent hover:bg-muted",
                )}
              >
                <item.icon className="h-4 w-4 transition-transform group-hover:scale-110" />
                <span className="md:flex-1">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
      )}

      {/* Masaüstü çıkış (mobilde üstte) */}
      <div className="hidden md:block pt-4 mt-4 border-t">
        <Button onClick={() => signOut({ callbackUrl: "/" })} variant="ghost" size="sm" className="w-full justify-start">
          <LogOut className="h-4 w-4 mr-2" /> Çıkış
        </Button>
      </div>
    </div>
  );
}
