import type { Metadata } from "next";
import Link from "next/link";
import {
  buildMetadata,
  breadcrumbJsonLd,
  buildArticleJsonLd,
  faqJsonLd,
} from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { makaleBul } from "../makaleler";

const SLUG = "ihtarname-nasil-cekilir";
const makale = makaleBul(SLUG)!;

export const metadata: Metadata = buildMetadata({
  title: "İhtarname Nasıl Çekilir? Adım Adım Noter Rehberi",
  description:
    "İhtarname nasıl çekilir, noter ihtarnamesi süreci, masrafı ve dikkat edilecekler. Alacak ve kira tahliye ihtarnameleri için adım adım rehber.",
  path: `/blog/${SLUG}`,
  type: "article",
  publishedTime: makale.yayinTarihi,
  authors: [makale.yazar],
  keywords: [
    "ihtarname nasıl çekilir",
    "noter ihtarnamesi",
    "ihtarname masrafı",
    "alacak ihtarnamesi",
    "kira tahliye ihtarnamesi",
  ],
});

const FAQ = [
  {
    q: "İhtarname noterden mi çekilmeli?",
    a: "Hukuken her ihtar noterden olmak zorunda değildir; ancak noter ihtarnamesi, içeriği ve tebliğ tarihini resmî olarak belgelediği için ispat açısından en güçlü yöntemdir. Özellikle temerrüt ve tahliye süreçlerinde noter tercih edilir.",
  },
  {
    q: "İhtarname çekmek ne kadar sürede sonuç verir?",
    a: "İhtarname, muhatabına tebliğ edildiği tarihten itibaren hüküm doğurur. İçinde verilen süre (örn. 7 veya 30 gün) dolduğunda; ödeme yapılmazsa icra takibi veya dava aşamasına geçilebilir.",
  },
  {
    q: "İhtarnamede hangi bilgiler bulunmalı?",
    a: "Tarafların kimlik ve adres bilgileri, talebin dayanağı (sözleşme, fatura, kira), net tutar veya talep, tanınan süre ve sonuçları (yasal yollara başvurulacağı) açıkça yer almalıdır.",
  },
];

export default function IhtarnameNasilCekilirPage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbJsonLd([
            { name: "Ana Sayfa", url: "/" },
            { name: "Rehber", url: "/blog" },
            { name: "İhtarname Nasıl Çekilir?", url: `/blog/${SLUG}` },
          ]),
          buildArticleJsonLd({
            title: makale.baslik,
            description: makale.ozet,
            path: `/blog/${SLUG}`,
            datePublished: makale.yayinTarihi,
            authorName: makale.yazar,
          }),
          faqJsonLd(FAQ.map((f) => ({ question: f.q, answer: f.a }))),
        ]}
      />
      <article className="container py-10 max-w-3xl prose prose-sm md:prose-base max-w-none">
        <nav className="text-sm text-muted-foreground mb-4 not-prose">
          <Link href="/" className="hover:text-foreground">
            Ana Sayfa
          </Link>{" "}
          /{" "}
          <Link href="/blog" className="hover:text-foreground">
            Rehber
          </Link>{" "}
          / <span>İhtarname Nasıl Çekilir?</span>
        </nav>

        <h1>İhtarname Nasıl Çekilir? Adım Adım Noter İhtarnamesi Rehberi</h1>

        <p>
          <strong>İhtarname</strong>, bir kişiyi hukuki bir yükümlülüğünü yerine
          getirmesi için resmî olarak uyaran yazılı bildirimdir. En yaygın
          kullanımı; borçluyu temerrüde düşürmek (alacak ihtarnamesi), kira
          borcunu ihtar etmek ya da sözleşmeyi feshetmektir. İhtarname, ileride
          açılacak icra takibi veya davada güçlü bir delil oluşturur.
        </p>

        <h2>1. Talebinizi ve dayanağını belirleyin</h2>
        <p>
          İhtarnamenin konusunu netleştirin: alacak mı, kira mı, fesih mi?
          Dayandığınız sözleşme, fatura veya senedi ve talep tutarını hazırlayın.
          Talebin somut ve ölçülebilir olması, ihtarın gücünü artırır.
        </p>

        <h2>2. Süre ve sonuçları yazın</h2>
        <p>
          Muhataba ödeme/ifa için makul bir süre tanıyın (örneğin kira temerrüdünde
          TBK 315 uyarınca en az 30 gün) ve süre sonunda yasal yollara
          başvurulacağını açıkça belirtin.
        </p>

        <h2>3. Noter aracılığıyla gönderin</h2>
        <p>
          İhtarnameyi notere verdiğinizde noter, metni muhataba tebliğ eder ve
          tebliğ tarihini belgeler. Bu tarih, temerrüt faizinin başlangıcı ve
          sürelerin işlemesi açısından kritik öneme sahiptir.
        </p>

        <div className="not-prose my-6 rounded-lg border bg-secondary/40 p-4">
          <p className="text-sm font-medium mb-2">
            Noter onayına hazır ihtarname taslağı oluşturun
          </p>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link href="/ihtarname" className="text-primary hover:underline">
              İhtarname üretici →
            </Link>
            <Link
              href="/ihtarname/kira-tahliye"
              className="text-primary hover:underline"
            >
              Kira tahliye ihtarnamesi →
            </Link>
            <Link
              href="/ihtarname/alacak"
              className="text-primary hover:underline"
            >
              Alacak ihtarnamesi →
            </Link>
          </div>
        </div>

        <h2 className="not-prose text-2xl font-bold mt-10 mb-4">
          Sıkça Sorulan Sorular
        </h2>
        <div className="not-prose space-y-5">
          {FAQ.map((item) => (
            <div key={item.q}>
              <h3 className="font-semibold mb-1">{item.q}</h3>
              <p className="text-muted-foreground text-sm">{item.a}</p>
            </div>
          ))}
        </div>

        <p className="not-prose mt-8 text-xs text-muted-foreground">
          Bu içerik bilgilendirme amaçlıdır, hukuki danışmanlık değildir. Somut
          durumunuz için bir avukata danışın.
        </p>
      </article>
    </>
  );
}
