import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { auth } from "@/auth";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { Providers } from "@/components/providers";
import { CookieConsent } from "@/components/cookie-consent";
import { ChromeGuard } from "@/components/layout/chrome-guard";
import { InactivityLogout } from "@/components/inactivity-logout";
import "./globals.css";

const inter = Inter({
  subsets: ["latin", "latin-ext"],
  display: "swap",
  variable: "--font-inter",
  preload: true,
});

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Türk Hukuk Asistanı | Emsal Karar Arama",
    template: "%s | Türk Hukuk Asistanı",
  },
  description:
    "İcra, tahsilat, ihtar konularında Yargıtay, Danıştay ve AİHM emsal kararları. Yapay Zeka destekli dilekçe, ihtarname, faiz hesaplama.",
  keywords: [
    "yargıtay kararları",
    "danıştay kararları",
    "emsal karar",
    "icra hukuku",
    "tahsilat",
    "ihtarname örnek",
    "dilekçe örnek",
    "faiz hesaplama",
    "zamanaşımı",
    "kvkk uyum",
  ],
  authors: [{ name: "Hukuk Emsal" }],
  creator: "Hukuk Emsal",
  publisher: "Hukuk Emsal",
  applicationName: "Türk Hukuk Asistanı",
  category: "law",
  openGraph: {
    type: "website",
    locale: "tr_TR",
    url: SITE_URL,
    siteName: "Hukuk Emsal",
    title: "Türk Hukuk Asistanı | Emsal Karar Arama",
    description:
      "Yargıtay, Danıştay ve AİHM emsal kararları + Yapay Zeka destekli hukuki araçlar.",
    images: [
      {
        url: "/og-default.png",
        width: 1200,
        height: 630,
        alt: "Türk Hukuk Asistanı",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Türk Hukuk Asistanı | Emsal Karar Arama",
    description:
      "Yargıtay, Danıştay ve AİHM emsal kararları + Yapay Zeka destekli hukuki araçlar.",
    images: ["/og-default.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  alternates: {
    canonical: "/",
    languages: {
      "tr-TR": "/",
    },
  },
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon-16x16.png",
    apple: "/apple-touch-icon.png",
  },
  manifest: "/site.webmanifest",
  verification: {
    // Google Search Console doğrulama token'ı env'den okunur.
    ...(process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION
      ? { google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION }
      : {}),
  },
  formatDetection: {
    email: false,
    telephone: false,
    address: false,
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#1e3a5f" },
    { media: "(prefers-color-scheme: dark)", color: "#0b172d" },
  ],
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  colorScheme: "light dark",
};

const legalServiceJsonLd = {
  "@context": "https://schema.org",
  "@type": "LegalService",
  name: "Hukuk Emsal",
  alternateName: "Türk Hukuk Asistanı",
  url: SITE_URL,
  logo: `${SITE_URL}/logo.png`,
  image: `${SITE_URL}/og-default.png`,
  description:
    "Yargıtay, Danıştay ve AİHM emsal kararları üzerinde arama ve Yapay Zeka destekli hukuki araçlar (dilekçe, ihtarname, faiz/zamanaşımı hesaplama).",
  inLanguage: "tr-TR",
  areaServed: {
    "@type": "Country",
    name: "Türkiye",
  },
  availableLanguage: ["tr-TR"],
  serviceType: [
    "Emsal karar arama",
    "Hukuki belge oluşturma",
    "Faiz hesaplama",
    "Zamanaşımı hesaplama",
    "KVKK uyum",
  ],
  potentialAction: {
    "@type": "SearchAction",
    target: {
      "@type": "EntryPoint",
      urlTemplate: `${SITE_URL}/emsal-arama?q={search_term_string}`,
    },
    "query-input": "required name=search_term_string",
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Giriş durumunu SUNUCUDA çöz → ilk render'da doğru header/oturum durumu
  // (client fetch'i beklemeden). "çıkış-yapmış → giriş-yapmış" titremesini önler.
  const session = await auth();
  const initialUser = session?.user
    ? {
        name: session.user.name ?? null,
        email: session.user.email ?? null,
        role: (session.user as { role?: string }).role ?? null,
      }
    : null;
  return (
    <html lang="tr" className={inter.variable} suppressHydrationWarning>
      <head>
        {/* Tema: render öncesi sınıfı uygula — FOUC önlenir.
            localStorage("tema") -> yoksa sistem tercihi (prefers-color-scheme). */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("tema");var koyu=t==="dark"||(!t&&window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches);if(koyu){document.documentElement.classList.add("dark");}else{document.documentElement.classList.remove("dark");}}catch(e){}})();`,
          }}
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        {/* JSON-LD ilk HTML'de olmalı — next/script afterInteractive kullanma */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(legalServiceJsonLd).replace(/</g, "\\u003c"),
          }}
        />
      </head>
      <body className="min-h-screen flex flex-col bg-background font-sans">
        <Providers initialUser={initialUser}>
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
          >
            Ana içeriğe geç
          </a>
          <ChromeGuard>
            <Header />
          </ChromeGuard>
          <main id="main-content" className="flex-1">
            {children}
          </main>
          <ChromeGuard>
            <Footer />
            <CookieConsent />
          </ChromeGuard>
          <InactivityLogout />
        </Providers>
      </body>
    </html>
  );
}
