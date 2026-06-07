import Script from "next/script";

interface JsonLdProps {
  id?: string;
  data: Record<string, unknown> | Array<Record<string, unknown>>;
}

/**
 * Generic JSON-LD bileşeni. Bir veya birden fazla schema basabilir.
 *  <JsonLd id="page-bc" data={breadcrumbJsonLd} />
 *  <JsonLd id="page-faq" data={[bc, faq, article]} />
 */
export function JsonLd({ id, data }: JsonLdProps) {
  const payload = Array.isArray(data) ? data : [data];
  return (
    <>
      {payload.map((d, i) => (
        <Script
          key={`${id ?? "ld"}-${i}`}
          id={`${id ?? "ld"}-${i}`}
          type="application/ld+json"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(d) }}
        />
      ))}
    </>
  );
}
