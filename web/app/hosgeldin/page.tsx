import Link from "next/link";
import type { Metadata } from "next";
import { CheckCircle2, ArrowRight, Search, FileText, Calculator } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Hoş Geldin — Hesabın Hazır | Hukuk Emsal",
  description:
    "Hukuk Emsal hesabın hazır. Emsal karar arama, AI dilekçe taslağı ve faiz/zamanaşımı hesaplama araçlarına hemen başla.",
  path: "/hosgeldin",
  noIndex: true,
});

export default function HosgeldinPage() {
  return (
    <div className="container max-w-3xl py-16">
      <div className="text-center mb-10">
        <CheckCircle2 className="h-16 w-16 text-emerald-500 mx-auto mb-4" />
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Hesabın hazır! 🎉</h1>
        <p className="text-muted-foreground max-w-md mx-auto">
          Free hesabınla bu özelliklere şimdi erişebilirsin:
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-4 mb-10">
        {[
          { icon: Search, t: "40 emsal arama/gün", d: "Anonim'in 2 katı" },
          { icon: FileText, t: "6 dilekçe/gün", d: "AI atıflı taslak" },
          { icon: Calculator, t: "Sınırsız hesap", d: "Faiz + zamanaşımı" },
        ].map((x, i) => (
          <Card key={i}><CardContent className="p-5 text-center">
            <x.icon className="h-8 w-8 text-primary mx-auto mb-2" />
            <div className="font-semibold mb-1">{x.t}</div>
            <div className="text-xs text-muted-foreground">{x.d}</div>
          </CardContent></Card>
        ))}
      </div>

      <div className="text-center space-y-3">
        <Button asChild size="lg">
          <Link href="/app">Dashboard&apos;a Git <ArrowRight className="ml-2 h-4 w-4" /></Link>
        </Button>
        <div>
          <Link href="/app/ayarlar/abonelik" className="text-sm text-muted-foreground hover:text-foreground">
            Pro paketi ile daha fazlasını al →
          </Link>
        </div>
      </div>
    </div>
  );
}
