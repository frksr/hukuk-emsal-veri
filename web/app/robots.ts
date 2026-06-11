import type { MetadataRoute } from "next";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukemsal.tr";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        // /api/og dinamik Open Graph görseli — engellenmemeli
        allow: ["/", "/api/og"],
        disallow: [
          "/api/",
          "/admin/",
          "/_next/",
          "/static/",
          "/app/",
          "/giris",
          "/kayit",
          "/sifre-sifirla",
          "/hosgeldin",
        ],
      },
      {
        userAgent: "GPTBot",
        disallow: "/",
      },
      {
        userAgent: "CCBot",
        disallow: "/",
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
