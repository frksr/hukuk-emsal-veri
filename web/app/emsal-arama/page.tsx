import type { Metadata } from "next";
import Link from "next/link";

import { buildMetadata } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import EmsalAramaClient from "./emsal-arama-client";

export const metadata: Metadata = buildMetadata({
  title: "Türk Hukuk Emsal Karar Arama | Yargıtay, Danıştay, AİHM",
  description:
    "10.000+ emsal karar arasında doğal dil ile arama yapın. İcra, tahsilat, ihtar konularında AI destekli emsal bulucu.",
  path: "/emsal-arama",
  keywords: [
    "emsal karar arama",
    "yargıtay karar arama",
    "danıştay karar arama",
    "aihm hudoc",
    "icra emsal kararları",
    "tahsilat emsal karar",
    "ihtarname emsal",
    "yargıtay 12 hukuk dairesi",
  ],
});

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukemsal.tr";

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
        <nav aria-label="Sayfa konumu" className="mb-6 text-sm text-slate-500">
          <ol className="flex flex-wrap items-center gap-2">
            <li>
              <Link href="/" className="hover:text-slate-900 hover:underline">
                Ana Sayfa
              </Link>
            </li>
            <li aria-hidden>/</li>
            <li aria-current="page" className="font-medium text-slate-900">
              Emsal Arama
            </li>
          </ol>
        </nav>

        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            Emsal Karar Arama
          </h1>
          <p className="mt-3 max-w-3xl text-base leading-relaxed text-slate-600">
            Yargıtay, Danıştay ve AİHM (HUDOC) veritabanlarından 10.000&apos;den
            fazla emsal karar arasında doğal dilde arama yapın. İcra takibi,
            tahsilat hukuku, ihtarname örnekleri ve menfi tespit gibi
            konularda saniyeler içinde benzerlik skoruna göre sıralı sonuçlar
            elde edin. Karar metnini görüntüleyin, kopyalayın veya dilekçenize
            atıf olarak ekleyin.
          </p>
        </header>

        <EmsalAramaClient />
      </main>
    </>
  );
}
