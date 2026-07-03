import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Cayma ve İade Politikası",
  description:
    "Hukuk Emsal abonelik ve ek paket satın alımlarında cayma hakkı, kısmi iade kuralları ve iade süreci.",
  path: "/iade-politikasi",
});

export default function IadePolitikasiPage() {
  return (
    <div className="container py-10 max-w-3xl prose prose-slate">
      {/*
        SİTE SAHİBİ İÇİN NOT: Destek e-posta adresini (destek@hukukcuyapayzekasi.com)
        teyit edin / gerekirse değiştirin. Yayına almadan önce metni bir avukata
        inceletin.
      */}
      <h1>Cayma ve İade Politikası</h1>
      <p>
        Bu politika, Hukuk Emsal platformu üzerinden satın alınan aylık
        abonelikler ve tek seferlik ek paketler için iptal, cayma hakkı ve
        iade sürecini açıklar. Ayrıntılı sözleşme hükümleri için{" "}
        <a href="/mesafeli-satis">Mesafeli Satış Sözleşmesi</a> sayfasına
        bakınız.
      </p>

      <p className="rounded-lg border border-amber-400/40 bg-amber-400/10 p-4 not-prose">
        <strong>Özet:</strong> Hukuk Emsal, dijital bir hizmettir ve satın
        alınan/kullanılan dönemler için <strong>ücret iadesi yapılmaz</strong>.
        Aboneliğinizi dilediğiniz an iptal edebilirsiniz; iptal yalnızca bir
        sonraki dönemin tahsilatını durdurur — <strong>ödemesi yapılmış cari
        dönem sonuna kadar kullanımınız açık kalır</strong>, dönem bitiminde
        erişiminiz otomatik olarak kısıtlanır/ücretsiz plana döner. Aşağıdaki
        14 günlük yasal cayma hakkı, yalnızca hizmeti hiç kullanmamış yeni
        satın almalar için geçerli olan dar kapsamlı bir istisnadır.
      </p>

      <h2>Genel Kural: Kullanılan Dönemler İçin İade Yok</h2>
      <ul>
        <li>
          Abonelik yenileme dönemleri için: bir sonraki dönemin tahsilatını
          istemiyorsanız, yenileme tarihinden önce panel üzerinden aboneliğinizi
          iptal edebilirsiniz. İptal işlemi geriye dönük iade doğurmaz;
          ödemesi zaten yapılmış <strong>cari dönem sonuna kadar erişiminiz
          devam eder</strong>, dönem sonunda hesabınız otomatik olarak
          ücretsiz plan koşullarına döner veya ek paket kredileriniz varsa
          onlarla sınırlı kullanıma geçer.
        </li>
        <li>
          Ay içinde iptal etseniz dahi, o aya ait ödenen tutarın gün bazında
          orantılı (pro-rata) iadesi yapılmaz.
        </li>
        <li>
          Yenileme tahsilatının kart/ödeme sorunu nedeniyle başarısız olması
          farklı bir durumdur; bu durumda ücret zaten tahsil edilmediği için
          hizmet askıya alınır, iade söz konusu olmaz.
        </li>
      </ul>

      <h2>14 Günlük Yasal Cayma Hakkı (Dar Kapsamlı İstisna)</h2>
      <ul>
        <li>
          Satın alma tarihinden itibaren <strong>14 gün</strong> içinde gerekçe
          göstermeden cayma hakkınız vardır (6502 sayılı Kanun ve Mesafeli
          Sözleşmeler Yönetmeliği).
        </li>
        <li>
          Hizmetimiz dijitaldir ve ödeme onayıyla birlikte hesabınıza{" "}
          <strong>anında tanımlanır</strong>. Mesafeli Sözleşmeler
          Yönetmeliği&apos;nin 15 inci maddesi uyarınca, onayınızla ifasına
          başlanan ve elektronik ortamda anında ifa edilen hizmetlerde cayma
          hakkı istisna kapsamındadır.
        </li>
        <li>
          Buna rağmen, abonelik veya ek paket haklarınızı{" "}
          <strong>henüz hiç kullanmadıysanız</strong> (tek bir arama, hesaplama
          veya üretim dahi yapmadıysanız), 14 gün içinde yapacağınız cayma
          talebini kabul ediyor ve bedelin tamamını iade ediyoruz. Hizmeti
          kullanmaya başladığınız andan itibaren bu istisna sona erer ve
          yukarıdaki genel kural (iade yok) uygulanır.
        </li>
      </ul>

      <h2>Ek Paketlerde Kısmi İade</h2>
      <ul>
        <li>
          Tek seferlik ek paket kredileri <strong>hiç kullanılmamışsa</strong>:
          14 gün içindeki cayma talebinde bedelin tamamı iade edilir.
        </li>
        <li>
          Krediler <strong>kısmen kullanılmışsa</strong>: cayma süresi içindeki
          taleplerde, kullanılan kredi oranı toplam bedelden düşülür ve kalan
          tutar iade edilir. Kullanılan oran, talebin bize ulaştığı andaki
          hesap kayıtlarına göre belirlenir.
        </li>
        <li>
          Kredilerin <strong>tamamı kullanılmışsa</strong> hizmet ifa edilmiş
          sayılır ve iade yapılmaz.
        </li>
      </ul>

      <h2>İade Kanalı ve Süresi</h2>
      <ul>
        <li>
          İadeler, ödemenin alındığı kanal olan <strong>iyzico</strong>{" "}
          üzerinden, ödemede kullandığınız <strong>karta</strong> yapılır; başka
          bir hesaba havale/EFT ile iade yapılmaz.
        </li>
        <li>
          İade, cayma bildiriminizin bize ulaşmasından itibaren en geç{" "}
          <strong>14 gün içinde</strong> başlatılır.
        </li>
        <li>
          Tutarın kart ekstrenize yansıması, bankanızın işlem sürelerine bağlı
          olarak birkaç iş günü sürebilir.
        </li>
      </ul>

      <h2>Talep Nasıl Yapılır?</h2>
      <p>
        Cayma ve iade taleplerinizi, hesabınıza kayıtlı e-posta adresinizden,
        sipariş/işlem bilgilerinizi (tarih, plan veya paket adı) belirterek{" "}
        <a href="mailto:destek@hukukcuyapayzekasi.com">
          destek@hukukcuyapayzekasi.com
        </a>{" "}
        adresine iletebilirsiniz. Talebiniz en geç 3 iş günü içinde
        yanıtlanır.
      </p>

      <h2>Uyuşmazlık</h2>
      <p>
        Çözülemeyen uyuşmazlıklarda, parasal sınırlar dahilinde yerleşim
        yerinizdeki Tüketici Hakem Heyetlerine, sınırı aşan uyuşmazlıklarda
        Tüketici Mahkemelerine başvurabilirsiniz.
      </p>
    </div>
  );
}
