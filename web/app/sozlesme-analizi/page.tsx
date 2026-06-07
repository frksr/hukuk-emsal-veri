import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { SozlesmeForm } from "./form";

export const metadata: Metadata = buildMetadata({
  title: "Sözleşme Analizi | AI ile Madde Bazlı Risk Tespiti",
  description:
    "PDF veya DOCX sözleşme yükleyin; AI madde madde risk analizi, eksik madde tespiti, fesih ve cezai şart kontrolü yapsın.",
  path: "/sozlesme-analizi",
  keywords: [
    "sözleşme analizi", "ai sözleşme inceleme", "sözleşme risk analizi",
    "cezai şart kontrolü", "fesih maddesi", "kvkk sözleşme", "ticari sözleşme",
  ],
});

export default function SozlesmePage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "Sözleşme", url: "/sozlesme-analizi" }])} />
      <div className="container py-10 max-w-6xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Sözleşme Analizi</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Sözleşme Analizi</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          Sözleşmenizi yükleyin veya metnini yapıştırın; sistem TBK, TTK ve KVKK çerçevesinde madde
          madde risk skorlasın, eksik maddeleri tespit etsin.
        </p>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 mb-6 text-sm">
          ⚠️ AI analizi, hukuki danışmanlığın yerine geçmez.
        </div>
        <SozlesmeForm />
      </div>
    </>
  );
}
