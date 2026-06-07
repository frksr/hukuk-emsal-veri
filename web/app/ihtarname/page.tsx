import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { IhtarnameForm } from "./ihtarname-form";

export const metadata: Metadata = buildMetadata({
  title: "İhtarname Üretici | Noter Onayına Hazır İhtarname Örneği",
  description:
    "TBK 117 ve İİK 51 referanslı ihtarname örneği üretin. Alacak temerrütü, kira tahliye, çek, fesih ihtarnameleri AI ile dakikalarda hazır.",
  path: "/ihtarname",
  keywords: [
    "ihtarname örneği", "noter ihtarnamesi", "tbk 117 ihtarname",
    "alacak ihtarnamesi", "kira tahliye ihtarnamesi", "çek ihtarnamesi",
    "fesih ihtarnamesi", "ihtarname yazımı",
  ],
});

export default function IhtarnamePage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "İhtarname", url: "/ihtarname" }])} />
      <div className="container py-10 max-w-6xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>İhtarname Üretici</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">İhtarname Üretici</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          Taraf ve alacak bilgilerini girin; sistem TBK 117, İİK 51, TBK 89 referansları ile noter onayına
          hazır ihtarname taslağı üretsin.
        </p>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 mb-6 text-sm">
          ⚠️ <strong>Yasal uyarı:</strong> AI taslağı, noter onayından önce avukat incelemesi gerekir.
        </div>
        <IhtarnameForm />
      </div>
    </>
  );
}
