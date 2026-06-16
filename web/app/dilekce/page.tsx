import type { Metadata } from "next";
import { buildMetadata, buildBreadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { DilekceForm } from "./dilekce-form";

export const metadata: Metadata = buildMetadata({
  title: "Yapay Zeka Dilekçe Üretici | Emsallere Atıflı Hukuki Dilekçe",
  description:
    "Davanızı doğal dille anlatın. Yapay Zeka, Yargıtay 12. HD ve Danıştay kararlarına atıfla itirazın iptali, ihalenin feshi, menfi tespit, tahsilat dilekçesi üretsin.",
  path: "/dilekce",
  keywords: [
    "dilekçe örneği", "itirazın iptali dilekçesi", "menfi tespit dilekçesi",
    "ihalenin feshi dilekçesi", "tahsilat dilekçesi", "ai dilekçe", "emsal kararlı dilekçe",
  ],
});

export default function DilekcePage() {
  return (
    <>
      <JsonLd data={buildBreadcrumbJsonLd([{ name: "Ana Sayfa", path: "/" }, { name: "Dilekçe Üretici", path: "/dilekce" }])} />
      <div className="container py-10 max-w-6xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Dilekçe Üretici</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Emsal-Bağlamlı Dilekçe Üretici</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          Davanızı serbest metinle anlatın. Sistem konuya uygun Yargıtay 12. HD ve Danıştay emsal kararlarını
          bulup, bu kararlara atıflı bir dilekçe taslağı üretir. Her atıf gerçek esas/karar numarasıyla
          desteklenir.
        </p>
        <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/20 p-4 mb-6 text-sm">
          ⚠️ <strong>Yasal uyarı:</strong> Yapay Zeka çıktısı taslak niteliğindedir. Mahkemeye sunmadan önce mutlaka
          bir avukatın incelemesinden geçmelidir.
        </div>
        <DilekceForm />
      </div>
    </>
  );
}
