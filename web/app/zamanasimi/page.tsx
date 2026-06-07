import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { ZamanasimiForm } from "./zamanasimi-form";

export const metadata: Metadata = buildMetadata({
  title: "Zamanaşımı Hesaplayıcı | Alacak, Kira, Çek, İcra Süreleri 2026",
  description:
    "Alacak, kira, çek, kambiyo, vergi, icra zamanaşımı sürelerini hesaplayın. TBK 146, TTK 778, AATUHK 102 referanslı kalan gün ve bitiş tarihi.",
  path: "/zamanasimi",
  keywords: [
    "zamanaşımı hesaplama", "alacak zamanaşımı", "kira zamanaşımı",
    "çek zamanaşımı 3 yıl", "kambiyo senedi zamanaşımı", "vergi zamanaşımı",
    "haksız fiil zamanaşımı", "icra zamanaşımı",
  ],
});

const FAQ = [
  { q: "Genel alacak zamanaşımı kaç yıldır?", a: "TBK 146 uyarınca genel alacak zamanaşımı 10 yıldır. Kira, ücret gibi belirli alacaklar 5 yıl, kambiyo senetleri 3 yıldır." },
  { q: "Zamanaşımını ihtarname ile kesebilir miyim?", a: "Evet, TBK 154 uyarınca ihtarname dahil hukuki takip işlemleri zamanaşımını keser. Kesilme sonrası süre baştan işlemeye başlar." },
  { q: "Vergi alacağında zamanaşımı süresi nedir?", a: "VUK 114 ve AATUHK 102 uyarınca vergi alacağı tahsil zamanaşımı 5 yıldır. Tarh zamanaşımı ise 5 yıl olup vergiyi doğuran olay yılını takip eden yılbaşından itibaren işler." },
];

export default function ZamanasimiPage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "Zamanaşımı", url: "/zamanasimi" }])} />
      <JsonLd data={faqJsonLd(FAQ)} />
      <div className="container py-10 max-w-5xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Zamanaşımı Hesaplayıcı</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Zamanaşımı Hesaplayıcı</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          Dava türünü ve olay tarihini girin, sistem TBK, TTK, AATUHK, İİK referanslı zamanaşımı süresini
          ve kalan günleri göstersin. Kesilme tarihleri ekleyerek güncel hesap yapabilirsiniz.
        </p>
        <ZamanasimiForm />

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
