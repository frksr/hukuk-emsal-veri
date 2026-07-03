import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Kullanım Şartları",
  description:
    "Hukuk Emsal platformunun kullanım şartları: hesap, abonelik, fikri mülkiyet, sorumluluk sınırlaması ve fesih hükümleri.",
  path: "/kullanim-sartlari",
});

export default function KullanimPage() {
  const guncelleme = "3 Temmuz 2026";
  return (
    <div className="container py-10 max-w-3xl prose prose-slate">
      {/*
        SİTE SAHİBİ İÇİN NOT: Şirket ünvanı/adres bilgilerini Mesafeli Satış
        Sözleşmesi'ndeki ile tutarlı tutun. Yayına almadan önce metnin tamamını
        bir avukata inceletin; özellikle sorumluluk sınırlaması ve fesih
        maddeleri işkolunuza göre uyarlanmalıdır.
      */}
      <h1>Kullanım Şartları</h1>
      <p className="text-sm text-muted-foreground">Son güncelleme: {guncelleme}</p>
      <p>
        İşbu Kullanım Şartları (&quot;Şartlar&quot;), hukukcuyapayzekasi.com
        adresinde yayınlanan Hukuk Emsal platformunu (&quot;Platform&quot;,
        &quot;Hizmet&quot;) kullanan tüm gerçek ve tüzel kişileri
        (&quot;Kullanıcı&quot;) bağlar. Platforma üye olarak, oturum açarak veya
        Platform&apos;u herhangi bir şekilde kullanarak işbu Şartlar&apos;ı
        okuduğunuzu, anladığınızı ve kabul ettiğinizi beyan etmiş sayılırsınız.
        Şartları kabul etmiyorsanız Platform&apos;u kullanmamalısınız.
      </p>

      <h2>1. Hizmetin Niteliği ve Kapsamı</h2>
      <p>
        Hukuk Emsal; Yargıtay, Danıştay ve AİHM emsal kararlarında arama,
        yapay zeka destekli dilekçe/ihtarname/sözleşme analizi taslak üretimi,
        faiz ve zamanaşımı hesaplama, KVKK uyum kontrol listesi ve benzeri
        hukuki üretkenlik araçları sunan bir <strong>yazılım hizmetidir
        (SaaS)</strong>.
      </p>
      <p>
        <strong>Platform bir avukatlık bürosu değildir ve hukuki danışmanlık
        hizmeti vermez.</strong> Yapay zeka tarafından üretilen tüm taslaklar,
        analizler, özetler ve hesaplamalar yalnızca bilgilendirme ve taslak
        oluşturma amaçlıdır; resmi bir sürece (mahkeme, icra dairesi, noter,
        idare vb.) sunulmadan önce mutlaka yetkili bir avukat veya ilgili
        meslek mensubu tarafından incelenmeli ve onaylanmalıdır. Ayrıntılar
        için <a href="/yasal-uyari">Yasal Uyarı</a> sayfasına bakınız.
      </p>

      <h2>2. Hesap Oluşturma ve Uygunluk</h2>
      <ul>
        <li>
          Platform&apos;u kullanabilmek için 18 yaşından büyük olmanız ve
          Türk hukuku uyarınca sözleşme ehliyetine sahip olmanız gerekir.
        </li>
        <li>
          Kayıt sırasında verdiğiniz bilgilerin (ad-soyad, e-posta) doğru ve
          güncel olmasından siz sorumlusunuz. Hesabınız, e-posta adresinize
          gönderilen kod ile doğrulanana kadar Platform&apos;un bazı
          bölümlerine erişemeyebilir.
        </li>
        <li>
          Hesap şifrenizin gizliliğinden ve hesabınız üzerinden
          gerçekleştirilen tüm işlemlerden siz sorumlusunuz. Hesabınızın
          yetkisiz kullanıldığını fark ederseniz derhal{" "}
          <a href="mailto:destek@hukukcuyapayzekasi.com">
            destek@hukukcuyapayzekasi.com
          </a>{" "}
          adresine bildiriniz.
        </li>
        <li>
          Ekip (Team) planlarında, tenant/çalışma alanı sahibi (owner),
          davet ettiği üyelerin Platform&apos;u işbu Şartlar&apos;a uygun
          kullanmasından da sorumludur.
        </li>
      </ul>

      <h2>3. Kullanıcı Yükümlülükleri ve Yasak Kullanımlar</h2>
      <p>Platform&apos;u kullanırken aşağıdakileri kabul edersiniz:</p>
      <ul>
        <li>Platform&apos;u yalnızca yasalara uygun amaçlarla kullanmak.</li>
        <li>
          Yapay zeka tarafından üretilen içerikleri, profesyonel bir hukuki
          inceleme yapılmadan resmi bir sürece (dava, icra takibi, ihtar,
          sözleşme imzası vb.) sokmamak.
        </li>
        <li>
          Platform&apos;a erişimi otomatikleştirilmiş araçlarla (bot, scraper)
          izinsiz şekilde yoğunlaştırmamak, hizmetin işleyişini bozmaya
          yönelik girişimlerde bulunmamak (güvenlik açığı istismarı, aşırı
          yük bindirme, yetkisiz erişim denemesi vb.).
        </li>
        <li>
          Başkasına ait kişisel verileri veya gizli/telif hakkı korunan
          içerikleri yetkisiz şekilde Platform&apos;a yüklememek veya işbu
          Platform aracılığıyla üçüncü kişilerle paylaşmamak.
        </li>
        <li>
          Bir plan veya ek paket kapsamında tanınan kullanım haklarını,
          hesap paylaşımı veya benzeri yollarla amacı dışında/plan limitlerini
          aşacak şekilde devretmemek.
        </li>
      </ul>
      <p>
        İşbu maddenin ihlali halinde Satıcı, önceden bildirimde bulunmaksızın
        ilgili hesabı askıya alma veya kapatma hakkını saklı tutar (bkz. madde
        8).
      </p>

      <h2>4. Abonelik, Ücretlendirme ve Fesih</h2>
      <p>
        Ücretli planlar ve ek paketler{" "}
        <a href="/fiyatlandirma">Fiyatlandırma</a> sayfasında belirtilen
        koşullarla, <a href="/mesafeli-satis">Mesafeli Satış Sözleşmesi</a>{" "}
        hükümleri çerçevesinde satın alınır. Cayma hakkı, iptal ve iade
        koşulları için <a href="/iade-politikasi">Cayma ve İade Politikası</a>{" "}
        sayfasına bakınız. Özetle:
      </p>
      <ul>
        <li>
          Aylık abonelikler, iptal edilmediği sürece her ay otomatik olarak
          yenilenir ve kayıtlı ödeme yöntemi üzerinden tahsilat yapılır.
        </li>
        <li>
          Aboneliğinizi dilediğiniz zaman panel üzerinden iptal
          edebilirsiniz; iptal, yalnızca bir sonraki yenileme dönemindeki
          tahsilatı durdurur. <strong>Cari (ödemesi yapılmış) dönem için
          kullanım hakkınız dönem sonuna kadar devam eder</strong>, dönem
          sonunda erişiminiz otomatik olarak ücretsiz plan koşullarına döner
          veya kısıtlanır.
        </li>
        <li>
          Kullanılmış veya kısmen kullanılmış dönemler/kredi paketleri için
          ücret iadesi yapılmaz; istisnalar için Cayma ve İade Politikası
          sayfasındaki 14 günlük yasal cayma hakkı bölümüne bakınız.
        </li>
        <li>
          Yenileme tahsilatının başarısız olması halinde ücretli özellikleriniz
          geçici olarak askıya alınabilir; ödeme yönteminizi güncelleyerek
          erişiminizi yeniden açabilirsiniz.
        </li>
      </ul>

      <h2>5. Fikri Mülkiyet</h2>
      <p>
        Platform üzerindeki yazılım, tasarım, marka, logo ve arayüz unsurları
        Hukuk Emsal&apos;e aittir ve fikri mülkiyet mevzuatı ile korunur.
        Resmi kaynaklardan (Yargıtay, Danıştay, HUDOC/AİHM) derlenen emsal
        karar metinleri kamuya açık kaynaklardır; Platform, bu kararların
        aranabilirliğini ve özetlenmesini sağlayan bir katma değer hizmeti
        sunar. Yapay zeka tarafından sizin girdileriniz temel alınarak
        üretilen taslak metinler (dilekçe, ihtarname, sözleşme analizi vb.)
        üzerindeki kullanım hakkı size aittir; Platform bu taslakları kendi
        adına yayınlama veya üçüncü kişilerle paylaşma hakkını kullanmaz.
      </p>

      <h2>6. Kullanıcı İçeriği ve Verileriniz</h2>
      <p>
        Platform&apos;a girdiğiniz olay anlatımları, yüklediğiniz belgeler
        (UYAP entegrasyonu dahil) ve bunlardan üretilen taslaklar size aittir.
        Bu içerikleri, size hizmet sunabilmek amacıyla (arama, taslak üretimi,
        depolama, geçmişinizde gösterme) işleme ve ilgili yapay zeka
        sağlayıcılarına (bkz. <a href="/gizlilik">Gizlilik Politikası</a>)
        iletme hakkını Platform&apos;a tanırsınız. Bu yetki, yalnızca size
        hizmet sunmakla sınırlıdır ve içerikleriniz üzerindeki mülkiyet
        hakkınızı ortadan kaldırmaz.
      </p>

      <h2>7. Sorumluluğun Sınırlandırılması</h2>
      <ul>
        <li>
          Platform &quot;olduğu gibi&quot; (as-is) sunulur; kesintisiz,
          hatasız çalışacağına veya belirli bir amaca uygunluğuna dair açık
          ya da zımni bir garanti verilmez.
        </li>
        <li>
          Yapay zeka tarafından üretilen içeriklerin hukuki doğruluğu, güncel
          mevzuata uygunluğu veya belirli bir somut olaya uygunluğu garanti
          edilmez; nihai sorumluluk, içeriği kullanan kullanıcıya/meslek
          mensubuna aittir.
        </li>
        <li>
          Yürürlükteki mevzuatın izin verdiği azami ölçüde, Hukuk Emsal;
          Platform&apos;un kullanımından veya kullanılamamasından
          kaynaklanan dolaylı, arızi veya sonuç itibarıyla ortaya çıkan
          zararlardan (kâr kaybı, veri kaybı, itibar kaybı dahil) sorumlu
          tutulamaz. Herhangi bir sorumluluk halinde, Hukuk Emsal&apos;in
          toplam sorumluluğu, ilgili kullanıcının son 12 ayda ödediği
          abonelik bedeli ile sınırlıdır.
        </li>
        <li>
          Bu sınırlamalar, Hukuk Emsal&apos;in kasıt veya ağır ihmalinden
          kaynaklanan sorumluluğu ya da tüketici mevzuatının emredici
          hükümlerini ortadan kaldırmaz.
        </li>
      </ul>

      <h2>8. Hesabın Askıya Alınması ve Fesih</h2>
      <p>
        İşbu Şartlar&apos;ın veya yürürlükteki mevzuatın ihlali halinde,
        Hukuk Emsal ilgili hesabı uyarı vererek veya vermeksizin askıya
        alabilir ya da kapatabilir. Kullanıcı, hesabını dilediği zaman panel
        üzerinden veya destek ekibine bildirimde bulunarak kapatabilir; ücret
        iadesi için madde 4 ve Cayma ve İade Politikası geçerlidir. Hesap
        kapatıldığında, kişisel verileriniz KVKK ve yasal saklama süreleri
        çerçevesinde işlenir/silinir (bkz. Gizlilik Politikası).
      </p>

      <h2>9. Hizmet Değişiklikleri</h2>
      <p>
        Hizmet kapsamı, plan limitleri ve özellikleri, hizmet kalitesini
        artırmak veya mevzuata uyum sağlamak amacıyla zaman zaman
        güncellenebilir. Kullanıcı aleyhine önemli değişiklikler (fiyat
        artışı, temel özelliklerin kaldırılması vb.), yürürlüğe girmeden
        makul bir süre önce e-posta veya site içi bildirimle duyurulur.
      </p>

      <h2>10. Uygulanacak Hukuk ve Yetkili Mahkeme</h2>
      <p>
        İşbu Şartlar Türkiye Cumhuriyeti kanunlarına tabidir. İşbu
        Şartlar&apos;dan doğan uyuşmazlıklarda, tüketici işlemlerinde
        Tüketici Hakem Heyetleri/Tüketici Mahkemeleri, ticari işlemlerde ise
        İstanbul (Merkez) Mahkemeleri ve İcra Daireleri yetkilidir.
      </p>

      <h2>11. Şartlarda Değişiklik</h2>
      <p>
        İşbu Şartlar zaman zaman güncellenebilir; güncel sürüm her zaman bu
        sayfada yayınlanır ve yayınlandığı tarihten itibaren geçerli olur.
        Önemli değişikliklerde kullanıcılar ayrıca bilgilendirilir.
      </p>

      <h2>12. İletişim</h2>
      <p>
        Sorularınız için{" "}
        <a href="mailto:info@hukukcuyapayzekasi.com">
          info@hukukcuyapayzekasi.com
        </a>
        , destek talepleri için{" "}
        <a href="mailto:destek@hukukcuyapayzekasi.com">
          destek@hukukcuyapayzekasi.com
        </a>{" "}
        adresine yazabilirsiniz.
      </p>
    </div>
  );
}
