import type { MetadataRoute } from "next";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukemsal.tr";

// Public sayfaların kanonik listesi — app/ klasöründeki GERÇEK route'larla
// birebir aynı olmalı. Yeni sayfa eklendikçe buraya ekleyin.
// Auth/private sayfalar (giris, kayit, sifre-sifirla, hosgeldin, app/*)
// bilinçli olarak DAHİL DEĞİL (noindex).
const STATIC_ROUTES: Array<{
  path: string;
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
  priority: number;
}> = [
  { path: "/", changeFrequency: "daily", priority: 1.0 },
  { path: "/emsal-arama", changeFrequency: "daily", priority: 0.9 },
  { path: "/fiyatlandirma", changeFrequency: "monthly", priority: 0.9 },
  { path: "/dilekce", changeFrequency: "weekly", priority: 0.8 },
  { path: "/ihtarname", changeFrequency: "weekly", priority: 0.8 },
  { path: "/karar-ozet", changeFrequency: "weekly", priority: 0.8 },
  { path: "/faiz-hesaplayici", changeFrequency: "monthly", priority: 0.7 },
  { path: "/zamanasimi", changeFrequency: "monthly", priority: 0.7 },
  { path: "/sozlesme-analizi", changeFrequency: "weekly", priority: 0.7 },
  { path: "/belge-denetim", changeFrequency: "weekly", priority: 0.6 },
  { path: "/karsi-argument", changeFrequency: "weekly", priority: 0.6 },
  { path: "/kvkk", changeFrequency: "monthly", priority: 0.6 },
  { path: "/trend", changeFrequency: "weekly", priority: 0.6 },
  { path: "/yasal-uyari", changeFrequency: "yearly", priority: 0.3 },
  { path: "/gizlilik", changeFrequency: "yearly", priority: 0.3 },
  { path: "/kullanim-sartlari", changeFrequency: "yearly", priority: 0.3 },
];

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return STATIC_ROUTES.map((r) => ({
    url: `${SITE_URL}${r.path}`,
    lastModified,
    changeFrequency: r.changeFrequency,
    priority: r.priority,
  }));
}
