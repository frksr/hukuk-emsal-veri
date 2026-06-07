import type { MetadataRoute } from "next";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukemsal.tr";

// Public sayfaların kanonik listesi. Yeni sayfa eklendikçe buraya ekleyin.
const STATIC_ROUTES: Array<{
  path: string;
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
  priority: number;
}> = [
  { path: "/", changeFrequency: "daily", priority: 1.0 },
  { path: "/emsal-arama", changeFrequency: "daily", priority: 0.9 },
  { path: "/dilekce", changeFrequency: "weekly", priority: 0.8 },
  { path: "/ihtarname", changeFrequency: "weekly", priority: 0.8 },
  { path: "/faiz-hesaplama", changeFrequency: "monthly", priority: 0.7 },
  { path: "/zamanasimi", changeFrequency: "monthly", priority: 0.7 },
  { path: "/kvkk-uyum", changeFrequency: "monthly", priority: 0.6 },
  { path: "/sozlesme-analizi", changeFrequency: "weekly", priority: 0.7 },
  { path: "/karsi-argument", changeFrequency: "weekly", priority: 0.6 },
  { path: "/trendler", changeFrequency: "weekly", priority: 0.6 },
  { path: "/hakkimizda", changeFrequency: "yearly", priority: 0.4 },
  { path: "/iletisim", changeFrequency: "yearly", priority: 0.4 },
  { path: "/gizlilik", changeFrequency: "yearly", priority: 0.3 },
  { path: "/kullanim-kosullari", changeFrequency: "yearly", priority: 0.3 },
];

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return STATIC_ROUTES.map((r) => ({
    url: `${SITE_URL}${r.path}`,
    lastModified,
    changeFrequency: r.changeFrequency,
    priority: r.priority,
    alternates: {
      languages: {
        "tr-TR": `${SITE_URL}${r.path}`,
      },
    },
  }));
}
