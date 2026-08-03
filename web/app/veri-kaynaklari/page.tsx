import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";

export const metadata: Metadata = buildMetadata({
  title: "Veri Kaynakları ve Güncelleme Politikası | Hukukçu Yapay Zekası",
  description:
    "Emsal karar veritabanımızın kaynakları, toplama yöntemi ve güncelleme sıklığı. Yargıtay, Danıştay ve AİHM (HUDOC) resmi kaynaklarından derlenen içtihat verisi.",
  path: "/veri-kaynaklari",
});

const datasetJsonLd = {
  "@context": "https://schema.org",
  "@type": "Dataset",
  name: "Hukukçu Yapay Zekası — İcra ve Tahsilat Odaklı Emsal Karar Veri Seti",
  description:
    "Yargıtay, Danıştay ve AİHM (HUDOC) resmi kaynaklarından derlenen, icra ve tahsilat hukukuna öncelik verilerek sınıflandırılmış emsal karar veri seti.",
  creator: { "@type": "Organization", name: "Hukukçu Yapay Zekası" },
  license: "https://hukukcuyapayzekasi.com/kullanim-sartlari",
  temporalCoverage: "2000/..",
};

export default function VeriKaynaklariPage() {
  return (
    <>
      <JsonLd
        data={[
          breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "Veri Kaynakları", url: "/veri-kaynaklari" }]),
          datasetJsonLd,
        ]}
      />
      <div className="container py-10 max-w-3xl prose prose-slate">
        <h1>Veri Kaynakları ve Güncelleme Politikası</h1>
        <p className="text-sm text-muted-foreground">Son güncelleme: 3 Ağustos 2026</p>

        <p>
          Emsal karar veri tabanımız yalnızca resmî ve kamuya açık
          kaynaklardan beslenir; ücretli üçüncü taraf arşivler veya
          doğrulanmamış kaynaklar kullanılmaz.
        </p>

        <h2>Kaynaklar</h2>
        <ul>
          <li>
            <strong>Yargıtay</strong> — Yargıtay Karar Arama Sistemi; özellikle
            icra-iflas hukukuyla ilgili 12. Hukuk Dairesi ve 8. Hukuk Dairesi
            içtihatlarına öncelik verilir.
          </li>
          <li>
            <strong>Danıştay</strong> — Danıştay Karar Arama Sistemi; idari
            yargı ve vergi uyuşmazlıkları.
          </li>
          <li>
            <strong>AİHM</strong> — HUDOC (Avrupa İnsan Hakları Mahkemesi
            karar veritabanı); Türkiye ile ilgili kararlar.
          </li>
        </ul>

        <h2>Yöntem</h2>
        <p>
          Kararlar, ilgili resmî sistemlerden otomatik toplama (scraping)
          araçlarıyla çekilir, temizlenir ve konu/daire/tarih gibi
          meta verilerle etiketlenir. Ardından anlamsal arama için
          vektörleştirilir (embedding) ve <Link href="/emsal-arama">Emsal Karar Arama</Link>{" "}
          aracımızda aranabilir hale getirilir. Bu süreç, sitede yer alan
          &quot;10.000+ emsal karar&quot; ifadesinin karşılığı olan, icra ve
          tahsilat alanına öncelik verilerek sınıflandırılmış bir veri
          setidir — amacımız ham veri hacminde değil, alanımıza özel
          sınıflandırma kalitesinde rakiplerimizden ayrışmaktır.
        </p>

        <h2>Güncelleme sıklığı</h2>
        <p>
          Yargıtay ve Danıştay kararları haftalık, AİHM (HUDOC) içeriği ise
          aylık periyotlarla taranıp veri setine eklenir. Belirli bir kararın
          veri setinde henüz bulunmaması, o kararın var olmadığı anlamına
          gelmez; kesinlik gerektiren durumlarda ilgili mahkemenin resmî
          karar arama sistemine başvurulmalıdır.
        </p>

        <h2>Doğruluk ve düzeltme</h2>
        <p>
          Toplama ve işleme sürecinde nadiren metin bozulması veya
          etiketleme hatası oluşabilir. Böyle bir durumla karşılaşırsanız{" "}
          <a href="mailto:info@hukukcuyapayzekasi.com">
            info@hukukcuyapayzekasi.com
          </a>{" "}
          adresine bildirmenizi rica ederiz; kararın orijinaline her karar
          sayfasında yer alan resmî kaynak bağlantısından ulaşılabilir.
        </p>

        <p>
          Rehber içeriklerimizin (blog) hazırlanma ve inceleme süreci için{" "}
          <Link href="/editoryal-politika">Editoryal Politika</Link>{" "}
          sayfamıza bakabilirsiniz.
        </p>
      </div>
    </>
  );
}
