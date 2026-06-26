import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { IhtarnameForm } from "../ihtarname-form";

export const metadata: Metadata = buildMetadata({
  title: "Kira Tahliye İhtarnamesi Örneği | Noter Onayına Hazır",
  description:
    "Kira tahliye ihtarnamesi örneği oluşturun. İki haklı ihtar, ödenmeyen kira ve tahliye taahhüdü için TBK 315 ve 352 referanslı noter onayına hazır taslak.",
  path: "/ihtarname/kira-tahliye",
  keywords: [
    "kira tahliye ihtarnamesi",
    "kira tahliye ihtarnamesi örneği",
    "iki haklı ihtar",
    "ödenmeyen kira ihtarnamesi",
    "tbk 315 ihtar",
    "kiracı tahliye ihtarı",
    "noter ihtarnamesi kira",
  ],
});

const FAQ = [
  {
    q: "Kira tahliye ihtarnamesi hangi durumlarda çekilir?",
    a: "Kira bedelinin ödenmemesi (TBK 315 temerrüt), bir kira yılı içinde iki haklı ihtara konu olacak gecikmeler (TBK 352/2) veya yazılı tahliye taahhüdüne uyulmaması hallerinde tahliye sürecinin ilk adımı olarak ihtarname çekilir.",
  },
  {
    q: "İki haklı ihtar nedir, tahliye için yeterli mi?",
    a: "Bir kira yılı içinde kiracıya kira borcu nedeniyle yazılı olarak iki kez haklı ihtar gönderilmesidir. TBK 352/2 uyarınca iki haklı ihtar, kira süresinin bitiminden itibaren açılacak tahliye davasında haklı sebep oluşturur. İhtarların noterden ve usulüne uygun yapılması önemlidir.",
  },
  {
    q: "Kira ödenmediğinde ne kadar süre verilir?",
    a: "TBK 315 uyarınca konut ve çatılı işyeri kiralarında temerrüt nedeniyle fesih için kiracıya en az 30 günlük süre verilerek ihtar edilir. Süre, ihtarın kiracıya tebliğinden itibaren işler. Bu süre içinde ödeme yapılmazsa tahliye davası açılabilir.",
  },
  {
    q: "İhtarname noterden mi çekilmeli?",
    a: "Geçerlilik için şart olmasa da ispat açısından noter ihtarnamesi güçlü biçimde önerilir. Noter, ihtarın içeriğini ve tebliğ tarihini resmî olarak belgeler; bu da olası tahliye davasında delil değeri taşır.",
  },
];

export default function KiraTahliyeIhtarnamePage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbJsonLd([
            { name: "Ana Sayfa", url: "/" },
            { name: "İhtarname", url: "/ihtarname" },
            { name: "Kira Tahliye İhtarnamesi", url: "/ihtarname/kira-tahliye" },
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
          <Link href="/ihtarname" className="hover:text-foreground">
            İhtarname
          </Link>{" "}
          / <span>Kira Tahliye İhtarnamesi</span>
        </nav>

        <h1 className="text-3xl md:text-4xl font-bold mb-3">
          Kira Tahliye İhtarnamesi Örneği
        </h1>
        <p className="text-muted-foreground mb-6 max-w-3xl">
          Ödenmeyen kira, iki haklı ihtar (TBK 352/2) ve temerrüt (TBK 315)
          senaryoları için noter onayına hazır kira tahliye ihtarnamesi taslağı
          oluşturun. Taraf bilgilerini ve talebinizi girin; sistem ilgili madde
          atıflarıyla metni hazırlasın.
        </p>

        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 mb-6 text-sm">
          ⚠️ <strong>Yasal uyarı:</strong> Yapay Zeka taslağı, noter onayından
          ve tahliye davası açılmadan önce avukat incelemesi gerektirir.
        </div>

        <IhtarnameForm />

        <section
          aria-labelledby="kira-tahliye-sss"
          className="mt-12 max-w-3xl"
        >
          <h2
            id="kira-tahliye-sss"
            className="text-2xl font-bold mb-6"
          >
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
                href="/ihtarname/alacak"
                className="text-primary hover:underline"
              >
                Alacak (temerrüt) ihtarnamesi örneği
              </Link>
            </li>
            <li>
              <Link
                href="/zamanasimi"
                className="text-primary hover:underline"
              >
                Kira alacağı zamanaşımı hesaplama
              </Link>
            </li>
            <li>
              <Link
                href="/emsal-arama?q=kira+tahliye+iki+hakl%C4%B1+ihtar"
                className="text-primary hover:underline"
              >
                Kira tahliye konulu emsal kararlar
              </Link>
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}
