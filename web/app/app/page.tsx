import Link from "next/link";
import { auth } from "@/auth";
import { ArrowRight, Search, FileText, Sparkles, Lock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

export default async function AppDashboard() {
  const session = await auth();
  const name = session?.user?.name ?? session?.user?.email?.split("@")[0] ?? "";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Hoş geldin, {name} 👋</h1>
        <p className="text-muted-foreground mt-1">Bugün hangi davadayız?</p>
      </div>

      {/* Hızlı erişim */}
      <div className="grid md:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <Search className="h-6 w-6 text-primary mb-2" />
            <CardTitle className="text-base">Emsal Karar Ara</CardTitle>
            <CardDescription>10K+ Yargıtay, Danıştay kararı</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm">
              <Link href="/emsal-arama">Aç <ArrowRight className="h-3 w-3 ml-1" /></Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <FileText className="h-6 w-6 text-primary mb-2" />
            <CardTitle className="text-base">Dilekçe Üret</CardTitle>
            <CardDescription>Emsallere atıflı AI taslak</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm">
              <Link href="/dilekce">Aç <ArrowRight className="h-3 w-3 ml-1" /></Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="border-accent/30 bg-accent/5">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-accent" />
              <span className="text-xs uppercase tracking-wider bg-accent text-accent-foreground px-2 py-0.5 rounded">Pro</span>
            </div>
            <CardTitle className="text-base mt-2">UYAP Dosyalarımda AI</CardTitle>
            <CardDescription>Kendi davalarınla çalış</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild size="sm">
              <Link href="/app/ayarlar/abonelik">Pro&apos;ya Geç <ArrowRight className="h-3 w-3 ml-1" /></Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Pro özellik teaser */}
      <Card className="border-dashed">
        <CardContent className="p-8 text-center">
          <Lock className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
          <h2 className="text-xl font-semibold mb-2">Kendi UYAP Dosyalarınla AI</h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto mb-4">
            Dosyalarınızı yükleyin, AI sadece sizin verilerinizle çalışsın. Verileriniz
            Türkiye'de, şifrelenmiş ve sadece size özel.
          </p>
          <Button asChild>
            <Link href="/app/ayarlar/abonelik">Pro Paketi İncele</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
