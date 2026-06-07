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
        <li>AI destekli hukuki araç sunumu</li>
        <li>Hizmet kalitesinin iyileştirilmesi (anonim analitik)</li>
        <li>Yasal yükümlülüklerin yerine getirilmesi</li>
      </ul>
      <h2>Veri Saklama</h2>
      <p>Form metinleri AI işleme sırasında üçüncü taraf LLM sağlayıcılarına (Anthropic, Google) iletilir ancak sunucularımızda kaydedilmez. Tarayıcı oturumunuz sona erdiğinde girişleriniz silinir.</p>
      <h2>KVKK Haklarınız</h2>
      <p>KVKK madde 11 uyarınca veri sorumlusuna başvurarak kendinize ait verilere ilişkin bilgi alma, düzeltme, silme ve kullanım itirazı haklarınızı kullanabilirsiniz.</p>
      <p>İletişim: <a href="mailto:kvkk@hukukemsal.tr">kvkk@hukukemsal.tr</a></p>
    </div>
  );
}
