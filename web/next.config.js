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
};

module.exports = nextConfig;
