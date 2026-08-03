import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";

export const metadata: Metadata = buildMetadata({
  title: "Editoryal Politika | Hukukçu Yapay Zekası",
  description:
    "Hukukçu Yapay Zekası rehber içeriklerinin nasıl hazırlandığı, kaynaklandığı, incelendiği ve güncellendiğine ilişkin editoryal politikamız.",
  path: "/editoryal-politika",
});

export default function EditoryalPolitikaPage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "Editoryal Politika", url: "/editoryal-politika" }])} />
      <div className="container py-10 max-w-3xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <Link href="/" className="hover:text-foreground">Ana Sayfa</Link> / <span>Editoryal Politika</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-2">Editoryal Politika</h1>
        <p className="text-sm text-muted-foreground mb-8">Son güncelleme: 3 Ağustos 2026</p>

        <div className="policy-content rounded-xl border bg-card p-6 md:p-8 shadow-sm">
        <p>
          Bu sayfa, <Link href="/blog">Hukuk Rehberi</Link> altında
          yayınladığımız makalelerin nasıl hazırlandığını, kaynaklandığını ve
          güncellendiğini açıklar.
        </p>

        <h2>İçerik nasıl hazırlanır?</h2>
        <ul>
          <li>
            Makaleler, ilgili mevzuat (kanun, yönetmelik, tebliğ), Resmî
            Gazete metinleri ve — varsa — güncel Yargıtay/Danıştay
            içtihadı esas alınarak hazırlanır.
          </li>
          <li>
            İçerik üretim sürecinde yapay zeka araçlarından yararlanılır;
            ancak yayınlanan her makale editoryal ekip tarafından gözden
            geçirilir. Bir makalenin ayrıca bir hukukçu tarafından
            incelendiği durumlarda, bu kişi ve unvanı makalenin başında{" "}
            <em>&quot;İçerik incelemesi&quot;</em> etiketiyle açıkça belirtilir.
          </li>
          <li>
            Sayısal/dönemsel veriler (faiz oranı, zamanaşımı süresi, harç
            tutarı vb.) her makalede kaynak ve yürürlük tarihiyle birlikte
            verilir; mümkün olduğunca sabit metin yerine kod seviyesinde
            tarihli tablolardan üretilen araçlara (ör.{" "}
            <Link href="/faiz-hesaplayici">Faiz Hesaplayıcı</Link>) atıf
            yapılır.
          </li>
        </ul>

        <h2>Kaynakça</h2>
        <p>
          Mümkün olan makalelerde, dayanılan mevzuat ve resmî kaynaklar
          makalenin sonunda &quot;Kaynakça&quot; başlığı altında listelenir.
          Kaynakça bulunmayan eski makaleler kademeli olarak
          güncellenmektedir.
        </p>

        <h2>Güncelleme ve düzeltme</h2>
        <p>
          Mevzuat değişikliği veya hata bildirimi durumunda ilgili makale
          güncellenir ve sayfa üzerindeki &quot;son güncelleme&quot; tarihi
          otomatik olarak yenilenir. Bir hata fark ederseniz{" "}
          <a href="mailto:info@hukukcuyapayzekasi.com">
            info@hukukcuyapayzekasi.com
          </a>{" "}
          adresine bildirebilirsiniz; bildirimler makul sürede
          değerlendirilir.
        </p>

        <h2>Bağımsızlık</h2>
        <p>
          Rehber içeriklerimiz ücretli reklam veya sponsorluk karşılığında
          yazılmaz. Platformumuzun araçlarına yapılan iç bağlantılar,
          okuyucuyu ilgili işlevsel sayfaya yönlendirmek amacı taşır ve
          içeriğin hukuki doğruluğunu etkilemez.
        </p>

        <h2>Yapay zeka açıklaması</h2>
        <p>
          Rehber makalelerinin taslak aşamasında yapay zeka araçları
          kullanılabilir. Bu, ürünümüzdeki dilekçe/ihtarname/özet gibi
          kullanıcıya özel üretken araçlardan farklıdır — onlar için geçerli
          sorumluluk sınırlamaları <Link href="/yasal-uyari">Yasal Uyarı</Link>{" "}
          sayfasındadır.
        </p>
        </div>
      </div>
    </>
  );
}
