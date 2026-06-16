import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { DenetimForm } from "./form";

export const metadata: Metadata = buildMetadata({
  title: "Hukuki Belge Denetleyici | Dilekçe & Sözleşme Yapay Zeka Kontrol",
  description:
    "Yazdığınız dilekçe, ihtarname veya sözleşmenin hukuki risklerini Yapay Zeka ile kontrol edin. Eksik madde, yanlış kanun referansı, emsal aykırılık tespiti.",
  path: "/belge-denetim",
  keywords: [
    "dilekçe denetimi", "dilekçe kontrol", "hukuki belge kontrol",
    "ai dilekçe inceleme", "sözleşme risk denetimi", "belge denetleyici",
    "dava dilekçesi kontrol", "cevap dilekçesi inceleme",
  ],
});

const FAQ = [
  {
    q: "Belge Denetleyici neyi kontrol eder?",
    a: "Yasal dayanak (kanun maddesi referansları), yapı (zorunlu bölümler eksik mi), tutarlılık (esas no/tarih), emsal uyumluluk (Yargıtay içtihatlarına aykırı argüman), üslup ve risk seviyesi.",
  },
  {
    q: "Hangi belge türlerini denetler?",
    a: "Dilekçe (genel, dava, cevap), ihtarname, sözleşme ve genel hukuki belge. PDF/DOCX olarak yükleyebilir veya metin yapıştırabilirsiniz.",
  },
  {
    q: "Çıktı bir avukatın yerine geçer mi?",
    a: "Hayır. Bu sistem Yapay Zeka destekli ön kontrol sağlar. Mahkemeye sunmadan önce mutlaka bir avukatın incelemesi şarttır.",
  },
];

export default function BelgeDenetimPage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([
        { name: "Ana Sayfa", url: "/" },
        { name: "Belge Denetleyici", url: "/belge-denetim" },
      ])} />
      <JsonLd data={faqJsonLd(FAQ)} />
      <div className="container py-10 max-w-6xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Belge Denetleyici</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Hukuki Belge Denetleyici</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          Yazdığınız veya yüklediğiniz dilekçeyi, ihtarnameyi ya da sözleşmeyi Yapay Zeka ile denetleyin: yasal
          dayanak doğru mu, eksik bölüm var mı, Yargıtay emsallerine aykırı argüman var mı, karşı tarafın
          yakalayabileceği zayıflık ne?
        </p>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 mb-6 text-sm">
          ⚠️ <strong>Yasal uyarı:</strong> Yapay Zeka denetimi, profesyonel hukuk inceleme servisinin yerine geçmez.
          Mahkemeye sunmadan önce avukat incelemesi şarttır.
        </div>

        <DenetimForm />

        <section className="mt-12">
          <h2 className="text-2xl font-bold mb-4">Sıkça Sorulan Sorular</h2>
          <div className="space-y-4">
            {FAQ.map((f, i) => (
              <details key={i} className="rounded-lg border bg-card p-5">
                <summary className="cursor-pointer font-semibold">{f.q}</summary>
                <p className="mt-3 text-muted-foreground">{f.a}</p>
              </details>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
