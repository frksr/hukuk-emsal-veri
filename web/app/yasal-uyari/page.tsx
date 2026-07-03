import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Yasal Uyarı",
  description:
    "Hukuk Emsal platformunun yasal uyarısı, sorumluluk reddi, veri kaynakları ve üçüncü taraf bağlantılara ilişkin açıklamalar.",
  path: "/yasal-uyari",
});

export default function YasalUyariPage() {
  const guncelleme = "3 Temmuz 2026";
  return (
    <div className="container py-10 max-w-3xl prose prose-slate">
      <h1>Yasal Uyarı</h1>
      <p className="text-sm text-muted-foreground">Son güncelleme: {guncelleme}</p>
      <p>
        Hukuk Emsal platformu, hukuk profesyonellerine ve genel kullanıcılara
        yardımcı bir <strong>yapay zeka destekli üretkenlik aracıdır</strong>.
        Platform bir avukatlık bürosu değildir, avukat-müvekkil ilişkisi
        kurmaz ve sunulan içerikler ile üretilen taslaklar profesyonel hukuki
        danışmanlığın yerine geçmez.
      </p>

      <h2>Sorumluluk Reddi</h2>
      <ul>
        <li>
          Üretilen dilekçe, ihtarname, sözleşme analizi ve karşı argüman
          taslakları <strong>iskelet/taslak niteliğindedir</strong>; somut
          olayın özelliklerine göre uyarlanmadan ve mahkemeye, icra dairesine,
          notere veya karşı tarafa sunulmadan önce mutlaka yetkili bir avukat
          tarafından incelenmeli ve onaylanmalıdır.
        </li>
        <li>
          Faiz, zamanaşımı ve harç/masraf hesaplamaları{" "}
          <strong>yaklaşık değerlerdir</strong> ve girilen verilere
          dayanır; resmi süreçte yetkili mercilerin (icra dairesi, mahkeme
          kalemi vb.) yapacağı hesaplama esastır.
        </li>
        <li>
          KVKK uyum kontrol listesi genel bir öz-değerlendirme aracıdır;
          kurumunuza özgü KVKK uyum sürecinin yerine geçmez.
        </li>
        <li>
          Yapay zeka modelleri, olasılıksal dil modelleri olmaları nedeniyle
          hatalı, eksik veya güncel olmayan bilgi (&quot;halüsinasyon&quot;)
          üretebilir. Üretilen her içerik, kullanılmadan önce kullanıcı
          tarafından doğrulanmalıdır.
        </li>
        <li>
          Emsal karar metinleri resmi kaynaklardan derlenmiştir; metinlerde
          işleme/dönüştürme sırasında oluşabilecek hatalara karşı tam
          doğruluk için orijinal kaynağa (Yargıtay/Danıştay karar arama
          sistemi, HUDOC) başvurulması önerilir.
        </li>
        <li>
          Yürürlükteki mevzuatın izin verdiği azami ölçüde, Platform ve
          işleteni, içeriklerin kullanımından doğan doğrudan veya dolaylı
          hiçbir maddi/manevi zarardan sorumlu tutulamaz. Ayrıntılı
          sorumluluk sınırlaması için{" "}
          <a href="/kullanim-sartlari">Kullanım Şartları</a> madde 7&apos;ye
          bakınız.
        </li>
      </ul>

      <h2>Veri Kaynakları</h2>
      <p>
        Emsal kararlar; Yargıtay Karar Arama Sistemi, Danıştay Karar Arama
        Sistemi ve HUDOC (Avrupa İnsan Hakları Mahkemesi) gibi resmi ve
        kamuya açık kaynaklardan derlenmiştir. Platform bu kararları
        aranabilir hale getirir ve yapay zeka destekli özetleme/eşleştirme
        sağlar; kararların içeriğinden veya yayınlayan resmi kurumun
        güncellemelerinden Platform sorumlu değildir.
      </p>

      <h2>Üçüncü Taraf Bağlantılar ve Hizmetler</h2>
      <p>
        Platform, ödeme işlemleri için iyzico, yapay zeka üretimi için
        Anthropic ve Google gibi üçüncü taraf hizmet sağlayıcılarını
        kullanır (bkz. <a href="/gizlilik">Gizlilik Politikası</a>).
        Platform üzerinde resmi kurumların (Yargıtay, Danıştay, UYAP vb.)
        sitelerine yönlendiren bağlantılar bulunabilir; bu üçüncü taraf
        sitelerin içeriğinden ve gizlilik uygulamalarından Platform sorumlu
        değildir.
      </p>

      <h2>Fikri Mülkiyet</h2>
      <p>
        Bu sayfadaki uyarılar, Platform&apos;un genel kullanım koşullarını
        tamamlar niteliktedir; ayrıntılı fikri mülkiyet ve hesap
        hükümleri için <a href="/kullanim-sartlari">Kullanım Şartları</a>{" "}
        sayfasına bakınız.
      </p>

      <h2>İletişim</h2>
      <p>
        Soru ve geri bildirimleriniz için{" "}
        <a href="mailto:info@hukukcuyapayzekasi.com">
          info@hukukcuyapayzekasi.com
        </a>{" "}
        adresine yazabilirsiniz.
      </p>
    </div>
  );
}
