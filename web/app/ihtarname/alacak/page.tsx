import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { IhtarnameForm } from "../ihtarname-form";

export const metadata: Metadata = buildMetadata({
  title: "Alacak İhtarnamesi Örneği | Temerrüt İhtarı Noter Onaylı",
  description:
    "Alacak ihtarnamesi örneği oluşturun. Borçluyu temerrüde düşürmek için TBK 117 ve faiz başlangıcı referanslı noter onayına hazır temerrüt ihtarnamesi taslağı.",
  path: "/ihtarname/alacak",
  keywords: [
    "alacak ihtarnamesi",
    "alacak ihtarnamesi örneği",
    "temerrüt ihtarnamesi",
    "tbk 117 ihtar",
    "borç ödeme ihtarı",
    "noter alacak ihtarı",
    "faiz başlangıcı ihtar",
  ],
});

const FAQ = [
  {
    q: "Alacak ihtarnamesi neden çekilir?",
    a: "Vadesi belirli olmayan borçlarda borçluyu temerrüde düşürmek için ihtarname gerekir (TBK 117). İhtar, hem temerrüt faizinin başlangıç tarihini belirler hem de ileride açılacak icra takibi veya davada borçlunun ödemeye davet edildiğini ispatlar.",
  },
  {
    q: "İhtarname temerrüt faizini başlatır mı?",
    a: "Evet. Vadesi belirlenmemiş alacaklarda borçlu, ancak ihtar ile temerrüde düşer ve temerrüt faizi ihtarın tebliğini izleyen günden itibaren işlemeye başlar. Vadesi belli alacaklarda ise vade sonunda temerrüt kendiliğinden oluşur.",
  },
  {
    q: "Alacak ihtarnamesinde hangi bilgiler bulunmalı?",
    a: "Tarafların kimlik ve adres bilgileri, alacağın kaynağı (sözleşme, fatura, senet), tutarı, ödeme için verilen süre ve ödenmemesi halinde yasal yollara başvurulacağı açıkça yer almalıdır. Tutarın ve dayanağın net olması ispat açısından önemlidir.",
  },
  {
    q: "İhtardan sonra ne yapılır?",
    a: "Verilen süre içinde ödeme yapılmazsa alacaklı icra takibi başlatabilir veya alacak davası açabilir. İhtarname, bu aşamada temerrüt ve faiz talebinin dayanağı olarak kullanılır.",
  },
];

export default function AlacakIhtarnamePage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbJsonLd([
            { name: "Ana Sayfa", url: "/" },
            { name: "İhtarname", url: "/ihtarname" },
            { name: "Alacak İhtarnamesi", url: "/ihtarname/alacak" },
          ]),
          faqJsonLd(FAQ.map((f) => ({ question: f.q, answer: f.a }))),
        ]}
      />
      <div className="container py-10 max-w-6xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <Link href="/" className="hover:text-foreground">
            Ana Sayfa
          </Link>{" "}
          /{" "}
          <Link href="/ihtarname" className="hover:text-foreground">
            İhtarname
          </Link>{" "}
          / <span>Alacak İhtarnamesi</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-3">
          Alacak İhtarnamesi Örneği
        </h1>
        <p className="text-muted-foreground mb-6 max-w-3xl">
          Borçluyu temerrüde düşürmek ve temerrüt faizini başlatmak için TBK 117
          referanslı alacak (temerrüt) ihtarnamesi taslağı oluşturun. Taraf,
          alacak ve süre bilgilerini girin; sistem noter onayına hazır metni
          hazırlasın.
        </p>

        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 mb-6 text-sm">
          ⚠️ <strong>Yasal uyarı:</strong> Yapay Zeka taslağı, noter onayından ve
          icra takibi başlatılmadan önce avukat incelemesi gerektirir.
        </div>

        <IhtarnameForm />

        <section aria-labelledby="alacak-sss" className="mt-12 max-w-3xl">
          <h2 id="alacak-sss" className="text-2xl font-bold mb-6">
            Sıkça Sorulan Sorular
          </h2>
          <div className="space-y-6">
            {FAQ.map((item) => (
              <div key={item.q}>
                <h3 className="font-semibold mb-1">{item.q}</h3>
                <p className="text-muted-foreground text-sm">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-12 max-w-3xl">
          <h2 className="text-xl font-bold mb-3">İlgili araçlar</h2>
          <ul className="list-disc pl-5 space-y-1 text-sm">
            <li>
              <Link
                href="/faiz-hesaplayici"
                className="text-primary hover:underline"
              >
                Temerrüt faizi hesaplama
              </Link>
            </li>
            <li>
              <Link
                href="/zamanasimi"
                className="text-primary hover:underline"
              >
                Alacak zamanaşımı hesaplama
              </Link>
            </li>
            <li>
              <Link
                href="/ihtarname/kira-tahliye"
                className="text-primary hover:underline"
              >
                Kira tahliye ihtarnamesi örneği
              </Link>
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}
