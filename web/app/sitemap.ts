import type { MetadataRoute } from "next";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";

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
  // Long-tail alt sayfalar (Cluster A×C — SEO_ANALIZ B6)
  { path: "/ihtarname/kira-tahliye", changeFrequency: "monthly", priority: 0.75 },
  { path: "/ihtarname/alacak", changeFrequency: "monthly", priority: 0.75 },
  { path: "/zamanasimi/cek", changeFrequency: "monthly", priority: 0.75 },
  { path: "/karar-ozet", changeFrequency: "weekly", priority: 0.8 },
  { path: "/faiz-hesaplayici", changeFrequency: "monthly", priority: 0.7 },
  { path: "/zamanasimi", changeFrequency: "monthly", priority: 0.7 },
  { path: "/sozlesme-analizi", changeFrequency: "weekly", priority: 0.7 },
  { path: "/belge-denetim", changeFrequency: "weekly", priority: 0.6 },
  { path: "/karsi-argument", changeFrequency: "weekly", priority: 0.6 },
  { path: "/kvkk", changeFrequency: "monthly", priority: 0.6 },
  { path: "/trend", changeFrequency: "weekly", priority: 0.6 },
  // Blog / rehber hub (Cluster B — SEO_ANALIZ B7)
  { path: "/blog", changeFrequency: "weekly", priority: 0.7 },
  { path: "/blog/emsal-karar-nedir", changeFrequency: "monthly", priority: 0.6 },
  { path: "/blog/ihtarname-nasil-cekilir", changeFrequency: "monthly", priority: 0.6 },
  { path: "/yasal-uyari", changeFrequency: "yearly", priority: 0.3 },
  { path: "/gizlilik", changeFrequency: "yearly", priority: 0.3 },
  { path: "/kullanim-sartlari", changeFrequency: "yearly", priority: 0.3 },
];

// Statik içerik son güncellenme tarihi (SABİT). `new Date()` her build'de
// "değişti" sinyali verir ve lastmod güvenini düşürür (SEO_ANALIZ B9).
// İçerik değiştikçe elle güncelleyin. Sık değişen route'lar (/, /emsal-arama,
// /trend) için changeFrequency zaten taze tarama sinyali veriyor.
const CONTENT_LAST_UPDATED = new Date("2026-06-26T00:00:00.000Z");

export default function sitemap(): MetadataRoute.Sitemap {
  return STATIC_ROUTES.map((r) => ({
    url: `${SITE_URL}${r.path}`,
    lastModified: CONTENT_LAST_UPDATED,
    changeFrequency: r.changeFrequency,
    priority: r.priority,
  }));
}
