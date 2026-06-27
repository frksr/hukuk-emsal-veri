/** @type {import('next').NextConfig} */
// Bu dosya geriye uyumluluk için. Asıl konfigürasyon next.config.mjs içinde.
// Next.js önce .mjs'i tarar; CommonJS isteyenler bu dosyayı kullanabilir.
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  compress: true,
  poweredByHeader: false,
  swcMinify: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
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
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com",
  },
  async rewrites() {
    // Dış URL /app/* ; iç route klasörü app/panel/*. Auth-gate /app yolunu bekler.
    return [
      { source: "/app", destination: "/panel" },
      { source: "/app/:path*", destination: "/panel/:path*" },
    ];
  },
};

module.exports = nextConfig;
