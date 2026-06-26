import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { MAKALELER } from "./makaleler";

const API_BASE =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export const revalidate = 300;

type Kart = { slug: string; baslik: string; ozet: string };

async function getYayinlananlar(): Promise<Kart[]> {
  try {
    const res = await fetch(`${API_BASE}/api/icerik/liste`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return [];
    const json = await res.json();
    const data = (json?.data as Array<{
      slug: string;
      title: string;
      excerpt?: string;
      meta_description?: string;
    }>) ?? [];
    return data.map((m) => ({
      slug: m.slug,
      baslik: m.title,
      ozet: m.excerpt || m.meta_description || "",
    }));
  } catch {
    return [];
  }
}

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

export default async function BlogIndexPage() {
  // Statik küratörlü makaleler + admin panelden yayınlananları birleştir.
  // Aynı slug varsa statik (küratörlü) öncelikli.
  const yayinlananlar = await getYayinlananlar();
  const staticSlugs = new Set(MAKALELER.map((m) => m.slug));
  const kartlar: Kart[] = [
    ...MAKALELER.map((m) => ({ slug: m.slug, baslik: m.baslik, ozet: m.ozet })),
    ...yayinlananlar.filter((m) => !staticSlugs.has(m.slug)),
  ];

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
          {kartlar.map((m) => (
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
