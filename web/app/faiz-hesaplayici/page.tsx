import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { FaizForm } from "./faiz-form";

export const metadata: Metadata = buildMetadata({
  title: "İcra Faiz Hesaplama | Yasal & Ticari Avans Faizi 2026",
  description:
    "İcra takibinde yasal faiz, ticari avans faizi ve TCMB reeskont oranı ile temerrüt faizi hesaplama. İİK cezaevi ve tahsil harçları, vekalet ücreti dahil tam tahsilat tutarı.",
  path: "/faiz-hesaplayici",
  keywords: [
    "icra faiz hesaplama", "yasal faiz oranı 2026", "ticari avans faizi",
    "tcmb reeskont", "iik harçları", "tahsil harcı", "vekalet ücreti hesaplama",
    "temerrüt faizi", "icra takibi faiz",
  ],
});

const FAQ = [
  {
    q: "Yasal faiz oranı 2026'da ne kadardır?",
    a: "TBK 88 kapsamındaki yasal faiz oranı 2026 yılı için yıllık %9 olarak uygulanmaktadır. Ticari işlerde TCMB avans faizi ise yıllık ~%47.5 civarındadır.",
  },
  {
    q: "Ticari faiz ile yasal faiz arasındaki fark nedir?",
    a: "Tacirler arası ticari işlerde TCMB'nin ilan ettiği avans faizi (kısa vadeli) uygulanır. Adi alacaklarda ise TBK 88 yasal faiz oranı geçerlidir.",
  },
  {
    q: "İcra takibinde cezaevi harcı nasıl hesaplanır?",
    a: "Cezaevi harcı, alacağın (anapara + faiz) toplam tutarı üzerinden %2 oranında hesaplanır ve tahsil edilir.",
  },
];

export default function FaizPage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "Faiz Hesaplayıcı", url: "/faiz-hesaplayici" }])} />
      <JsonLd data={faqJsonLd(FAQ)} />
      <div className="container py-10 max-w-6xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Faiz Hesaplayıcı</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Faiz & Tahsilat Hesaplayıcı</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          İcra takibinde anapara, temerrüt tarihi ve faiz türünü girin; sistem yıllık bazda faizi, İİK
          cezaevi ve tahsil harçlarını, vekalet ücretini ve toplam alacağı hesaplasın.
        </p>
        <FaizForm />

        <section className="mt-12 prose prose-sm max-w-none">
          <h2 className="text-2xl font-bold mb-4">Sıkça Sorulan Sorular</h2>
          <div className="space-y-4">
            {FAQ.map((f, i) => (
              <details key={i} className="rounded-lg border bg-card p-5">
                <summary className="cursor-pointer font-semibold">{f.q}</summary>
                <p className="mt-3 text-muted-foreground">{f.a}</p>
              </details>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
