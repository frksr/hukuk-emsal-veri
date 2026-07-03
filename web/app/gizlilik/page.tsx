import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Gizlilik Politikası",
  description:
    "Hukuk Emsal KVKK aydınlatma metni: hangi verilerin toplandığı, üçüncü taraflarla (yapay zeka sağlayıcıları, ödeme kuruluşu) paylaşım ve haklarınız.",
  path: "/gizlilik",
});

export default function GizlilikPage() {
  const guncelleme = "3 Temmuz 2026";
  return (
    <div className="container py-10 max-w-3xl prose prose-slate">
      {/*
        SİTE SAHİBİ İÇİN NOT: [ŞİRKET ÜNVANI]/[ADRES] alanlarını doldurun (Mesafeli
        Satış Sözleşmesi'ndeki ile aynı olmalı). Yayına almadan önce metni, özellikle
        "yurt dışına aktarım" ve "veri saklama süreleri" bölümlerini bir avukata/KVKK
        danışmanına inceletin — gerçek saklama sürelerini ve VERBİS kaydınızı buna
        göre netleştirin.
      */}
      <h1>Gizlilik Politikası (KVKK Aydınlatma Metni)</h1>
      <p className="text-sm text-muted-foreground">Son güncelleme: {guncelleme}</p>
      <p>
        İşbu Aydınlatma Metni, 6698 sayılı Kişisel Verilerin Korunması Kanunu
        (&quot;KVKK&quot;) madde 10 uyarınca, veri sorumlusu sıfatıyla{" "}
        <strong>[ŞİRKET ÜNVANI]</strong> (&quot;Hukuk Emsal&quot;,
        &quot;Şirket&quot;) tarafından hukukcuyapayzekasi.com platformu
        (&quot;Platform&quot;) üzerinden işlenen kişisel verileriniz hakkında
        sizi bilgilendirmek amacıyla hazırlanmıştır.
      </p>

      <h2>1. Toplanan Kişisel Veriler</h2>
      <ul>
        <li>
          <strong>Kimlik ve iletişim verileri:</strong> ad-soyad, e-posta
          adresi, (opsiyonel) büro/firma adı.
        </li>
        <li>
          <strong>Hesap ve işlem verileri:</strong> plan/abonelik bilgisi,
          giriş geçmişi, e-posta doğrulama durumu, hesap tercihleri (ör.
          &quot;geçmişi tut&quot; ayarınız).
        </li>
        <li>
          <strong>Kullanım ve içerik verileri:</strong> emsal arama
          sorgularınız, dilekçe/ihtarname/sözleşme analizi gibi araçlara
          girdiğiniz olay anlatımları ve bu araçların ürettiği çıktılar.
          Hesabınızdaki &quot;Geçmişi tut&quot; ayarı{" "}
          <strong>varsayılan olarak açıktır</strong>; açık olduğu sürece bu
          girdi/çıktılar hesabınıza bağlı olarak saklanır ve
          panelinizdeki &quot;Geçmişim&quot; bölümünden erişilebilir. Bu
          ayarı istediğiniz zaman kapatabilir ve geçmiş kayıtlarınızı
          silebilirsiniz (bkz. madde 5).
        </li>
        <li>
          <strong>UYAP/dosya verileri</strong> (yalnızca UYAP entegrasyonlu
          planlarda): yüklediğiniz dava dosyaları ve belgeler, işlenmiş metin
          içerikleriyle birlikte <strong>şifrelenmiş</strong> olarak
          saklanır.
        </li>
        <li>
          <strong>Ödeme ile ilgili sınırlı veriler:</strong> ödeme durumu,
          tutar, plan/paket bilgisi ve fatura numarası. Kart bilgileri ve
          T.C. Kimlik Numarası tarafımızca değil, yalnızca ödeme kuruluşu
          tarafından işlenir (bkz. madde 4).
        </li>
        <li>
          <strong>Teknik veriler:</strong> IP adresi, tarayıcı/işletim
          sistemi bilgisi, oturum çerezleri, anonim kullanım istatistikleri
          (sayfa görüntüleme, özellik kullanım sıklığı).
        </li>
        <li>
          <strong>Pazarlama izni verildiyse:</strong> e-posta ile ürün
          duyurusu/bülten gönderimi için kullanılan iletişim tercihi.
        </li>
      </ul>

      <h2>2. Veri İşleme Amaçları</h2>
      <ul>
        <li>Emsal karar arama, yapay zeka destekli taslak üretimi ve diğer hukuki araçların sunulması,</li>
        <li>Hesabınızın oluşturulması, kimlik doğrulama ve güvenliğinin sağlanması,</li>
        <li>Abonelik ve ödeme süreçlerinin yürütülmesi,</li>
        <li>Hatırlatıcı ve emsal alarmı gibi bildirim tercihlerinizin uygulanması,</li>
        <li>Hizmet kalitesinin ölçülmesi ve iyileştirilmesi (anonim/istatistiksel analiz),</li>
        <li>Yasal yükümlülüklerin (vergi, tüketici mevzuatı, MASAK vb.) yerine getirilmesi,</li>
        <li>Talep ve şikayetlerinizin yanıtlanması (destek hizmeti).</li>
      </ul>

      <h2>3. Hukuki Sebep</h2>
      <p>
        Kişisel verileriniz, KVKK madde 5/2 kapsamında; bir sözleşmenin
        kurulması veya ifasıyla doğrudan ilgili olması (hizmet sunumu, ödeme),
        hukuki yükümlülüğün yerine getirilmesi (fatura, MASAK) ve meşru
        menfaat (hizmet güvenliği, kötüye kullanımın önlenmesi) hukuki
        sebeplerine dayanılarak işlenir. Pazarlama iletişimi gibi açık rıza
        gerektiren işlemler, yalnızca ayrıca verdiğiniz onay üzerine
        yürütülür ve dilediğiniz zaman geri alınabilir.
      </p>

      <h2>4. Ödeme ve Kimlik Bilgileri</h2>
      <p>
        Abonelik ve ek paket ödemeleri, lisanslı ödeme kuruluşu{" "}
        <strong>iyzico</strong> altyapısı üzerinden alınır. Ödeme sırasında
        istenen <strong>T.C. Kimlik Numarası</strong> ve kart bilgileri,
        yasal zorunluluk (MASAK ve 5549 sayılı Kanun) gereği yalnızca iyzico
        tarafından talep edilir ve işlenir. Bu bilgiler{" "}
        <strong>
          tarafımızca hiçbir şekilde saklanmaz, kaydedilmez veya loglanmaz
        </strong>
        ; yalnızca ödeme anında güvenli bağlantı üzerinden doğrudan
        iyzico&apos;ya iletilir. Tarafımızda yalnızca işlem sonucu (ödeme
        durumu, tutar, plan/paket bilgisi) tutulur.
      </p>

      <h2>5. Üçüncü Taraflarla Paylaşım ve Yurt Dışına Aktarım</h2>
      <p>
        Emsal arama sorgularınız ve yapay zeka araçlarına girdiğiniz metinler,
        ilgili çıktıyı üretebilmek amacıyla aşağıdaki yapay zeka
        sağlayıcılarına <strong>yalnızca işleme amacıyla</strong> iletilir:
      </p>
      <ul>
        <li>
          <strong>Google (Gemini API, ABD merkezli):</strong> arama
          sorgularının vektöre çevrilmesi (embedding) ve/veya metin üretimi
          için.
        </li>
        <li>
          <strong>Anthropic (Claude API, ABD merkezli):</strong> dilekçe,
          ihtarname, sözleşme analizi ve benzeri taslak üretimi için.
        </li>
      </ul>
      <p>
        Bu sağlayıcılar verilerinizi kendi model eğitimlerinde kullanmaz
        (API kullanım koşulları bu yöndedir) ve yalnızca isteğinize yanıt
        üretmek için geçici olarak işler. Bu aktarım, KVKK madde 9 anlamında
        <strong> yurt dışına veri aktarımı</strong> teşkil eder; Platform&apos;u
        kullanarak, hizmetin ifası için gerekli olan bu aktarıma açık rızanızı
        vermiş olursunuz. Ayrıca ödeme altyapısı için <strong>iyzico</strong>{" "}
        ve barındırma/altyapı hizmeti için sunucu sağlayıcımızla
        (bulut barındırma) sınırlı, hizmetin ifası için gerekli veriler
        paylaşılır. Kişisel verileriniz, yukarıdakiler dışında, yasal
        zorunluluk olmadıkça üçüncü kişilerle paylaşılmaz veya satılmaz.
      </p>

      <h2>6. Veri Saklama Süreleri</h2>
      <ul>
        <li>
          Hesap bilgileriniz, hesabınız aktif olduğu sürece ve hesap
          kapatıldıktan sonra yasal saklama yükümlülükleriniz (ör. fatura
          kayıtları için Vergi Usul Kanunu&apos;nda öngörülen süreler) saklı
          kalmak kaydıyla makul bir süre daha saklanır.
        </li>
        <li>
          Arama/üretim geçmişiniz, &quot;Geçmişi tut&quot; ayarınız açık
          olduğu sürece hesabınızda tutulur; bu ayarı kapatabilir veya
          panelinizdeki &quot;Geçmişim&quot; bölümünden dilediğiniz kaydı
          tek tek ya da toplu olarak silebilirsiniz.
        </li>
        <li>
          Hesabınızın silinmesini talep etmeniz halinde, yasal saklama
          yükümlülüğü bulunmayan kişisel verileriniz makul bir süre içinde
          silinir veya anonim hale getirilir.
        </li>
      </ul>

      <h2>7. Veri Güvenliği</h2>
      <p>
        Şifreniz geri döndürülemez biçimde (bcrypt) saklanır. UYAP
        entegrasyonu kapsamında yüklenen dava dosyaları şifreli olarak
        depolanır. Platform&apos;a erişim HTTPS üzerinden şifrelenir.
        Bununla birlikte, internet üzerinden hiçbir iletim veya elektronik
        depolama yönteminin %100 güvenli olduğu garanti edilemez.
      </p>

      <h2>8. Çerezler</h2>
      <p>
        Platform, oturumunuzu açık tutmak (kimlik doğrulama) için zorunlu
        çerezler kullanır. Bu çerezler olmadan giriş yapılı bir şekilde
        Platform&apos;u kullanmak mümkün değildir. Zorunlu olmayan analitik
        çerez kullanımı bulunması halinde, ayrı bir çerez bildirimiyle
        ayrıca bilgilendirilirsiniz.
      </p>

      <h2>9. KVKK Kapsamındaki Haklarınız</h2>
      <p>
        KVKK madde 11 uyarınca veri sorumlusuna başvurarak: kişisel
        verilerinizin işlenip işlenmediğini öğrenme, işlenmişse buna ilişkin
        bilgi talep etme, işlenme amacını ve amacına uygun kullanılıp
        kullanılmadığını öğrenme, yurt içinde/yurt dışında aktarıldığı
        üçüncü kişileri bilme, eksik/yanlış işlenmişse düzeltilmesini
        isteme, KVKK madde 7&apos;deki şartlar oluştuğunda silinmesini/yok
        edilmesini isteme, işlenen verilerin münhasıran otomatik sistemler
        vasıtasıyla analiz edilmesi suretiyle aleyhinize bir sonucun
        ortaya çıkmasına itiraz etme ve kanuna aykırı işleme sebebiyle
        zarara uğramanız halinde zararın giderilmesini talep etme
        haklarına sahipsiniz.
      </p>

      <h2>10. Başvuru Yöntemi</h2>
      <p>
        Yukarıdaki haklarınızı kullanmak için kimliğinizi tevsik edici
        belgelerle birlikte{" "}
        <a href="mailto:kvkk@hukukcuyapayzekasi.com">
          kvkk@hukukcuyapayzekasi.com
        </a>{" "}
        adresine yazılı olarak başvurabilirsiniz. Talebiniz, niteliğine göre
        en geç 30 gün içinde ücretsiz olarak sonuçlandırılır.
      </p>

      <h2>11. Değişiklikler</h2>
      <p>
        İşbu Aydınlatma Metni, mevzuat değişiklikleri veya hizmet
        kapsamındaki güncellemeler nedeniyle zaman zaman revize edilebilir;
        güncel sürüm her zaman bu sayfada yayınlanır.
      </p>
    </div>
  );
}
