import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { auth } from "@/auth";
import { AppSidebar } from "./_sidebar";
import { DogrulamaBanner } from "@/components/dogrulama-banner";
import { PageTransition } from "@/components/page-transition";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  // Bu layout bazen /app disindaki rotalar/404'ler icin de calisabiliyor (Next
  // routing). Loop'u onlemek icin auth-gate'i SADECE gercek /app yolunda uygula.
  const pathname = headers().get("x-pathname") || "";
  if (pathname.startsWith("/app") && !session?.user) {
    redirect("/giris?callbackUrl=" + encodeURIComponent(pathname));
  }

  return (
    <div className="container py-6 grid grid-cols-12 gap-6 min-h-[calc(100vh-4rem)]">
      <aside className="col-span-12 md:col-span-3 lg:col-span-2">
        <AppSidebar userName={session.user.name ?? session.user.email ?? ""} />
      </aside>
      <main className="col-span-12 md:col-span-9 lg:col-span-10">
        <DogrulamaBanner />
        <PageTransition>{children}</PageTransition>
      </main>
    </div>
  );
}
