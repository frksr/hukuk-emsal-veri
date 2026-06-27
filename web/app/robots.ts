import type { MetadataRoute } from "next";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";

// Public olmayan / indekslenmemesi gereken yollar.
const DISALLOW = [
  "/api/",
  "/admin/",
  "/panel/",
  "/_next/",
  "/static/",
  "/giris",
  "/kayit",
  "/sifre-sifirla",
  "/hosgeldin",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        // /api/og dinamik Open Graph görseli — engellenmemeli
        allow: ["/", "/api/og"],
        disallow: DISALLOW,
      },
      // AI crawler'ları (ChatGPT/OpenAI, Common Crawl, Perplexity): public araç
      // ve karar sayfalarına izin; panel/auth/api yine kapalı. AI aramada
      // görünürlük artan bir trafik kaynağı olduğundan açıldı (SEO_ANALIZ B11).
      {
        userAgent: "GPTBot",
        allow: ["/", "/api/og"],
        disallow: DISALLOW,
      },
      {
        userAgent: "OAI-SearchBot",
        allow: ["/", "/api/og"],
        disallow: DISALLOW,
      },
      {
        userAgent: "CCBot",
        allow: ["/", "/api/og"],
        disallow: DISALLOW,
      },
      {
        userAgent: "PerplexityBot",
        allow: ["/", "/api/og"],
        disallow: DISALLOW,
      },
    ],
    // TEK index: hem statik /sitemap.xml hem de /karar/sitemap/0..9.xml burada.
    sitemap: `${SITE_URL}/sitemap_index.xml`,
    host: SITE_URL,
  };
}
