import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { AppSidebar } from "./_sidebar";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user) {
    redirect("/giris?callbackUrl=/app");
  }

  return (
    <div className="container py-6 grid grid-cols-12 gap-6 min-h-[calc(100vh-4rem)]">
      <aside className="col-span-12 md:col-span-3 lg:col-span-2">
        <AppSidebar userName={session.user.name ?? session.user.email ?? ""} />
      </aside>
      <main className="col-span-12 md:col-span-9 lg:col-span-10">
        {children}
      </main>
    </div>
  );
}
