import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { TrendPanel } from "./panel";

export const metadata: Metadata = buildMetadata({
  title: "Karar Trend Paneli | Yargıtay Danıştay Konu Bazlı İstatistik",
  description:
    "Yargıtay ve Danıştay kararlarının yıllık dağılımı, konu bazlı trendler, mahkeme yoğunlukları. İcra, tahsilat, ihtar konularında veriye dayalı içgörü.",
  path: "/trend",
  keywords: ["yargıtay istatistik", "danıştay trend", "karar dağılımı", "hukuki içgörü"],
});

export default function TrendPage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "Trend", url: "/trend" }])} />
      <div className="container py-10">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Karar Trend Paneli</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Karar Trend Paneli</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          10.000+ Yargıtay, Danıştay ve AİHM kararı üzerinde yıllık trendler, konu dağılımları ve mahkeme
          yoğunlukları. Veriye dayalı strateji için.
        </p>
        <TrendPanel />
      </div>
    </>
  );
}
