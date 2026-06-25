import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { getUserRole } from "@/lib/auth/db";

export const dynamic = "force-dynamic";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  const userId = (session?.user as { id?: string })?.id;
  if (!userId) redirect("/giris?callbackUrl=/app/admin");

  // Rolü JWT yerine DB'den doğrula (kaynak-doğruluk). Böylece hesap admin
  // yapıldığında, eski oturum token'ı 'user' taşısa bile admin paneli açılır.
  let role = (session?.user as { role?: string })?.role;
  try {
    const dbRole = await getUserRole(userId);
    if (dbRole) role = dbRole;
  } catch {
    /* DB erişilemezse JWT rolüne düş */
  }
  if (role !== "admin") redirect("/app?error=unauthorized");

  // Sekmeler artık sol menüde (AppSidebar). Burada yalnızca başlık + içerik.
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          🛡️ Admin Panel
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Sistem, müşteri, paket ve kredi izleme — soldaki menüden bölümlere geçin.
        </p>
      </div>
      <div>{children}</div>
    </div>
  );
}
