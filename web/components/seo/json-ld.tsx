interface JsonLdProps {
  id?: string;
  data: Record<string, unknown> | Array<Record<string, unknown>>;
}

/**
 * Generic JSON-LD bileşeni. Bir veya birden fazla schema basabilir.
 *  <JsonLd id="page-bc" data={breadcrumbJsonLd} />
 *  <JsonLd id="page-faq" data={[bc, faq, article]} />
 *
 * ÖNEMLİ: next/script DEĞİL düz <script> kullanılır — JSON-LD'nin ilk HTML
 * yanıtında (SSR) yer alması gerekir; afterInteractive ile inject edilirse
 * Google dışındaki crawler'lar (ve bazen Google'ın ilk dalga taraması) göremez.
 */
export function JsonLd({ id, data }: JsonLdProps) {
  const payload = Array.isArray(data) ? data : [data];
  return (
    <>
      {payload.map((d, i) => (
        <script
          key={`${id ?? "ld"}-${i}`}
          type="application/ld+json"
          // JSON-LD XSS guard: </script> kaçışı
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(d).replace(/</g, "\\u003c"),
          }}
        />
      ))}
    </>
  );
}
