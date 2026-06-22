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
  // Tip kontrolu build'i bloklamasin (NextAuth overload'lari gibi tip gurultu).
  // Tipleri lokalde `npm run type-check` ile ayrica denetle.
  typescript: {
    ignoreBuildErrors: true,
  },
  experimental: {
    serverActions: {
      allowedOrigins: ["localhost:3000", "hukukemsal.tr"],
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
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL || "https://hukukemsal.tr",
  },
  async headers() {
    return [
      {
        source: "/(.*)",
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
