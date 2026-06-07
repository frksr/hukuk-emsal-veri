/** @type {import('next-sitemap').IConfig} */
module.exports = {
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL || "https://hukukemsal.tr",
  generateRobotsTxt: false, // App Router'da robots.ts kullanıyoruz
  generateIndexSitemap: true,
  sitemapSize: 5000,
  changefreq: "weekly",
  priority: 0.7,
  exclude: ["/admin/*", "/api/*", "/_next/*", "/server-sitemap.xml"],
  robotsTxtOptions: {
    policies: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/admin/"],
      },
    ],
  },
  transform: async (config, path) => {
    // Yüksek değerli sayfalar için öncelik ayarı
    const highPriority = ["/", "/emsal-arama"];
    const priority = highPriority.includes(path) ? 1.0 : config.priority;
    return {
      loc: path,
      changefreq: config.changefreq,
      priority,
      lastmod: new Date().toISOString(),
      alternateRefs: [
        {
          href: `${config.siteUrl}${path}`,
          hreflang: "tr-TR",
        },
      ],
    };
  },
};
