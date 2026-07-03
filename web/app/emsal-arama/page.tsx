import type { Metadata } from "next";
import Link from "next/link";
import { Gavel } from "lucide-react";

import { buildMetadata } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { AramaForm } from "./arama-form";

export const metadata: Metadata = buildMetadata({
  title: "İcra ve Tahsilat Hukuku Emsal Karar Arama | Yargıtay, Danıştay, AİHM",
  description:
    "10.000+ emsal karar arasında doğal dil ile arama yapın. Uzmanlık alanımız icra ve tahsilat hukuku (Yargıtay 12. Hukuk Dairesi); ayrıca Danıştay ve AİHM kararları da veritabanımızda.",
  path: "/emsal-arama",
  keywords: [
    "icra hukuku emsal karar",
    "tahsilat hukuku emsal karar",
    "yargıtay 12 hukuk dairesi",
    "icra takibi emsal karar",
    "haciz emsal karar",
    "ödeme emrine itiraz emsal",
    "emsal karar arama",
    "yargıtay karar arama",
    "danıştay karar arama",
    "aihm hudoc",
    "ihtarname emsal",
  ],
});

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";

const searchActionJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: "Emsal Karar Arama",
  description:
    "Yargıtay, Danıştay ve AİHM kararları arasında doğal dil ile arama.",
  potentialAction: {
    "@type": "SearchAction",
    target: {
      "@type": "EntryPoint",
      urlTemplate: `${SITE_URL}/emsal-arama?q={search_term_string}`,
    },
    "query-input": "required name=search_term_string",
  },
};

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    {
      "@type": "ListItem",
      position: 1,
      name: "Ana Sayfa",
      item: `${SITE_URL}/`,
    },
    {
      "@type": "ListItem",
      position: 2,
      name: "Emsal Arama",
      item: `${SITE_URL}/emsal-arama`,
    },
  ],
};

export default function EmsalAramaPage() {
  return (
    <>
      <JsonLd data={searchActionJsonLd} />
      <JsonLd data={breadcrumbJsonLd} />

      <main className="mx-auto w-full max-w-6xl px-4 py-10 sm:py-14">
        {/* Breadcrumb */}
        <nav aria-label="Sayfa konumu" className="mb-6 text-sm text-muted-foreground">
          <ol className="flex flex-wrap items-center gap-2">
            <li>
              <Link href="/" className="hover:text-foreground hover:underline">
                Ana Sayfa
              </Link>
            </li>
            <li aria-hidden>/</li>
            <li aria-current="page" className="font-medium text-foreground">
              Emsal Arama
            </li>
          </ol>
        </nav>

        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Emsal Karar Arama
          </h1>
          <p className="mt-3 max-w-3xl text-base leading-relaxed text-muted-foreground">
            Yargıtay, Danıştay ve AİHM (HUDOC) veritabanlarından 10.000&apos;den
            fazla emsal karar arasında doğal dilde arama yapın. İcra takibi,
            tahsilat hukuku, ihtarname örnekleri ve menfi tespit gibi
            konularda saniyeler içinde benzerlik skoruna göre sıralı sonuçlar
            elde edin. Karar metnini görüntüleyin, kopyalayın veya dilekçenize
            atıf olarak ekleyin.
          </p>
        </header>

        <section
          aria-label="Uzmanlık alanımız"
          className="mb-8 rounded-xl border border-primary/20 bg-primary/5 p-5 sm:p-6"
        >
          <div className="flex items-start gap-3">
            <div className="rounded-full bg-primary/10 p-2 text-primary shrink-0">
              <Gavel className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-foreground">
                Uzmanlık alanımız: İcra ve Tahsilat Hukuku
              </h2>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                Veritabanımızdaki kararların büyük çoğunluğu icra takibi, haciz,
                ödeme emrine itiraz, ihtarname ve amme alacağının tahsili gibi
                icra ve tahsilat hukuku konularını kapsıyor — başta Yargıtay 12.
                Hukuk Dairesi (icra ve iflas) olmak üzere. Bu sayede icra
                dosyalarınızla ilgili emsal aramalarında en derin ve güncel
                sonuçları sunuyoruz. Danıştay&apos;ın vergi/amme alacağı tahsilat
                kararları ve AİHM (HUDOC) emsalleri de ayrıca veritabanımızda yer
                alıyor.
              </p>
            </div>
          </div>
        </section>

        <AramaForm />
      </main>
    </>
  );
}
