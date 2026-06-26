import type { Metadata } from "next";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";
// Tek marka/entity adı (single source of truth) — domain ile uyumlu.
// Tüm OG/Twitter/JSON-LD sinyalleri buradan beslenir (SEO_ANALIZ B5).
const SITE_NAME = "Hukukçu Yapay Zekası";

export interface BuildMetadataInput {
  title: string;
  description: string;
  path?: string;
  keywords?: string[];
  ogImage?: string;
  noIndex?: boolean;
  type?: "website" | "article";
  publishedTime?: string;
  modifiedTime?: string;
  authors?: string[];
}

/**
 * Sayfa bazlı Metadata üretir. Title/description uzunluğunu doğrular.
 * Title: 40-60 karakter ideal. Description: 150-160 karakter ideal.
 */
export function buildMetadata(input: BuildMetadataInput): Metadata {
  const {
    title,
    description,
    path = "/",
    keywords,
    ogImage,
    noIndex,
    type = "website",
    publishedTime,
    modifiedTime,
    authors,
  } = input;

  // Dev'de uyarı (prod'da no-op)
  if (process.env.NODE_ENV !== "production") {
    if (title.length < 30 || title.length > 65) {
      console.warn(
        `[seo] Title uzunluğu önerilenin dışında (${title.length} char): "${title}"`
      );
    }
    if (description.length < 120 || description.length > 170) {
      console.warn(
        `[seo] Description uzunluğu önerilenin dışında (${description.length} char)`
      );
    }
  }

  const url = `${SITE_URL}${path}`;
  const image = ogImage ?? generateOgImageUrl(title);

  return {
    title,
    description,
    keywords,
    alternates: {
      canonical: path,
      languages: { "tr-TR": path },
    },
    openGraph: {
      title,
      description,
      url,
      siteName: SITE_NAME,
      locale: "tr_TR",
      type,
      images: [{ url: image, width: 1200, height: 630, alt: title }],
      ...(publishedTime ? { publishedTime } : {}),
      ...(modifiedTime ? { modifiedTime } : {}),
      ...(authors ? { authors } : {}),
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
    },
    robots: noIndex
      ? { index: false, follow: false }
      : { index: true, follow: true },
  };
}

/**
 * Dinamik OG image URL'i üretir.
 *  /api/og?title=...&subtitle=... gibi bir endpoint'in var olduğu varsayılır.
 *  Yoksa default static fallback kullanılır.
 */
export function generateOgImageUrl(
  title: string,
  subtitle?: string
): string {
  const params = new URLSearchParams({ title });
  if (subtitle) params.set("subtitle", subtitle);
  // İleride /api/og endpoint'i eklenecek; şimdilik query string güvenli URL.
  return `${SITE_URL}/api/og?${params.toString()}`;
}

/**
 * Breadcrumb JSON-LD üreticisi.
 */
export function buildBreadcrumbJsonLd(
  items: Array<{ name: string; path?: string; url?: string }>
) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: `${SITE_URL}${item.path ?? item.url ?? ""}`,
    })),
  };
}

// Geriye dönük uyumluluk alias'ları (sayfalar bu adlarla import ediyor)
export const breadcrumbJsonLd = buildBreadcrumbJsonLd;

/**
 * FAQ JSON-LD üreticisi.
 */
export function buildFaqJsonLd(
  faqs: Array<{ question: string; answer: string }>
) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((f) => ({
      "@type": "Question",
      name: f.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: f.answer,
      },
    })),
  };
}

// Geriye dönük uyumluluk alias'ı
export const faqJsonLd = buildFaqJsonLd;

/**
 * Article JSON-LD üreticisi.
 */
export function buildArticleJsonLd(input: {
  title: string;
  description: string;
  path: string;
  image?: string;
  datePublished: string;
  dateModified?: string;
  authorName?: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: input.title,
    description: input.description,
    image: input.image ?? generateOgImageUrl(input.title),
    datePublished: input.datePublished,
    dateModified: input.dateModified ?? input.datePublished,
    author: {
      "@type": input.authorName ? "Person" : "Organization",
      name: input.authorName ?? SITE_NAME,
    },
    publisher: {
      "@type": "Organization",
      name: SITE_NAME,
      logo: {
        "@type": "ImageObject",
        url: `${SITE_URL}/logo.png`,
      },
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `${SITE_URL}${input.path}`,
    },
    inLanguage: "tr-TR",
  };
}
