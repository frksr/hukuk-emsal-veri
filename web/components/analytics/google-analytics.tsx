import Script from "next/script";

/**
 * Google tag (gtag.js) — GA4. NEXT_PUBLIC_GA_MEASUREMENT_ID tanımlı değilse hiçbir
 * şey render etmez (lokal/dev'de yanlışlıkla veri göndermeyi önler).
 *
 * next/script + strategy="afterInteractive" kullanılıyor (Next.js'in resmi GA
 * entegrasyon önerisi): sayfa render'ını bloklamadan, hydration sonrası yüklenir.
 * Next bu script'i otomatik olarak doğru yere enjekte eder — App Router'da
 * elle <head> içine ham <script> eklemekten daha güvenilirdir.
 */
export function GoogleAnalytics() {
  const gaId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;
  if (!gaId) return null;

  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`}
        strategy="afterInteractive"
      />
      <Script id="google-analytics" strategy="afterInteractive">
        {`
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '${gaId}');
        `}
      </Script>
    </>
  );
}
