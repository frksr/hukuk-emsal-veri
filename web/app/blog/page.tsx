import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { MAKALELER } from "./makaleler";

export const metadata: Metadata = buildMetadata({
  title: "Hukuk Rehberi ve Blog | Emsal Karar, İhtarname, İcra",
  description:
    "Emsal karar, ihtarname, icra takibi ve faiz hesaplama üzerine pratik hukuk rehberleri. Araçlarımızla desteklenmiş, sade anlatımlı içerikler.",
  path: "/blog",
  keywords: [
    "hukuk rehberi",
    "emsal karar nedir",
    "ihtarname nasıl çekilir",
    "icra takibi rehberi",
    "hukuk blog",
  ],
});

export default function BlogIndexPage() {
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Ana Sayfa", url: "/" },
          { name: "Rehber", url: "/blog" },
        ])}
      />
      <div className="container py-10 max-w-4xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <Link href="/" className="hover:text-foreground">
            Ana Sayfa
          </Link>{" "}
          / <span>Rehber</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-3">Hukuk Rehberi</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          Emsal karar, ihtarname, icra ve faiz konularında pratik, kaynak
          gösterimli rehberler. Her rehber, ilgili aracımıza bağlanır.
        </p>

        <div className="space-y-6">
          {MAKALELER.map((m) => (
            <article
              key={m.slug}
              className="rounded-lg border p-5 hover:border-primary/40 transition-colors"
            >
              <h2 className="text-xl font-semibold mb-1">
                <Link
                  href={`/blog/${m.slug}`}
                  className="hover:text-primary"
                >
                  {m.baslik}
                </Link>
              </h2>
              <p className="text-sm text-muted-foreground mb-2">{m.ozet}</p>
              <Link
                href={`/blog/${m.slug}`}
                className="text-sm text-primary hover:underline"
              >
                Devamını oku →
              </Link>
            </article>
          ))}
        </div>
      </div>
    </>
  );
}
