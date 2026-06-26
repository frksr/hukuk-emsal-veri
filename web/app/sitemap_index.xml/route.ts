import { NextResponse } from "next/server";

/**
 * Sitemap INDEX — tüm alt sitemap'leri tek noktadan bildirir.
 *
 * Next.js App Router'da iki ayrı sitemap üretimi var:
 *   1. app/sitemap.ts          -> /sitemap.xml        (statik public route'lar)
 *   2. app/karar/sitemap.ts    -> /karar/sitemap/{0..N-1}.xml  (10K karar URL'i)
 *
 * Bunları birbirine bağlayan bir index YOKTU; sonuç olarak karar URL'leri
 * Google tarafından sitemap üzerinden keşfedilemiyordu (SEO_ANALIZ B1).
 * Bu route, GSC'ye gönderilecek TEK index'tir: /sitemap_index.xml
 *
 * KARAR_SITEMAP_SAYISI, app/karar/sitemap.ts içindeki SAYFA_SAYISI ile
 * SENKRON tutulmalıdır.
 */
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";

// app/karar/sitemap.ts -> SAYFA_SAYISI ile aynı olmalı.
const KARAR_SITEMAP_SAYISI = 10;

export const dynamic = "force-static";
export const revalidate = 86400;

export function GET() {
  const now = new Date().toISOString();

  const sitemaps: string[] = [
    `${SITE_URL}/sitemap.xml`,
    ...Array.from(
      { length: KARAR_SITEMAP_SAYISI },
      (_, i) => `${SITE_URL}/karar/sitemap/${i}.xml`
    ),
  ];

  const body =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    sitemaps
      .map(
        (loc) =>
          `  <sitemap>\n    <loc>${loc}</loc>\n    <lastmod>${now}</lastmod>\n  </sitemap>`
      )
      .join("\n") +
    `\n</sitemapindex>`;

  return new NextResponse(body, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=0, s-maxage=86400",
    },
  });
}
