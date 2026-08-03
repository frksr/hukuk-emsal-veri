import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Mesafeli Satış Sözleşmesi",
  description:
    "Hukuk Emsal abonelik ve ek paket satışlarına ilişkin mesafeli satış sözleşmesi (6502 sayılı Kanun ve Mesafeli Sözleşmeler Yönetmeliği uyarınca).",
  path: "/mesafeli-satis",
});

export default function MesafeliSatisPage() {
  return (
    <div className="container py-10 max-w-3xl">
      <nav className="text-sm text-muted-foreground mb-4">
        <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Mesafeli Satış Sözleşmesi</span>
      </nav>
      <h1 className="text-3xl md:text-4xl font-bold mb-8">Mesafeli Satış Sözleşmesi</h1>

      <div className="policy-content rounded-xl border bg-card p-6 md:p-8 shadow-sm">
      {/*
        SİTE SAHİBİ İÇİN NOT: Aşağıdaki köşeli parantezli alanları ([ŞİRKET ÜNVANI],
        [ADRES], [MERSİS NO], [VERGİ DAİRESİ / VERGİ NO], [TELEFON]) şirket
        bilgileriyle doldurun ve yayına almadan önce metnin tamamını bir avukata
        inceletin. E-posta adreslerinin aktif olduğunu doğrulayın.
      */}
      <p>
        İşbu Mesafeli Satış Sözleşmesi (&quot;Sözleşme&quot;), 6502 sayılı
        Tüketicinin Korunması Hakkında Kanun ve Mesafeli Sözleşmeler Yönetmeliği
        hükümleri uyarınca, aşağıda bilgileri yer alan Satıcı ile Hukuk Emsal
        platformu üzerinden abonelik veya ek paket satın alan Alıcı arasında
        elektronik ortamda kurulmuştur.
      </p>

      <h2>1. Taraflar</h2>
      <h3>1.1. Satıcı</h3>
      <ul>
        <li>
          <strong>Ünvan:</strong> [ŞİRKET ÜNVANI]
        </li>
        <li>
          <strong>Adres:</strong> [ADRES]
        </li>
        <li>
          <strong>MERSİS No:</strong> [MERSİS NO]
        </li>
        <li>
          <strong>Vergi Dairesi / No:</strong> [VERGİ DAİRESİ / VERGİ NO]
        </li>
        <li>
          <strong>Telefon:</strong> [TELEFON]
        </li>
        <li>
          <strong>İletişim:</strong>{" "}
          <Link href="/panel/oneri">Bize Yazın</Link> sayfası
        </li>
      </ul>
      <h3>1.2. Alıcı</h3>
      <p>
        Hukuk Emsal platformuna üye olan ve sipariş sırasında hesap bilgilerinde
        yer alan ad-soyad ve e-posta adresini bildiren gerçek veya tüzel kişidir
        (&quot;Alıcı&quot;). Alıcı&apos;nın sipariş sırasında bildirdiği bilgiler
        esas alınır.
      </p>

      <h2>2. Sözleşmenin Konusu</h2>
      <p>
        İşbu Sözleşme&apos;nin konusu, Alıcı&apos;nın Satıcı&apos;ya ait Hukuk
        Emsal platformu üzerinden elektronik ortamda siparişini verdiği aşağıda
        nitelikleri belirtilen dijital hizmetin satışı ve ifası ile ilgili olarak
        tarafların hak ve yükümlülüklerinin belirlenmesidir.
      </p>

      <h2>3. Sözleşme Konusu Hizmetin Nitelikleri</h2>
      <ul>
        <li>
          <strong>Aylık abonelik planları:</strong> Yapay zeka destekli emsal
          karar arama, dilekçe/ihtarname taslağı üretimi, sözleşme analizi ve
          ilgili hukuki araçlara plan kapsamındaki limitler dahilinde erişim.
          Abonelik, aylık dönemler halinde yenilenir.
        </li>
        <li>
          <strong>Tek seferlik ek paketler:</strong> Abonelik limitlerine ek
          kullanım hakkı (kredi) tanıyan, bir defaya mahsus satın alınan dijital
          paketlerdir.
        </li>
      </ul>
      <p>
        Hizmetin temel özellikleri, kapsamı, kullanım limitleri ve vergiler dahil
        toplam satış fiyatı, sipariş anında{" "}
        <a href="/fiyatlandirma">Fiyatlandırma</a> sayfasında ve ödeme ekranında
        Alıcı&apos;ya gösterilir. İlan edilen fiyatlar güncellenene kadar
        geçerlidir; süreli fiyatlar belirtilen süre sonuna kadar geçerlidir.
      </p>

      <h2>4. Ödeme ve Faturalandırma</h2>
      <p>
        Ödemeler, lisanslı ödeme kuruluşu <strong>iyzico</strong> altyapısı
        üzerinden kredi kartı / banka kartı ile alınır. Kart bilgileri Satıcı
        tarafından saklanmaz; ödeme güvenliği iyzico tarafından sağlanır. Aylık
        abonelik bedeli her yenileme döneminde kayıtlı ödeme yöntemi üzerinden
        tahsil edilir. Yenileme tahsilatının başarısız olması halinde hizmet
        askıya alınabilir. Fatura, Alıcı&apos;nın bildirdiği e-posta adresine
        elektronik ortamda iletilir.
      </p>

      <h2>5. Hizmetin İfası</h2>
      <p>
        Sözleşme konusu hizmet dijital niteliktedir; ödemenin onaylanmasıyla
        birlikte abonelik hakları ve/veya ek paket kredileri Alıcı&apos;nın
        hesabına derhal tanımlanır ve hizmetin ifasına anında başlanır. Fiziki
        teslimat söz konusu değildir.
      </p>

      <h2>6. Cayma Hakkı</h2>
      <p>
        Alıcı, Mesafeli Sözleşmeler Yönetmeliği uyarınca, sözleşmenin kurulduğu
        tarihten itibaren <strong>14 (on dört) gün</strong> içinde herhangi bir
        gerekçe göstermeksizin ve cezai şart ödemeksizin cayma hakkına sahiptir.
      </p>
      <p>
        <strong>İstisna:</strong> Mesafeli Sözleşmeler Yönetmeliği&apos;nin 15
        inci maddesi uyarınca, tüketicinin onayı ile ifasına başlanan
        hizmetlere ilişkin sözleşmelerde ve elektronik ortamda anında ifa
        edilen gayrimaddi mallara ilişkin sözleşmelerde cayma hakkı
        kullanılamaz. Sözleşme konusu hizmet dijitaldir ve ödeme onayıyla
        birlikte Alıcı&apos;nın hesabına anında tanımlanır; Alıcı, ödeme
        adımında hizmetin ifasına derhal başlanmasını onayladığını ve bu
        onayla birlikte cayma hakkını kaybettiğini kabul eder. Bu nedenle
        satın alma sonrasında cayma hakkı kullanılamaz ve iade yapılmaz.
      </p>

      <h2>7. İptal</h2>
      <ul>
        <li>
          Alıcı, aboneliğini panel üzerinden dilediği an iptal edebilir.
          İptal, bir sonraki dönemin tahsilatını durdurur; ödemesi yapılmış
          cari dönem sonuna kadar kullanım hakkı devam eder ve dönem sonunda
          abonelik <strong>otomatik olarak yenilenmez</strong>.
        </li>
        <li>
          Zaten tahsil edilmiş tutarlar için, kullanım durumu ne olursa olsun
          iade yapılmaz.
        </li>
        <li>
          Ek paket kredileri de aynı kurala tabidir: krediler hesapta
          kullanılana kadar geçerliliğini korur, ancak satın alma sonrası
          iade yapılmaz.
        </li>
        <li>
          İptal ve diğer talepler{" "}
          <Link href="/panel/oneri">Bize Yazın</Link>{" "}
          sayfasından iletilebilir.
        </li>
      </ul>

      <h2>8. Uyuşmazlıkların Çözümü</h2>
      <p>
        İşbu Sözleşme&apos;den doğan uyuşmazlıklarda, Ticaret Bakanlığı&apos;nca
        her yıl ilan edilen parasal sınırlar dahilinde Alıcı&apos;nın veya
        Satıcı&apos;nın yerleşim yerindeki <strong>Tüketici Hakem Heyetleri</strong>,
        bu sınırları aşan uyuşmazlıklarda ise <strong>Tüketici Mahkemeleri</strong>{" "}
        yetkilidir. Alıcı, şikayet ve itirazlarını Tüketici Bilgi Sistemi (TÜBİS)
        üzerinden de iletebilir.
      </p>

      <h2>9. Yürürlük</h2>
      <p>
        Alıcı, ödeme ekranında işbu Sözleşme&apos;yi ve ön bilgilendirmeyi
        okuduğunu ve kabul ettiğini elektronik ortamda teyit etmekle Sözleşme
        hükümleriyle bağlıdır. Sözleşme, ödemenin onaylandığı anda kurulmuş ve
        yürürlüğe girmiş sayılır. Sözleşme metni Satıcı tarafından saklanır ve
        Alıcı talep ettiğinde kendisine iletilir.
      </p>

      <h2>İletişim</h2>
      <p>
        <Link href="/panel/oneri">Bize Yazın</Link>
      </p>
      </div>
    </div>
  );
}
