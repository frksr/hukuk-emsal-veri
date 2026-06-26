import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { ZamanasimiForm } from "../zamanasimi-form";

export const metadata: Metadata = buildMetadata({
  title: "Kira Alacağı Zamanaşımı | 5 Yıllık Süre Hesaplama",
  description:
    "Kira alacağında zamanaşımı süresini hesaplayın. TBK 147 uyarınca kira bedeli alacakları 5 yıllık zamanaşımına tabidir; kalan gün ve bitiş tarihini öğrenin.",
  path: "/zamanasimi/kira",
  keywords: [
    "kira zamanaşımı",
    "kira alacağı zamanaşımı",
    "kira zamanaşımı 5 yıl",
    "tbk 147 zamanaşımı",
    "ödenmeyen kira zamanaşımı",
    "kira borcu zamanaşımı",
  ],
});

const FAQ = [
  {
    q: "Kira alacağında zamanaşımı kaç yıldır?",
    a: "TBK 147/1 uyarınca kira bedeli alacakları 5 yıllık zamanaşımına tabidir. Her bir kira alacağı için süre, o alacağın muaccel olduğu (ödenmesi gerektiği) tarihten itibaren ayrı ayrı işler.",
  },
  {
    q: "Zamanaşımı her kira ayı için ayrı mı işler?",
    a: "Evet. Dönemsel edim niteliğindeki kira alacaklarında her aylık kira, muaccel olduğu tarihten itibaren kendi 5 yıllık süresine tabidir. Bu nedenle eski aylar zamanaşımına uğrarken yeni aylar takip edilebilir durumda olabilir.",
  },
  {
    q: "Kira zamanaşımı nasıl kesilir?",
    a: "TBK 154 uyarınca dava açılması, icra takibi, kiracının borcu ikrarı veya ihtarname gibi işlemlerle zamanaşımı kesilir. Kesilmeden sonra süre yeniden işlemeye başlar.",
  },
  {
    q: "Zamanaşımına uğramış kira alacağı tahsil edilebilir mi?",
    a: "Zamanaşımı, borcu sona erdirmez ancak borçluya bir def'i (savunma) hakkı verir. Borçlu zamanaşımı def'ini ileri sürerse alacak mahkemece reddedilebilir; sürmezse tahsil mümkün olabilir.",
  },
];

export default function KiraZamanasimiPage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbJsonLd([
            { name: "Ana Sayfa", url: "/" },
            { name: "Zamanaşımı", url: "/zamanasimi" },
            { name: "Kira Alacağı Zamanaşımı", url: "/zamanasimi/kira" },
          ]),
          faqJsonLd(FAQ.map((f) => ({ question: f.q, answer: f.a }))),
        ]}
      />
      <div className="container py-10 max-w-6xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <Link href="/" className="hover:text-foreground">
            Ana Sayfa
          </Link>{" "}
          /{" "}
          <Link href="/zamanasimi" className="hover:text-foreground">
            Zamanaşımı
          </Link>{" "}
          / <span>Kira Alacağı Zamanaşımı</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-3">
          Kira Alacağı Zamanaşımı Hesaplama
        </h1>
        <p className="text-muted-foreground mb-6 max-w-3xl">
          Kira bedeli alacakları TBK 147 uyarınca 5 yıllık zamanaşımına tabidir
          ve her ay için ayrı işler. Alacağın muaccel olduğu tarihi girin; kalan
          gün ve zamanaşımı bitiş tarihini hesaplayın.
        </p>

        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 mb-6 text-sm">
          ⚠️ <strong>Yasal uyarı:</strong> Hesaplama bilgilendirme amaçlıdır;
          kesilme/durma halleri ve somut olay için avukata danışın.
        </div>

        <ZamanasimiForm />

        <section aria-labelledby="kira-zaman-sss" className="mt-12 max-w-3xl">
          <h2 id="kira-zaman-sss" className="text-2xl font-bold mb-6">
            Sıkça Sorulan Sorular
          </h2>
          <div className="space-y-6">
            {FAQ.map((item) => (
              <div key={item.q}>
                <h3 className="font-semibold mb-1">{item.q}</h3>
                <p className="text-muted-foreground text-sm">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-12 max-w-3xl">
          <h2 className="text-xl font-bold mb-3">İlgili araçlar</h2>
          <ul className="list-disc pl-5 space-y-1 text-sm">
            <li>
              <Link
                href="/ihtarname/kira-tahliye"
                className="text-primary hover:underline"
              >
                Kira tahliye ihtarnamesi örneği
              </Link>
            </li>
            <li>
              <Link href="/faiz-hesaplayici" className="text-primary hover:underline">
                Kira alacağında faiz hesaplama
              </Link>
            </li>
            <li>
              <Link href="/zamanasimi/cek" className="text-primary hover:underline">
                Çek zamanaşımı hesaplama
              </Link>
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}
