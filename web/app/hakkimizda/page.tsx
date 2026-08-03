import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";

export const metadata: Metadata = buildMetadata({
  title: "Hakkımızda | Hukukçu Yapay Zekası",
  description:
    "Hukukçu Yapay Zekası (Hukuk Emsal), icra ve tahsilat hukukuna özel yapay zeka destekli emsal karar arama platformudur. Misyonumuz, veri kaynaklarımız ve editoryal sürecimiz.",
  path: "/hakkimizda",
});

export default function HakkimizdaPage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "Hakkımızda", url: "/hakkimizda" }])} />
      <div className="container py-10 max-w-3xl prose prose-slate">
        <h1>Hakkımızda</h1>
        <p className="text-sm text-muted-foreground">Son güncelleme: 3 Ağustos 2026</p>

        <p>
          <strong>Hukukçu Yapay Zekası</strong> (ürün adı: Hukuk Emsal), icra ve
          tahsilat hukukunda çalışan avukatlar ve hukuk profesyonelleri için
          geliştirilmiş, yapay zeka destekli bir emsal karar arama ve
          hukuki üretkenlik platformudur. Yargıtay, Danıştay ve AİHM
          kararları arasında doğal dille arama; icra takibi, itirazın
          iptali, menfi tespit, ihtiyati haciz ve alacak tahsilatı gibi
          konularda ilgili emsalleri bulma sürecini hızlandırmayı
          hedefliyoruz.
        </p>

        <h2>Neden icra ve tahsilat hukuku?</h2>
        <p>
          Genel amaçlı bir &quot;hukuk yapay zekâsı&quot; olmak yerine, önce
          icra ve tahsilat hukukunda derinleşmeyi tercih ettik. Emsal karar
          arama, faiz/harç hesaplama, zamanaşımı takibi ve ihtarname/dilekçe
          üretimi gibi araçlarımızın çekirdeği bu alana göre tasarlandı;
          KVKK uyum kontrolü ve sözleşme analizi gibi diğer modüller bu
          çekirdeği tamamlayan destek araçlarıdır.
        </p>

        <h2>Editoryal ve hukuki doğruluk yaklaşımımız</h2>
        <p>
          Faiz oranı, zamanaşımı süresi ve harç gibi rakamlar dönemsel olarak
          değişir; bu nedenle bu tür veriler sitemizde sabit metin olarak
          değil, kaynak ve yürürlük tarihi ile birlikte, kod seviyesinde
          tarihli bir tablodan üretilir (bkz.{" "}
          <Link href="/faiz-hesaplayici">Faiz Hesaplayıcı</Link> sayfasındaki
          &quot;Kaynak ve son kontrol&quot; bölümü). Rehber içeriklerimizin
          nasıl hazırlandığı ve doğrulandığı için{" "}
          <Link href="/editoryal-politika">Editoryal Politika</Link>
          sayfamıza, emsal karar verisinin kaynağı ve güncelleme sıklığı için{" "}
          <Link href="/veri-kaynaklari">Veri Kaynakları</Link> sayfamıza
          bakabilirsiniz.
        </p>

        <h2>Yapay zeka kullanımı</h2>
        <p>
          Platformumuzdaki dilekçe, ihtarname ve özet gibi üretken araçlar
          yapay zeka modelleri kullanır ve çıktıları <strong>taslak</strong>{" "}
          niteliğindedir; mahkemeye, icra dairesine, notere veya karşı tarafa
          sunulmadan önce mutlaka bir avukat tarafından incelenmelidir. Bu
          konudaki tüm sorumluluk sınırlamaları{" "}
          <Link href="/yasal-uyari">Yasal Uyarı</Link> sayfamızda ayrıntılı
          olarak açıklanmıştır.
        </p>

        <h2>İletişim</h2>
        <p>
          Sorularınız, düzeltme talepleriniz veya iş birliği önerileriniz
          için{" "}
          <a href="mailto:info@hukukcuyapayzekasi.com">
            info@hukukcuyapayzekasi.com
          </a>{" "}
          adresinden bize ulaşabilirsiniz.
        </p>
      </div>
    </>
  );
}
