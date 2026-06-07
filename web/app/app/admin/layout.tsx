import { redirect } from "next/navigation";
import Link from "next/link";
import { auth } from "@/auth";
import { LayoutDashboard, Users, MessageSquare, FileWarning, Gift } from "lucide-react";

const TABS = [
  { href: "/app/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/app/admin/kullanicilar", label: "Kullanıcılar", icon: Users },
  { href: "/app/admin/feedback", label: "Geri Bildirim", icon: MessageSquare },
  { href: "/app/admin/audit", label: "Audit Log", icon: FileWarning },
  { href: "/app/admin/beta", label: "Beta Davet", icon: Gift },
];

export const dynamic = "force-dynamic";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  const role = (session?.user as { role?: string })?.role;
  if (role !== "admin") redirect("/app?error=unauthorized");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          🛡️ Admin Panel
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Yalnızca admin kullanıcılar — kullanıcı, tenant ve sistem yönetimi.
        </p>
      </div>
      <nav className="flex gap-1 border-b overflow-x-auto">
        {TABS.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className="px-4 py-2 text-sm hover:text-foreground text-muted-foreground border-b-2 border-transparent hover:border-primary transition-colors whitespace-nowrap flex items-center gap-2"
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </Link>
        ))}
      </nav>
      <div>{children}</div>
    </div>
  );
}
