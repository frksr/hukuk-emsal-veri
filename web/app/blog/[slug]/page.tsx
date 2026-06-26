import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  buildMetadata,
  breadcrumbJsonLd,
  buildArticleJsonLd,
  faqJsonLd,
} from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { makaleBul } from "../makaleler";

const API_BASE =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

// Yeni yayınlanan makaleler kısa sürede görünsün.
export const revalidate = 300;
export const dynamicParams = true;

type Faq = { soru: string; cevap: string };
interface Makale {
  slug: string;
  title: string;
  excerpt?: string;
  body?: string;
  meta_title?: string;
  meta_description?: string;
  keywords?: string[];
  faq?: Faq[];
  author?: string;
  published_at?: string;
  updated_at?: string;
}

async function getMakale(slug: string): Promise<Makale | null> {
  try {
    const res = await fetch(
      `${API_BASE}/api/icerik/makale/${encodeURIComponent(slug)}`,
      { next: { revalidate: 300 } }
    );
    if (!res.ok) return null;
    const json = await res.json();
    return (json?.data as Makale) ?? null;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const m = await getMakale(params.slug);
  if (!m) return { robots: { index: false } };
  return buildMetadata({
    title: (m.meta_title || m.title).slice(0, 65),
    description:
      (m.meta_description || m.excerpt || m.title).slice(0, 170),
    path: `/blog/${m.slug}`,
    type: "article",
    keywords: m.keywords,
    publishedTime: m.published_at,
    modifiedTime: m.updated_at,
    authors: m.author ? [m.author] : undefined,
  });
}

// --- Hafif Markdown render (bağımlılıksız): ## h2, ### h3, - liste, **kalın** ---
function inline(text: string, keyBase: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    if (/^\*\*[^*]+\*\*$/.test(p)) {
      return <strong key={`${keyBase}-${i}`}>{p.slice(2, -2)}</strong>;
    }
    return <span key={`${keyBase}-${i}`}>{p}</span>;
  });
}

function renderBody(body: string): React.ReactNode[] {
  const lines = (body || "").split(/\r?\n/);
  const nodes: React.ReactNode[] = [];
  let para: string[] = [];
  let list: string[] = [];
  let k = 0;

  const flushPara = () => {
    if (para.length) {
      nodes.push(<p key={`p-${k++}`}>{inline(para.join(" "), `p${k}`)}</p>);
      para = [];
    }
  };
  const flushList = () => {
    if (list.length) {
      nodes.push(
        <ul key={`ul-${k++}`} className="list-disc pl-5 space-y-1">
          {list.map((li, i) => (
            <li key={i}>{inline(li, `li${k}-${i}`)}</li>
          ))}
        </ul>
      );
      list = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^###\s+/.test(line)) {
      flushPara();
      flushList();
      nodes.push(
        <h3 key={`h3-${k++}`} className="text-lg font-semibold mt-6 mb-2">
          {line.replace(/^###\s+/, "")}
        </h3>
      );
    } else if (/^##\s+/.test(line)) {
      flushPara();
      flushList();
      nodes.push(
        <h2 key={`h2-${k++}`} className="text-2xl font-bold mt-8 mb-3">
          {line.replace(/^##\s+/, "")}
        </h2>
      );
    } else if (/^[-*]\s+/.test(line)) {
      flushPara();
      list.push(line.replace(/^[-*]\s+/, ""));
    } else if (line.trim() === "") {
      flushPara();
      flushList();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return nodes;
}

export default async function BlogMakalePage({
  params,
}: {
  params: { slug: string };
}) {
  const m = await getMakale(params.slug);
  if (!m) notFound();

  const faqList = (m.faq || []).filter((f) => f.soru && f.cevap);

  return (
    <>
      <JsonLd
        data={[
          breadcrumbJsonLd([
            { name: "Ana Sayfa", url: "/" },
            { name: "Rehber", url: "/blog" },
            { name: m.title, url: `/blog/${m.slug}` },
          ]),
          buildArticleJsonLd({
            title: m.meta_title || m.title,
            description: m.meta_description || m.excerpt || m.title,
            path: `/blog/${m.slug}`,
            datePublished: m.published_at || new Date().toISOString(),
            dateModified: m.updated_at,
            authorName: m.author,
          }),
          ...(faqList.length
            ? [
                faqJsonLd(
                  faqList.map((f) => ({ question: f.soru, answer: f.cevap }))
                ),
              ]
            : []),
        ]}
      />
      <article className="container py-10 max-w-3xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <Link href="/" className="hover:text-foreground">
            Ana Sayfa
          </Link>{" "}
          /{" "}
          <Link href="/blog" className="hover:text-foreground">
            Rehber
          </Link>{" "}
          / <span>{m.title}</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-3">{m.title}</h1>
        {m.author && (
          <p className="text-sm text-muted-foreground mb-6">{m.author}</p>
        )}

        <div className="prose prose-sm md:prose-base max-w-none space-y-4">
          {renderBody(m.body || "")}
        </div>

        {faqList.length > 0 && (
          <section className="mt-10">
            <h2 className="text-2xl font-bold mb-4">Sıkça Sorulan Sorular</h2>
            <div className="space-y-5">
              {faqList.map((f, i) => (
                <div key={i}>
                  <h3 className="font-semibold mb-1">{f.soru}</h3>
                  <p className="text-muted-foreground text-sm">{f.cevap}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        <p className="mt-8 text-xs text-muted-foreground">
          Bu içerik bilgilendirme amaçlıdır, hukuki danışmanlık değildir. Somut
          durumunuz için bir avukata danışın.
        </p>
      </article>
    </>
  );
}
