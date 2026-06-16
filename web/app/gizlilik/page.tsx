import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Gizlilik Politikası",
  description: "Hukuk Emsal KVKK uyumlu gizlilik ve veri işleme politikası.",
  path: "/gizlilik",
});

export default function GizlilikPage() {
  return (
    <div className="container py-10 max-w-3xl prose prose-slate">
      <h1>Gizlilik Politikası</h1>
      <p>Bu politika, Hukuk Emsal platformunun KVKK (6698 sayılı Kişisel Verilerin Korunması Kanunu) kapsamında veri işleme uygulamalarını açıklar.</p>
      <h2>Toplanan Veriler</h2>
      <ul>
        <li>Form girişleriniz (dilekçe, ihtarname, sözleşme metinleri) — geçici olarak işlenir, kaydedilmez</li>
        <li>Anonim kullanım istatistikleri (sayfa görüntüleme, oturum süresi)</li>
        <li>Kullanıcı hesabı oluştururken: e-posta, ad-soyad (opsiyonel)</li>
      </ul>
      <h2>Veri İşleme Amaçları</h2>
      <ul>
        <li>Yapay Zeka destekli hukuki araç sunumu</li>
        <li>Hizmet kalitesinin iyileştirilmesi (anonim analitik)</li>
        <li>Yasal yükümlülüklerin yerine getirilmesi</li>
      </ul>
      <h2>Veri Saklama</h2>
      <p>Form metinleri Yapay Zeka işleme sırasında üçüncü taraf LLM sağlayıcılarına (Anthropic, Google) iletilir ancak sunucularımızda kaydedilmez. Tarayıcı oturumunuz sona erdiğinde girişleriniz silinir.</p>
      <h2>Ödeme ve Kimlik Bilgileri</h2>
      <p>Abonelik ve ek paket ödemeleri, lisanslı ödeme kuruluşu <strong>iyzico</strong> altyapısı üzerinden alınır. Ödeme sırasında istenen <strong>TC Kimlik Numarası</strong> ve kart bilgileri, yasal zorunluluk (MASAK ve 5549 sayılı Kanun) gereği yalnızca iyzico tarafından talep edilir ve işlenir. Bu bilgiler <strong>tarafımızca hiçbir şekilde saklanmaz, kaydedilmez veya loglanmaz</strong>; yalnızca ödeme anında güvenli bağlantı üzerinden doğrudan iyzico'ya iletilir. Tarafımızda yalnızca işlem sonucu (ödeme durumu, tutar, plan/paket bilgisi) tutulur. Kart verileri hiçbir aşamada sunucularımıza ulaşmaz.</p>
      <h2>KVKK Haklarınız</h2>
      <p>KVKK madde 11 uyarınca veri sorumlusuna başvurarak kendinize ait verilere ilişkin bilgi alma, düzeltme, silme ve kullanım itirazı haklarınızı kullanabilirsiniz.</p>
      <p>İletişim: <a href="mailto:kvkk@hukukcuyapayzekasi.com">kvkk@hukukcuyapayzekasi.com</a></p>
    </div>
  );
}
