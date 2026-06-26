import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FileText, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { JsonLd } from "@/components/seo/json-ld";
import {
  buildArticleJsonLd,
  buildBreadcrumbJsonLd,
  generateOgImageUrl,
} from "@/lib/seo";
import { AiOzetButton } from "./ai-ozet-button";

const API_BASE =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";

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
  topic_tags?: string | string[];
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

async function getBenzerKararlar(id: string): Promise<Karar[]> {
  try {
    const res = await fetch(
      `${API_BASE}/api/karar/benzer/${encodeURIComponent(id)}?limit=6`,
      { next: { revalidate: 86400 } }
    );
    if (!res.ok) return [];
    const json = await res.json();
    return (json?.data as Karar[]) ?? [];
  } catch {
    return [];
  }
}

function kararBaslik(k: Karar): string {
  const kaynak = KAYNAK_ETIKET[k.source ?? ""] ?? k.source ?? "";
  const daire = k.court_chamber ? ` ${k.court_chamber}` : "";
  const esas = k.case_no ? ` ${k.case_no} E.` : "";
  const karar = k.decision_no ? ` ${k.decision_no} K.` : "";
  return `${kaynak}${daire}${esas}${karar}`.trim() || k.id;
}

// topic_tags string ("a, b") veya string[] olabilir — normalize et.
function topicEtiketler(k: Karar): string[] {
  const raw = k.topic_tags;
  if (!raw) return [];
  const arr = Array.isArray(raw) ? raw : String(raw).split(/[,;|]/);
  return arr.map((t) => t.trim()).filter(Boolean);
}

