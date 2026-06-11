import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FileText, Scale, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { JsonLd } from "@/components/seo/json-ld";
import { buildArticleJsonLd, buildBreadcrumbJsonLd } from "@/lib/seo";

const API_BASE =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukemsal.tr";

// ISR: karar metni değişmez — günde bir tazele yeterli.
export const revalidate = 86400;
export const dynamicParams = true;

const KAYNAK_ETIKET: Record<string, string> = {
  yargitay: "Yargıtay",
  danistay: "Danıştay",
  hudoc: "AİHM (HUDOC)",
  aym: "Anayasa Mahkemesi",
};

interface Karar {
  id: string;
  source?: string;
  court_chamber?: string;
  case_no?: string;
  decision_no?: string;
  decision_date?: string;
  topic_tags?: string;
  cleaned_text?: string;
  source_url?: string;
  anonymization_check?: string;
}

async function getKarar(id: string): Promise<Karar | null> {
  try {
    const res = await fetch(
      `${API_BASE}/api/arama/full/${encodeURIComponent(id)}`,
      { next: { revalidate: 86400 } }
    );
    if (!res.ok) return null;
    const json = await res.json();
    return (json?.data as Karar) ?? null;
  } catch {
    return null;
  }
}

function kararBaslik(k: Karar): string {
  const kaynak = KAYNAK_ETIKET[k.source ?? ""] ?? k.source ?? "";
  const daire = k.court_chamber ? ` ${k.court_chamber}` : "";
  const esas = k.case_no ? ` ${k.case_no} E.` : "";
  const karar = k.decision_no ? ` ${k.decision_no} K.` : "";
  return `${kaynak}${daire}${esas}${karar}`.trim() || k.id;
}

function tarihFormat(t?: string): string {
  if (!t) return "";
  try {
    return new Date(t).toLocaleDateString("tr-TR", {
      year: "numeric", month: "long", day: "numeric",
    });
  } catch {
    return t;
  }
}

export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  const karar = await getKarar(decodeURIComponent(params.id));
  if (!karar) return { robots: { index: false } };
  const baslik = kararBaslik(karar);
  const ozet = (karar.cleaned_text ?? "").slice(0, 155).replace(/\s+/g, " ");
  return {
    title: `${baslik} — Emsal Karar`.slice(0, 65),
    description:
      ozet || "Anonimleştirilmiş emsal karar metni ve ilgili içtihatlar.",
    alternates: { canonical: `/karar/${encodeURIComponent(karar.id)}` },
    openGraph: {
      title: baslik,
      type: "article",
      url: `${SITE_URL}/karar/${encodeURIComponent(karar.id)}`,
    },
  };
}

export default async function KararPage({
  params,
}: {
  params: { id: string };
}) {
  const id = decodeURIComponent(params.id);
  const karar = await getKarar(id);
  if (!karar) notFound();

  // KVKK: anonimleştirme kontrolünden geçmemiş karar yayımlanmaz.
  const anon = String(karar.anonymization_check ?? "").toLowerCase();
  if (anon === "failed" || anon === "false" || anon === "0") notFound();

  const baslik = kararBaslik(karar);
  const metin = karar.cleaned_text ?? "";
  const tarih = tarihFormat(karar.decision_date);
  const path = `/karar/${encodeURIComponent(karar.id)}`;

  const jsonLd = [
    buildBreadcrumbJsonLd([
      { name: "Ana Sayfa", path: "/" },
      { name: "Emsal Kararlar", path: "/emsal-arama" },
      { name: baslik, path },
    ]),
    buildArticleJsonLd({
      title: baslik,
      description: metin.slice(0, 160),
      path,
      datePublished: karar.decision_date ?? new Date().toISOString(),
    }),
  ];

  return (
    <>
      <JsonLd id="karar-ld" data={jsonLd} />
      <div className="container max-w-4xl py-10">
        <nav className="text-sm text-muted-foreground mb-6">
          <Link href="/" className="hover:text-foreground">Ana Sayfa</Link>
          {" / "}
          <Link href="/emsal-arama" className="hover:text-foreground">Emsal Arama</Link>
          {" / "}
          <span>{baslik}</span>
        </nav>

        <h1 className="text-2xl md:text-3xl font-bold mb-2">{baslik}</h1>
        <div className="text-sm text-muted-foreground mb-6">
          {tarih && <span>Karar tarihi: {tarih}</span>}
          {karar.topic_tags && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {karar.topic_tags.split(",").filter(Boolean).slice(0, 8).map((t) => (
                <span key={t} className="text-xs rounded-full bg-secondary px-2 py-0.5">
                  {t.trim()}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-wrap gap-2 mb-8">
          <Button asChild size="sm">
            <Link href={`/dilekce?durum=${encodeURIComponent(metin.slice(0, 300))}`}>
              <FileText className="h-3.5 w-3.5 mr-1.5" /> Bu kararla dilekçe oluştur
            </Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href={`/karar-ozet?id=${encodeURIComponent(karar.id)}`}>
              <Scale className="h-3.5 w-3.5 mr-1.5" /> AI özetini çıkar
            </Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/emsal-arama">
              <Search className="h-3.5 w-3.5 mr-1.5" /> Benzer karar ara
            </Link>
          </Button>
        </div>

        <Card>
          <CardContent className="p-6">
            <div className="prose prose-sm max-w-none whitespace-pre-wrap leading-relaxed text-foreground/90">
              {metin}
            </div>
          </CardContent>
        </Card>

        {karar.source_url && (
          <p className="mt-4 text-xs text-muted-foreground">
            Kaynak:{" "}
            <a href={karar.source_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              {karar.source_url}
            </a>
          </p>
        )}

        <div className="mt-8 rounded-lg border bg-muted/30 p-4 text-xs text-muted-foreground">
          Bu sayfadaki karar metni kamuya açık kaynaklardan derlenmiş ve kişisel
          veriler otomatik olarak anonimleştirilmiştir. Metin bilgilendirme
          amaçlıdır; hukuki tavsiye değildir. Hatalı anonimleştirme fark ederseniz{" "}
          <a href="mailto:kvkk@hukukemsal.tr" className="text-primary hover:underline">
            kvkk@hukukemsal.tr
          </a>{" "}
          adresine bildirin.
        </div>
      </div>
    </>
  );
}
