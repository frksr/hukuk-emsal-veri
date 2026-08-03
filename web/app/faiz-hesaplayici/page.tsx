import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { FaizForm } from "./faiz-form";

export const metadata: Metadata = buildMetadata({
  title: "İcra Faiz Hesaplama | Yasal & Ticari Avans Faizi 2026",
  description:
    "İcra takibinde yasal faiz, ticari avans faizi ve TCMB reeskont oranı ile temerrüt faizi hesaplama. İİK cezaevi ve tahsil harçları, vekalet ücreti dahil tam tahsilat tutarı.",
  path: "/faiz-hesaplayici",
  keywords: [
    "icra faiz hesaplama", "yasal faiz oranı 2026", "ticari avans faizi",
    "tcmb reeskont", "iik harçları", "tahsil harcı", "vekalet ücreti hesaplama",
    "temerrüt faizi", "icra takibi faiz",
  ],
});

// Kaynak: 7589 sayılı Kanun / 12. Yargı Paketi m.10 (RG 31.07.2026/33326) —
// 3095 sayılı Kanun m.1'i değiştirdi. Ayrıntı: services/faiz_hesaplayici.py
// FAIZ_DONEMLERI (gün hassasiyetli, kod seviyesinde kaynak atıflı tablo).
const ORAN_SON_KONTROL = "3 Ağustos 2026";

const FAQ = [
  {
    q: "Yasal faiz oranı 2026'da ne kadardır?",
    a: "2026 yılında yasal faiz (3095 sayılı Kanun m.1) tek bir oran değildir: 30 Temmuz 2026'ya kadar yıllık %24, 31 Temmuz 2026'dan itibaren ise yıllık %31 uygulanır (7589 sayılı Kanun, RG 31.07.2026/33326, TCMB reeskont oranının %80'i). Hesaplayıcımız bu kırılımı otomatik uygular; tek dönemi kapsayan hesaplarda tek oran, iki dönemi kapsayan hesaplarda her iki oranın ağırlıklı toplamı gösterilir.",
  },
  {
    q: "Ticari faiz ile yasal faiz arasındaki fark nedir?",
    a: "Tacirler arası ticari işlerde TCMB'nin ilan ettiği avans/temerrüt faizi (2026'da yıllık %39,75) uygulanır. Mal/hizmet tedarikinde geç ödemede ise TTK 1530'a göre ayrı bir oran (2026'da yıllık %43) geçerlidir. Ticari olmayan adi alacaklarda 3095 sayılı Kanun m.1 yasal faizi (31 Temmuz 2026'dan itibaren %31) esas alınır.",
  },
  {
    q: "İcra takibinde cezaevi harcı nasıl hesaplanır?",
    a: "Cezaevi harcı, alacağın (anapara + faiz) toplam tutarı üzerinden %2 oranında hesaplanır ve tahsil edilir.",
  },
  {
    q: "Bu oranların kaynağı ve son kontrol tarihi nedir?",
    a: "Oranlar 7589 sayılı Kanun (RG 31.07.2026/33326), 8485 sayılı Cumhurbaşkanı Kararı (RG 21.05.2024/32552), TCMB'nin reeskont/avans ilanları ve TTK 1530 tebliği (RG 02.01.2026/33125) esas alınarak kod seviyesinde tarihli olarak tutulur ve avukat/editör kontrolünden geçirilir. Son kontrol: " + ORAN_SON_KONTROL + ". Kesin hesap için mahkeme/icra müdürlüğü değerlendirmesi ve avukat kontrolü önerilir.",
  },
];

const ONCEKI_ORANLAR = [
  { donem: "1 Ocak 2006 – 31 Mayıs 2024", yasal: "%9", kaynak: "3095 s. Kanun (eski m.1)" },
  { donem: "1 Haziran 2024 – 30 Temmuz 2026", yasal: "%24", kaynak: "8485 s. CB Kararı, RG 21.05.2024/32552" },
  { donem: "31 Temmuz 2026 – (güncel)", yasal: "%31", kaynak: "7589 s. Kanun, RG 31.07.2026/33326" },
];

export default function FaizPage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "Faiz Hesaplayıcı", url: "/faiz-hesaplayici" }])} />
      <JsonLd data={faqJsonLd(FAQ)} />
      <div className="container py-10 max-w-6xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>Faiz Hesaplayıcı</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Faiz & Tahsilat Hesaplayıcı</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          İcra takibinde anapara, temerrüt tarihi ve faiz türünü girin; sistem yıllık bazda faizi, İİK
          cezaevi ve tahsil harçlarını, vekalet ücretini ve toplam alacağı hesaplasın.
        </p>
        <FaizForm />

        <section className="mt-10 rounded-lg border bg-muted/30 p-5 text-sm">
          <p className="font-medium mb-1">Kaynak ve son kontrol</p>
          <p className="text-muted-foreground">
            Bu sayfadaki oranlar 7589 sayılı Kanun (12. Yargı Paketi, RG 31.07.2026/33326),
            8485 sayılı Cumhurbaşkanı Kararı, TCMB reeskont/avans ilanları ve TTK 1530
            tebliği esas alınarak günlük hassasiyette hesaplanır. Son kontrol:{" "}
            <strong>{ORAN_SON_KONTROL}</strong>. Hesaplama tahmini niteliktedir; kesin tutar
            için avukat/muhasebeci kontrolü önerilir.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[420px] text-sm">
              <thead className="text-left text-muted-foreground border-b">
                <tr><th className="pb-2">Dönem (yasal faiz)</th><th>Oran</th><th>Dayanak</th></tr>
              </thead>
              <tbody>
                {ONCEKI_ORANLAR.map((o) => (
                  <tr key={o.donem} className="border-b last:border-0">
                    <td className="py-2">{o.donem}</td>
                    <td>{o.yasal}</td>
                    <td className="text-muted-foreground">{o.kaynak}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-10 prose prose-sm max-w-none">
          <h2 className="text-2xl font-bold mb-4">Sıkça Sorulan Sorular</h2>
          <div className="space-y-4">
            {FAQ.map((f, i) => (
              <details key={i} className="rounded-lg border bg-card p-5">
                <summary className="cursor-pointer font-semibold">{f.q}</summary>
                <p className="mt-3 text-muted-foreground">{f.a}</p>
              </details>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
