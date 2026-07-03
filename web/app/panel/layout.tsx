import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { auth } from "@/auth";
import { getEmailVerified } from "@/lib/auth/db";
import { AppSidebar } from "./_sidebar";
import { DogrulamaBanner } from "@/components/dogrulama-banner";
import { PageTransition } from "@/components/page-transition";
import { OnboardingTur } from "@/components/onboarding-tur";
import { NpsAnket } from "@/components/nps-anket";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  const pathname = headers().get("x-pathname") || "";
  // /panel/* hem doğrudan hem de /app/* rewrite'ı üzerinden gelebilir.
  const isAppRoute = pathname.startsWith("/panel") || pathname.startsWith("/app");

  // Gercek panel yolunda + oturum yoksa girise yonlendir.
  if (isAppRoute && !session?.user) {
    redirect("/giris?callbackUrl=" + encodeURIComponent(pathname));
  }

  // Bu layout bazen panel disindaki rotalar (/, /giris ...) icin de calisiyor
  // (Next routing ozelligi). O durumda app chrome'unu (sidebar) render ETME ve
  // session.user'a DOKUNMA — sadece icerigi gecir. Aksi halde null session ->
  // server-side exception olur.
  if (!isAppRoute || !session?.user) {
    return <>{children}</>;
  }

  // Zorunlu e-posta doğrulama kapısı — doğrulanmamış kullanıcı panele hiç
  // giremez (admin muaf). Rol/doğrulama JWT'de tutulmaz (verify anında token
  // yenilenmiyor), bu yüzden DB'den canlı okunur — admin rolü kontrolüyle aynı
  // desende (bkz. panel/admin/layout.tsx). DB'ye erişilemezse kilitlenmeyi
  // önlemek için erişime İZİN VERİLİR (fail-open).
  const userId = (session.user as { id?: string }).id;
  const role = (session.user as { role?: string }).role;
  if (userId && role !== "admin") {
    // NOT: redirect() Next.js içinde özel bir throw ile çalışır — bu yüzden
    // try/catch'in İÇİNE alınmamalı (aksi halde catch onu yutar ve yönlendirme
    // hiç gerçekleşmez). Sadece DB okuması try/catch'te.
    let verified = true; // DB'ye erişilemezse varsayılan: erişime izin ver (fail-open)
    try {
      verified = await getEmailVerified(userId);
    } catch {
      verified = true;
    }
    if (!verified) {
      redirect("/giris/dogrulama?next=" + encodeURIComponent(pathname));
    }
  }

  return (
    <div className="container py-6 grid grid-cols-12 gap-6 min-h-[calc(100vh-4rem)]">
      <aside className="col-span-12 md:col-span-3 lg:col-span-2 md:rounded-xl md:border md:border-border/60 md:bg-gradient-to-b md:from-muted/50 md:to-transparent md:p-2">
        <AppSidebar userName={session.user.name ?? session.user.email ?? ""} />
      </aside>
      <main className="col-span-12 md:col-span-9 lg:col-span-10">
        <DogrulamaBanner />
        <OnboardingTur />
        <PageTransition>{children}</PageTransition>
        <NpsAnket />
      </main>
    </div>
  );
}
