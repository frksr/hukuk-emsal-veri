import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { KapakYerTutucu } from "./_kapak";

const API_BASE =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export const revalidate = 300;

type Kart = { slug: string; baslik: string; ozet: string; kapak?: string | null };

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
      cover_image?: string | null;
    }>) ?? [];
    return data.map((m) => ({
      slug: m.slug,
      baslik: m.title,
      ozet: m.excerpt || m.meta_description || "",
      kapak: m.cover_image,
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
  // Tüm makaleler admin panelden (blog_articles tablosu) yönetilir — tekil
  // kaynak. Eskiden statik/küratörlü ayrı bir liste vardı (makaleler.ts); bu
  // ikili yapı bazı yazıların admin panelde görünmemesine ve kapak
  // görselinin hep placeholder çıkmasına yol açıyordu; kaldırıldı.
  const kartlar: Kart[] = await getYayinlananlar();

  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Ana Sayfa", url: "/" },
          { name: "Rehber", url: "/blog" },
        ])}
      />
      <div className="container py-10 max-w-5xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <Link href="/" className="hover:text-foreground">
            Ana Sayfa
          </Link>{" "}
          / <span>Rehber</span>
        </nav>

        <div className="inline-flex items-center gap-2 bg-primary/10 text-primary text-xs font-semibold px-3 py-1 rounded-full mb-4 uppercase tracking-wide">
          İcra ve Tahsilat Hukuku Rehberi
        </div>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Hukuk Rehberi</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          Emsal karar, ihtarname, icra ve faiz konularında pratik, kaynak
          gösterimli rehberler. Her rehber, ilgili aracımıza bağlanır.
        </p>

        {kartlar.length === 0 ? (
          <p className="text-muted-foreground">Henüz yayınlanmış rehber yok.</p>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 stagger">
            {kartlar.map((m) => (
              <article
                key={m.slug}
                className="group hover-lift rounded-xl border bg-card overflow-hidden flex flex-col"
              >
                <Link
                  href={`/blog/${m.slug}`}
                  className="block aspect-[16/9] overflow-hidden bg-muted"
                >
                  {m.kapak ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={m.kapak}
                      alt=""
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                  ) : (
                    <KapakYerTutucu slug={m.slug} />
                  )}
                </Link>
                <div className="p-5 flex flex-col flex-1">
                  <h2 className="text-lg font-semibold mb-1.5 leading-snug">
                    <Link href={`/blog/${m.slug}`} className="hover:text-primary">
                      {m.baslik}
                    </Link>
                  </h2>
                  <p className="text-sm text-muted-foreground mb-3 line-clamp-3 flex-1">
                    {m.ozet}
                  </p>
                  <Link
                    href={`/blog/${m.slug}`}
                    className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                  >
                    Devamını oku
                    <ArrowRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-1" />
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
