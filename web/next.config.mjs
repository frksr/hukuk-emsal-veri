/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  compress: true,
  poweredByHeader: false,
  swcMinify: true,
  // ESLint config'i @typescript-eslint eklentisine atif yapiyor ama eklenti kurulu
  // degil; production image build'inde lint'i atla (lint dev/CI'da calistirilsin).
  eslint: {
    ignoreDuringBuilds: true,
  },
  // TİP KONTROLÜ ARTIK BUILD'İ BLOKLAR.
  // Eskiden `ignoreBuildErrors: true` idi ve 41 gerçek tip hatası (lib/api.ts
  // sözleşmeleriyle bileşenler arasında tam uyuşmazlık dahil) prod build'inde
  // sessizce geçiyordu — TypeScript fiilen devre dışıydı. Hatalar giderildi;
  // bayrak kapatıldı ki tip güvenliği gerçek bir garanti olsun.
  // ACİL DURUMDA (üretim düzeltmesi tip hatasıyla bloklanırsa) geçici olarak
  // `ignoreBuildErrors: true` yapılabilir — ama aynı gün geri alınmalıdır.
  typescript: {
    ignoreBuildErrors: false,
  },
  experimental: {
    serverActions: {
      allowedOrigins: ["localhost:3000", "hukukcuyapayzekasi.com", "www.hukukcuyapayzekasi.com"],
    },
    optimizePackageImports: ["lucide-react", "@tanstack/react-query"],
  },
  images: {
    domains: [],
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 60 * 60 * 24 * 7,
  },
  i18n: undefined, // App Router'da i18n manuel yapılıyor; lang="tr" sabit
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com",
    NEXT_PUBLIC_GA_MEASUREMENT_ID: process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "",
  },
  async rewrites() {
    // Dış URL /app/* ; iç route klasörü app/panel/*. Auth-gate /app yolunu bekler.
    return [
      { source: "/app", destination: "/panel" },
      { source: "/app/:path*", destination: "/panel/:path*" },
    ];
  },
  async headers() {
    return [
      {
        // /embed/* — faiz hesaplayıcı widget'ı BİLEREK üçüncü taraf sitelere
        // gömülebilir olmalı (backlink/marka stratejisi). Global
        // X-Frame-Options: SAMEORIGIN bu sayfayı da kapsadığı için widget
        // fiilen çalışmıyordu. Bu kural önce geldiğinden /embed/* için
        // X-Frame-Options HİÇ gönderilmez; çerçeveleme izni CSP
        // frame-ancestors ile middleware.ts'te yönetilir.
        source: "/embed/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ],
      },
      {
        source: "/((?!embed).*)",
        headers: [
          { key: "X-DNS-Prefetch-Control", value: "on" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
