import Link from "next/link";
import { auth } from "@/auth";
import { ArrowRight, Search, FileText, Sparkles, Lock, Calculator, Clock, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { WorkspacePanel } from "./_workspace";
import { Greeting } from "./_greeting";
import { DashboardStats } from "./_stats";

export const dynamic = "force-dynamic";

type Hizmet = {
  icon: typeof Search;
  title: string;
  desc: string;
  href: string;
  rozet?: "ucretsiz" | "pro";
  pro?: boolean;
  cta?: string;
};

const HIZMETLER: Hizmet[] = [
  { icon: Search, title: "Emsal Karar Ara", desc: "10K+ Yargıtay, Danıştay kararı", href: "/emsal-arama" },
  { icon: Calculator, title: "Faiz & Tahsilat", desc: "Yasal/ticari faiz + İİK harç hesabı", href: "/faiz-hesaplayici", rozet: "ucretsiz" },
  { icon: Clock, title: "Zamanaşımı", desc: "Süre, bitiş ve durum hesaplama", href: "/zamanasimi", rozet: "ucretsiz" },
  { icon: ShieldCheck, title: "KVKK Uyum", desc: "Sektörel uyum checklist'i", href: "/kvkk", rozet: "ucretsiz" },
  { icon: FileText, title: "Dilekçe Üret", desc: "Emsallere atıflı Yapay Zeka taslak", href: "/dilekce" },
  { icon: Sparkles, title: "UYAP Dosyalarımda Yapay Zeka", desc: "Kendi davalarınla çalış", href: "/panel/ayarlar/abonelik", pro: true, cta: "Pro'ya Geç" },
];

export default async function AppDashboard() {
  const session = await auth();
  const name = session?.user?.name ?? session?.user?.email?.split("@")[0] ?? "";
  const isAdmin = (session?.user as { role?: string })?.role === "admin";

  return (
    <div className="space-y-6">
      <Greeting name={name} />

      <DashboardStats />

      {/* Hizmetler */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Hizmetler
        </h2>
        <div className="grid md:grid-cols-3 gap-4 stagger">
          {HIZMETLER.map((h) => (
            <Card
              key={h.title}
              className={`group hover-lift ${h.pro ? "border-accent/30 bg-accent/5" : ""}`}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <span
                    className={`rounded-xl p-2 transition-transform duration-300 group-hover:scale-110 ${
                      h.pro ? "bg-accent/15 text-accent" : "bg-primary/10 text-primary"
                    }`}
                  >
                    <h.icon className="h-5 w-5" />
                  </span>
                  {h.rozet === "ucretsiz" && (
                    <span className="text-[10px] uppercase tracking-wider rounded-full border border-emerald-400/30 bg-emerald-400/15 text-emerald-700 dark:text-emerald-300 px-2 py-0.5">
                      Ücretsiz
                    </span>
                  )}
                  {h.pro && !isAdmin && (
                    <span className="text-xs uppercase tracking-wider bg-accent text-accent-foreground px-2 py-0.5 rounded">
                      Pro
                    </span>
                  )}
                </div>
                <CardTitle className="text-base mt-2">{h.title}</CardTitle>
                <CardDescription>{h.desc}</CardDescription>
              </CardHeader>
              <CardContent>
                <Button asChild variant={h.pro ? "default" : "outline"} size="sm">
                  {/* Admin → Pro araç doğrudan açılır (yükseltme yok) */}
                  <Link href={h.pro && isAdmin ? "/panel/sorgu" : h.href}>
                    {h.pro && isAdmin ? "Aç" : (h.cta ?? "Aç")}{" "}
                    <ArrowRight className="h-3 w-3 ml-1 transition-transform duration-300 group-hover:translate-x-1" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Son işlemler — son üretimler, notlar, aramalar */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Son İşlemlerim
        </h2>
        <WorkspacePanel />
      </div>

      {/* Pro özellik teaser — admin'e gösterilmez (her şey zaten açık) */}
      {!isAdmin && (
        <Card className="border-dashed">
          <CardContent className="p-8 text-center">
            <Lock className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
            <h2 className="text-xl font-semibold mb-2">Kendi UYAP Dosyalarınla Yapay Zeka</h2>
            <p className="text-sm text-muted-foreground max-w-md mx-auto mb-4">
              Dosyalarınızı yükleyin, Yapay Zeka sadece sizin verilerinizle çalışsın. Verileriniz
              Türkiye&apos;de, şifrelenmiş ve sadece size özel.
            </p>
            <Button asChild>
              <Link href="/panel/ayarlar/abonelik">Pro Paketi İncele</Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
