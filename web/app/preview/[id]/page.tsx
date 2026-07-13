import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

// Önizleme sayfası: yayınlanmamış taslakları gösterir. ARAMA MOTORLARINA KAPALI
// (noindex,nofollow) ve her istekte taze (cache yok). Yol tahmin edilemez bir
// preview_id içerir; API kimliği yerine bu id ile korunur.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export const metadata: Metadata = {
  title: "Önizleme",
  robots: { index: false, follow: false },
};

const API_BASE =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

type Faq = { soru: string; cevap: string };
interface Onizleme {
  slug: string;
  title: string;
  excerpt?: string;
  body?: string;
  meta_description?: string;
  keywords?: string[];
  faq?: Faq[];
  author?: string;
  cover_image?: string | null;
  status?: string;
}

async function getOnizleme(id: string): Promise<Onizleme | null> {
  try {
    const res = await fetch(
      `${API_BASE}/api/publisher/preview/${encodeURIComponent(id)}`,
      { cache: "no-store" }
    );
    if (!res.ok) return null;
    const json = await res.json();
    return (json?.data as Onizleme) ?? null;
  } catch {
    return null;
  }
}

// Hafif markdown render — blog/[slug]/page.tsx ile aynı kuralların sadeleştirilmiş
// hali (## h2, ### h3, - liste, **kalın**, [metin](url), > kutu, ![alt](url)).
const IMG_RE = /^!\[([^\]]*)\]\(([^)\s]+)\)/;
function inline(text: string, key: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  text.split(/(\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*)/g).forEach((seg, i) => {
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(seg);
    if (link) {
      out.push(
        <a key={`${key}-a${i}`} href={link[2]} className="text-primary font-medium hover:underline">
          {link[1]}
        </a>
      );
    } else if (/^\*\*[^*]+\*\*$/.test(seg)) {
      out.push(<strong key={`${key}-b${i}`}>{seg.slice(2, -2)}</strong>);
    } else if (seg) {
      out.push(<span key={`${key}-s${i}`}>{seg}</span>);
    }
  });
  return out;
}

function renderBody(body: string): React.ReactNode[] {
  const lines = (body || "").split(/\r?\n/);
  const nodes: React.ReactNode[] = [];
  let para: string[] = [];
  let k = 0;
  const flush = () => {
    if (para.length) {
      nodes.push(<p key={`p${k++}`}>{inline(para.join(" "), `p${k}`)}</p>);
      para = [];
    }
  };
  for (const raw of lines) {
    const line = raw.trim();
    const img = IMG_RE.exec(line);
    if (/^###\s+/.test(line)) {
      flush();
      nodes.push(<h3 key={`h3${k++}`} className="text-lg font-semibold mt-6 mb-2">{line.replace(/^###\s+/, "")}</h3>);
    } else if (/^##\s+/.test(line)) {
      flush();
      nodes.push(<h2 key={`h2${k++}`} className="text-2xl font-bold mt-8 mb-3">{line.replace(/^##\s+/, "")}</h2>);
    } else if (img) {
      flush();
      // eslint-disable-next-line @next/next/no-img-element
      nodes.push(<img key={`img${k++}`} src={img[2]} alt={img[1]} className="my-6 w-full rounded-lg border" />);
    } else if (/^[-*]\s+/.test(line)) {
      flush();
      nodes.push(<li key={`li${k++}`} className="ml-5 list-disc">{inline(line.replace(/^[-*]\s+/, ""), `li${k}`)}</li>);
    } else if (line === "") {
      flush();
    } else {
      para.push(line);
    }
  }
  flush();
  return nodes;
}

export default async function OnizlemePage({
  params,
}: {
  params: { id: string };
}) {
  const m = await getOnizleme(params.id);
  if (!m) notFound();
  const faqList = (m.faq || []).filter((f) => f.soru && f.cevap);

  return (
    <article className="container py-10 max-w-3xl">
      <div className="mb-6 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <strong>Önizleme</strong> — bu yazı henüz yayında değil
        {m.status ? ` (durum: ${m.status})` : ""}. Sayfa arama motorlarına kapalıdır.
      </div>

      <h1 className="text-3xl md:text-4xl font-bold mb-3">{m.title}</h1>
      {m.author && <p className="text-sm text-muted-foreground mb-6">{m.author}</p>}

      {m.cover_image && (
        <div className="mb-8 aspect-[16/9] w-full overflow-hidden rounded-xl border">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={m.cover_image} alt="" className="h-full w-full object-cover" />
        </div>
      )}

      <div className="prose prose-base md:prose-lg max-w-none leading-relaxed space-y-6">
        {renderBody(m.body || "")}
      </div>

      {faqList.length > 0 && (
        <section className="mt-10">
          <h2 className="text-2xl font-bold mb-4">Sıkça Sorulan Sorular</h2>
          <div className="space-y-3">
            {faqList.map((f, i) => (
              <div key={i} className="rounded-lg border bg-card p-4">
                <h3 className="font-semibold mb-1.5">{f.soru}</h3>
                <p className="text-muted-foreground text-sm">{f.cevap}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      <p className="mt-10 text-xs text-muted-foreground">
        <Link href="/blog" className="hover:underline">← Rehber</Link>
      </p>
    </article>
  );
}