// Ham metinden cümle sınırında özet lede çıkarır (LLM'siz, özgün çerçeveleme
// için). Tam metni birebir basmak duplicate/thin içerik riski taşıdığından
// (SEO_ANALIZ B3) sayfa bu özetle başlar; tam metin katlanır bölümde kalır.
function ozetCikar(metin: string, maxLen = 360): string {
  const temiz = (metin ?? "").replace(/\s+/g, " ").trim();
  if (temiz.length <= maxLen) return temiz;
  const kesit = temiz.slice(0, maxLen);
  const sonNokta = kesit.lastIndexOf(". ");
  return (sonNokta > 120 ? kesit.slice(0, sonNokta + 1) : kesit).trim() + " …";
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
  const etiketler = topicEtiketler(karar);

  // Description: ham usul metni (genelde düşük CTR mahkeme başlığı) yerine
  // konu etiketleri + bağlam. Yoksa kısaltılmış metne düş (SEO_ANALIZ B10).
  const konuKismi = etiketler.length
    ? `Konular: ${etiketler.slice(0, 4).join(", ")}. `
    : "";
  const hamOzet = (karar.cleaned_text ?? "").replace(/\s+/g, " ").trim();
  const description = (
    `${baslik}. ${konuKismi}Anonimleştirilmiş emsal karar özeti, ilgili içtihatlar ve dilekçe oluşturma.` +
    (hamOzet ? ` ${hamOzet}` : "")
  )
    .slice(0, 160)
    .trim();

  const ogImage = generateOgImageUrl(baslik, etiketler.slice(0, 3).join(" · "));

  return {
    title: `${baslik} — Emsal Karar`.slice(0, 65),
    description,
    keywords: [
      "emsal karar",
      baslik,
      ...etiketler.slice(0, 6),
    ].filter(Boolean),
    alternates: { canonical: `/karar/${encodeURIComponent(karar.id)}` },
    openGraph: {
      title: baslik,
      description,
      type: "article",
      url: `${SITE_URL}/karar/${encodeURIComponent(karar.id)}`,
      images: [{ url: ogImage, width: 1200, height: 630, alt: baslik }],
    },
    twitter: {
      card: "summary_large_image",
      title: baslik,
      description,
      images: [ogImage],
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
  const etiketler = topicEtiketler(karar);
  const lede = ozetCikar(metin);
  const kaynakAdi = KAYNAK_ETIKET[karar.source ?? ""] ?? karar.source ?? "";
  const benzer = await getBenzerKararlar(karar.id);

  const jsonLd = [
    buildBreadcrumbJsonLd([
      { name: "Ana Sayfa", path: "/" },
      { name: "Emsal Kararlar", path: "/emsal-arama" },
      { name: baslik, path },
    ]),
    buildArticleJsonLd({
      title: baslik,
      description: lede.slice(0, 160) || baslik,
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
              {(Array.isArray(karar.topic_tags)
                ? karar.topic_tags
                : karar.topic_tags.split(",")
              ).filter(Boolean).slice(0, 8).map((t) => (
                <span key={t} className="text-xs rounded-full bg-secondary px-2 py-0.5">
                  {t.trim()}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Özgün, server-render özet — sayfanın indekslenen ana içeriği (B3).
            Tam metin aşağıda katlanır bölümde; AI analizi Pro upsell olarak ayrı. */}
        <section aria-labelledby="karar-ozet" className="mb-8">
          <h2 id="karar-ozet" className="text-lg font-semibold mb-2">
            Karar Özeti
          </h2>
          <p className="text-foreground/90 leading-relaxed">
            {kaynakAdi ? `${kaynakAdi} tarafından` : "Bu emsal kararda"}
            {tarih ? ` ${tarih} tarihinde` : ""} verilen{" "}
            <strong>{baslik}</strong> sayılı emsal karar
            {etiketler.length
              ? `, ${etiketler.slice(0, 4).join(", ")} konularını ilgilendirmektedir.`
              : " incelenmektedir."}{" "}
            {lede}
          </p>
          <p className="mt-3 text-sm text-muted-foreground">
            Kararın tam metni aşağıda yer almaktadır. Yapay Zeka destekli ayrıntılı
            analiz ve gerekçeli özet için “Yapay Zeka özetini çıkar” aracını
            kullanabilirsiniz.
          </p>
        </section>

        <div className="flex flex-wrap gap-2 mb-8">
          <Button asChild size="sm">
            <Link href={`/dilekce?durum=${encodeURIComponent(metin.slice(0, 300))}`}>
              <FileText className="h-3.5 w-3.5 mr-1.5" /> Bu kararla dilekçe oluştur
            </Link>
          </Button>
          <AiOzetButton decisionId={karar.id} />
          <Button asChild size="sm" variant="outline">
            <Link href="/emsal-arama">
              <Search className="h-3.5 w-3.5 mr-1.5" /> Benzer karar ara
            </Link>
          </Button>
        </div>

        <Card>
          <CardContent className="p-6">
            <details>
              <summary className="cursor-pointer font-medium text-foreground mb-2 select-none">
                Kararın tam metnini göster
              </summary>
              <div className="prose prose-sm max-w-none whitespace-pre-wrap leading-relaxed text-foreground/90 mt-4">
                {metin}
              </div>
            </details>
          </CardContent>
        </Card>

        {benzer.length > 0 && (
          <section aria-labelledby="ilgili-kararlar" className="mt-10">
            <h2 id="ilgili-kararlar" className="text-lg font-semibold mb-3">
              İlgili Kararlar
            </h2>
            <ul className="grid gap-2 sm:grid-cols-2">
              {benzer.map((b) => {
                const bBaslik = kararBaslik(b);
                const bTarih = tarihFormat(b.decision_date);
                return (
                  <li key={b.id}>
                    <Link
                      href={`/karar/${encodeURIComponent(b.id)}`}
                      className="block rounded-lg border p-3 hover:border-primary/40 transition-colors"
                    >
                      <span className="block text-sm font-medium text-foreground">
                        {bBaslik}
                      </span>
                      {bTarih && (
                        <span className="block text-xs text-muted-foreground mt-0.5">
                          {bTarih}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

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
          <a href="mailto:kvkk@hukukcuyapayzekasi.com" className="text-primary hover:underline">
            kvkk@hukukcuyapayzekasi.com
          </a>{" "}
          adresine bildirin.
        </div>
      </div>
    </>
  );
}
