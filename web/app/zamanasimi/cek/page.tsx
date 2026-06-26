import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { ZamanasimiForm } from "../zamanasimi-form";

export const metadata: Metadata = buildMetadata({
  title: "Çek Zamanaşımı Hesaplama | 3 Yıllık Süre ve Bitiş Tarihi",
  description:
    "Çek zamanaşımı süresini hesaplayın. TTK 6102 uyarınca çekte 3 yıllık kambiyo zamanaşımı; ibraz tarihinden kalan gün ve bitiş tarihini anında öğrenin.",
  path: "/zamanasimi/cek",
  keywords: [
    "çek zamanaşımı",
    "çek zamanaşımı 3 yıl",
    "çek zamanaşımı hesaplama",
    "kambiyo senedi zamanaşımı",
    "çek ibraz süresi",
    "ttk çek zamanaşımı",
  ],
});

const FAQ = [
  {
    q: "Çekte zamanaşımı süresi kaç yıldır?",
    a: "6102 sayılı TTK uyarınca çekte kambiyo hukukundan doğan talepler için zamanaşımı süresi 3 yıldır. Süre, çekin ibraz süresinin bitiminden itibaren işlemeye başlar. Hamilin cirantalara ve düzenleyene karşı talepleri bu süreye tabidir.",
  },
  {
    q: "Çek ibraz süresi ne kadardır?",
    a: "Çek, düzenlendiği yerde ödenecekse 10 gün, başka bir yerde ödenecekse 1 ay içinde muhatap bankaya ibraz edilmelidir. Zamanaşımı, bu ibraz süresinin dolmasıyla başlar; bu nedenle ibraz tarihi hesaplamada kritik öneme sahiptir.",
  },
  {
    q: "Çek zamanaşımı kesilir mi?",
    a: "Evet. Dava açılması, icra takibi, borçlunun borcu ikrar etmesi gibi hallerde zamanaşımı kesilir ve kesilmeden sonra süre yeniden işlemeye başlar. Hesaplayıcı, başlangıç tarihine göre kalan süreyi gösterir; kesilme hallerini ayrıca değerlendirmelisiniz.",
  },
  {
    q: "Zamanaşımına uğramış çek tamamen geçersiz mi olur?",
    a: "Kambiyo (çek) vasfından doğan takip hakkı zamanaşımına uğrar; ancak temel ilişkiden (sözleşme, alacak) doğan talep, genel zamanaşımı süreleri içinde ayrıca dava konusu yapılabilir. Bu durumda çek delil olarak kullanılabilir.",
  },
];

export default function CekZamanasimiPage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbJsonLd([
            { name: "Ana Sayfa", url: "/" },
            { name: "Zamanaşımı", url: "/zamanasimi" },
            { name: "Çek Zamanaşımı", url: "/zamanasimi/cek" },
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
          / <span>Çek Zamanaşımı</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-3">
          Çek Zamanaşımı Hesaplama
        </h1>
        <p className="text-muted-foreground mb-6 max-w-3xl">
          Çekte kambiyo zamanaşımı TTK uyarınca 3 yıldır ve ibraz süresinin
          bitiminden işler. İbraz/başlangıç tarihini girin; kalan gün ve
          zamanaşımı bitiş tarihini anında hesaplayın.
        </p>

        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 mb-6 text-sm">
          ⚠️ <strong>Yasal uyarı:</strong> Hesaplama bilgilendirme amaçlıdır;
          kesilme/durma halleri ve somut olay için avukata danışın.
        </div>

        <ZamanasimiForm />

        <section aria-labelledby="cek-sss" className="mt-12 max-w-3xl">
          <h2 id="cek-sss" className="text-2xl font-bold mb-6">
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
                href="/faiz-hesaplayici"
                className="text-primary hover:underline"
              >
                Çek alacağında faiz hesaplama
              </Link>
            </li>
            <li>
              <Link
                href="/ihtarname/alacak"
                className="text-primary hover:underline"
              >
                Alacak ihtarnamesi örneği
              </Link>
            </li>
            <li>
              <Link
                href="/emsal-arama?q=%C3%A7ek+zamana%C5%9F%C4%B1m%C4%B1"
                className="text-primary hover:underline"
              >
                Çek zamanaşımı konulu emsal kararlar
              </Link>
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}
