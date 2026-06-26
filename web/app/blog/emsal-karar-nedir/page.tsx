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

const SLUG = "emsal-karar-nedir";
const makale = makaleBul(SLUG)!;

export const metadata: Metadata = buildMetadata({
  title: "Emsal Karar Nedir? Yargıtay-Danıştay Kararları Rehberi",
  description:
    "Emsal karar nedir, içtihattan farkı nedir, bir davada nasıl gerekçe olarak kullanılır? Yargıtay ve Danıştay emsal kararları için sade rehber.",
  path: `/blog/${SLUG}`,
  type: "article",
  publishedTime: makale.yayinTarihi,
  authors: [makale.yazar],
  keywords: [
    "emsal karar nedir",
    "emsal karar",
    "içtihat nedir",
    "yargıtay kararı emsal",
    "emsal karar bağlayıcı mı",
  ],
});

const FAQ = [
  {
    q: "Emsal karar bağlayıcı mıdır?",
    a: "Kural olarak emsal kararlar bağlayıcı değil, yol göstericidir. İstisnası, Yargıtay İçtihadı Birleştirme Kararları (İBK) ve Anayasa Mahkemesi'nin bireysel başvuru kararlarıdır; bunlar benzer uyuşmazlıklarda bağlayıcı niteliktedir.",
  },
  {
    q: "Emsal karar ile içtihat arasındaki fark nedir?",
    a: "İçtihat, mahkemelerin benzer hukuki sorunlara getirdiği yerleşik yorumdur. Emsal karar ise somut bir uyuşmazlıkta dayanak gösterilen tekil karardır. Bir emsal karar, yerleşik içtihadın örneği olabilir.",
  },
  {
    q: "Emsal kararı dilekçede nasıl kullanırım?",
    a: "Kararın mahkemesi, esas ve karar numarası ile tarihini belirtip, kararın olayınızla benzeşen hukuki tespitini gerekçe olarak gösterirsiniz. Birden çok yönde emsal varsa lehinize olanları öne çıkarmak etkili olur.",
  },
];

export default function EmsalKararNedirPage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbJsonLd([
            { name: "Ana Sayfa", url: "/" },
            { name: "Rehber", url: "/blog" },
            { name: "Emsal Karar Nedir?", url: `/blog/${SLUG}` },
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
          / <span>Emsal Karar Nedir?</span>
        </nav>

        <h1>Emsal Karar Nedir? Yargıtay ve Danıştay Kararları Nasıl Kullanılır?</h1>

        <p>
          <strong>Emsal karar</strong>, benzer bir hukuki uyuşmazlıkta daha önce
          verilmiş ve sonraki davalarda yol gösterici olarak kullanılan mahkeme
          kararıdır. Avukatlar ve hâkimler, bir olaydaki hukuki sorunu
          değerlendirirken aynı yönde verilmiş yüksek mahkeme kararlarını gerekçe
          olarak gösterir. Türk hukukunda en sık başvurulan kaynaklar Yargıtay
          (özel hukuk ve ceza) ile Danıştay (idari yargı) kararlarıdır.
        </p>

        <h2>Emsal karar bağlayıcı mıdır?</h2>
        <p>
          Genel kural olarak emsal kararlar <em>bağlayıcı değil</em>, ikna edici
          niteliktedir. Yani bir mahkeme, başka bir kararı dikkate almak zorunda
          değildir ama uygulamada yerleşik içtihada uygun karar verme eğilimi
          güçlüdür. Bu kuralın istisnaları vardır: Yargıtay İçtihadı Birleştirme
          Kararları (İBK) ve Anayasa Mahkemesi'nin bireysel başvuru kararları,
          benzer uyuşmazlıklarda bağlayıcıdır.
        </p>

        <h2>Emsal karar ile içtihat farkı</h2>
        <p>
          İçtihat, mahkemelerin zaman içinde oluşturduğu yerleşik yorumu ifade
          eder; emsal karar ise bu yorumun somut bir örneğidir. Bir başka deyişle
          her emsal karar içtihadın bir parçası olabilir, ancak içtihat tek bir
          karardan ibaret değildir.
        </p>

        <h2>Bir davada emsal karar nasıl kullanılır?</h2>
        <p>
          Etkili kullanım için kararın mahkemesi, esas/karar numarası ve tarihi
          belirtilir; ardından kararın sizin olayınızla benzeşen hukuki tespiti
          dilekçede gerekçe olarak gösterilir. Karşı tarafın aleyhe emsal sunma
          ihtimaline karşı, lehe kararların güncel ve aynı daireden olmasına
          dikkat etmek önemlidir.
        </p>

        <div className="not-prose my-6 rounded-lg border bg-secondary/40 p-4">
          <p className="text-sm font-medium mb-2">
            Olayınıza uygun emsal kararı bulun
          </p>
          <Link
            href="/emsal-arama"
            className="text-primary hover:underline text-sm"
          >
            Yapay Zeka destekli emsal karar aramayı deneyin →
          </Link>
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
