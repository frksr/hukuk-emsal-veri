import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Cayma ve İade Politikası",
  description:
    "Hukuk Emsal abonelik ve ek paket satın alımlarında iade yapılmadığına, cayma hakkının neden uygulanmadığına ve abonelik iptal sürecine ilişkin açıklamalar.",
  path: "/iade-politikasi",
});

export default function IadePolitikasiPage() {
  return (
    <div className="container py-10 max-w-3xl">
      <nav className="text-sm text-muted-foreground mb-4">
        <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Cayma ve İade Politikası</span>
      </nav>
      <h1 className="text-3xl md:text-4xl font-bold mb-8">Cayma ve İade Politikası</h1>

      <div className="policy-content rounded-xl border bg-card p-6 md:p-8 shadow-sm">
      {/*
        SİTE SAHİBİ İÇİN NOT: İletişim kanalı /panel/oneri (Bize Yazın) sayfasıdır.
        Yayına almadan önce metni bir avukata inceletin.
      */}
      <p>
        Bu politika, Hukuk Emsal platformu üzerinden satın alınan aylık
        abonelikler ve tek seferlik ek paketler için iptal sürecini ve iade
        yapılmama koşullarını açıklar. Ayrıntılı sözleşme hükümleri için{" "}
        <a href="/mesafeli-satis">Mesafeli Satış Sözleşmesi</a> sayfasına
        bakınız.
      </p>

      <p className="rounded-lg border border-amber-400/40 bg-amber-400/10 p-4 not-prose">
        <strong>Özet:</strong> Hukuk Emsal, dijital bir hizmettir; ödeme
        onayıyla birlikte anında ifa edilmeye başlandığından satın alınan
        abonelik ve ek paketler için <strong>hiçbir şekilde iade
        yapılmaz</strong>. Aboneliğinizi dilediğiniz an iptal edebilirsiniz;
        iptal yalnızca bir sonraki dönemin tahsilatını durdurur — <strong>
        ödemesi yapılmış cari dönem sonuna kadar kullanım hakkınız devam
        eder</strong>, dönem sonunda abonelik <strong>otomatik olarak
        yenilenmez</strong> ve hesabınız ücretsiz plan koşullarına döner.
      </p>

      <h2>Genel Kural: İade Yapılmaz</h2>
      <ul>
        <li>
          Abonelik yenileme dönemleri için: bir sonraki dönemin tahsilatını
          istemiyorsanız, yenileme tarihinden önce panel üzerinden aboneliğinizi
          iptal edebilirsiniz. İptal işlemi geriye dönük iade doğurmaz;
          ödemesi zaten yapılmış <strong>cari dönem sonuna kadar kullanım
          hakkınız devam eder</strong>, abonelik <strong>otomatik olarak
          yenilenmez</strong> ve dönem sonunda hesabınız ücretsiz plan
          koşullarına döner veya ek paket kredileriniz varsa onlarla sınırlı
          kullanıma geçer.
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
        <li>
          Tek seferlik ek paket kredileri de aynı kurala tabidir: satın alma
          sonrası iade yapılmaz. Krediler, hesabınızda kullanılana kadar
          geçerliliğini korur; kullanılmayan kredi için bedel iadesi
          yapılmaz.
        </li>
      </ul>

      <h2>14 Günlük Yasal Cayma Hakkı Neden Uygulanmaz?</h2>
      <p>
        Mesafeli Sözleşmeler Yönetmeliği, tüketiciye satın alma tarihinden
        itibaren 14 gün içinde gerekçe göstermeden cayma hakkı tanır (6502
        sayılı Kanun). Ancak Yönetmelik&apos;in 15 inci maddesi uyarınca, tüketicinin
        onayı ile ifasına başlanan hizmetlere ve elektronik ortamda anında
        ifa edilen gayrimaddi mallara ilişkin sözleşmelerde bu hak istisna
        kapsamındadır. Hizmetimiz dijitaldir ve ödeme onayıyla birlikte
        hesabınıza <strong>anında tanımlanır</strong>; ödeme adımında,
        hizmetin ifasına derhal başlanmasını onayladığınızı ve bu onayla
        birlikte cayma hakkınızı kaybettiğinizi kabul edersiniz. Bu nedenle
        satın alma sonrasında cayma veya iade talebi kabul edilmez.
      </p>

      <h2>İptal Nasıl Yapılır?</h2>
      <p>
        Aboneliğinizi panel üzerinden dilediğiniz an iptal edebilirsiniz;
        iptal sonrasında cari dönem sonuna kadar kullanmaya devam edersiniz ve
        dönem sonunda abonelik yenilenmez. Sorularınız için{" "}
        <Link href="/panel/oneri">Bize Yazın</Link>{" "}
        sayfasından bize ulaşabilirsiniz.
      </p>

      <h2>Uyuşmazlık</h2>
      <p>
        Çözülemeyen uyuşmazlıklarda, parasal sınırlar dahilinde yerleşim
        yerinizdeki Tüketici Hakem Heyetlerine, sınırı aşan uyuşmazlıklarda
        Tüketici Mahkemelerine başvurabilirsiniz.
      </p>
      </div>
    </div>
  );
}
