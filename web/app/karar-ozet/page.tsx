import type { Metadata } from "next";
import { Suspense } from "react";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { OzetForm } from "./ozet-form";

export const metadata: Metadata = buildMetadata({
  title: "Karar Özetleyici | Yargıtay Kararları Sade Türkçe Özet",
  description:
    "Uzun Yargıtay ve Danıştay kararlarını 3-10 paragraflık sade Türkçe özetlere dönüştürün. Yapay Zeka destekli karar özetleyici ile dakikalar yerine saniyelerde anlayın.",
  path: "/karar-ozet",
  keywords: [
    "yargıtay kararı özeti", "danıştay kararı özeti", "karar özetleme",
    "hukuki karar sadeleştirme", "ai karar özet", "içtihat özet",
  ],
});

export default function KararOzetPage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([
        { name: "Ana Sayfa", url: "/" },
        { name: "Karar Özetleyici", url: "/karar-ozet" },
      ])} />
      <div className="container py-10 max-w-5xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Karar Özetleyici</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Karar Özetleyici</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          Karar metnini yapıştırın, sistem 3 paragraflık sade Türkçe özet üretsin: davacı ne istedi, mahkeme
          ne dedi, sonuç ne. Hukuki terimler parantez içinde açıklamalı.
        </p>
        <Suspense fallback={null}>
          <OzetForm />
        </Suspense>
      </div>
    </>
  );
}
