import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { KarsiArgumentForm } from "./form";

export const metadata: Metadata = buildMetadata({
  title: "Karşı Argüman Öngörüsü | Davada Karşı Taraf Ne Diyebilir?",
  description:
    "Davadan önce karşı tarafın hangi argümanları kullanabileceğini AI ile öngörün. Emsal kararlara dayalı rebuttal önerileri.",
  path: "/karsi-argument",
  keywords: ["karşı argüman", "dava stratejisi", "rebuttal", "davada karşı taraf", "ai hukuk asistanı"],
});

export default function KarsiArgumentPage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "Karşı Argüman", url: "/karsi-argument" }])} />
      <div className="container py-10 max-w-5xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Karşı Argüman Öngörüsü</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Karşı Argüman Öngörüsü</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          Kendi tezinizi yazın; AI emsal kararlara bakarak karşı tarafın olası argümanlarını sıralasın, her
          biri için güç skoru ve rebuttal önerisi versin.
        </p>
        <KarsiArgumentForm />
      </div>
    </>
  );
}
