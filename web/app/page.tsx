import Link from "next/link";
import type { Metadata } from "next";
import {
  Search,
  FileText,
  FileSearch,
  Calculator,
  Clock,
  Mail,
  TrendingUp,
  Shield,
  ScrollText,
  ArrowRight,
  CheckCircle2,
  Sparkles,
  Database,
  BookOpen,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { buildMetadata, buildFaqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { cn } from "@/lib/utils";

export const metadata: Metadata = buildMetadata({
  // Baş anahtar kelime ("emsal karar arama") title başında; <=60 karakter
  // (SERP'te kesilmesin — SEO_ANALIZ B8).
  title: "Emsal Karar Arama | Yargıtay-Danıştay Yapay Zeka Asistanı",
  description:
    "Yargıtay, Danıştay ve AİHM emsal kararları arasında Yapay Zeka destekli arama. İcra takibi, tahsilat, ihtarname ve faiz hesaplama için Türk hukukuna özel asistan.",
  path: "/",
  keywords: [
    "yargıtay kararları",
    "danıştay kararları",
    "emsal karar arama",
    "icra takibi",
    "tahsilat hukuku",
    "ihtarname örneği",
    "dilekçe örneği",
    "icra faiz hesaplama",
    "yasal faiz oranı 2026",
    "Yapay Zeka hukuk asistanı",
  ],
});

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";

const websiteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "Hukukçu Yapay Zekası",
  alternateName: "Emsal Karar Arama",
  url: SITE_URL,
  inLanguage: "tr-TR",
  description:
    "Türk hukuk sisteminde Yargıtay, Danıştay ve AİHM emsal kararlarını Yapay Zeka ile arayın; dilekçe, ihtarname ve faiz hesaplama araçları.",
  potentialAction: {
    "@type": "SearchAction",
    target: {
      "@type": "EntryPoint",
      urlTemplate: `${SITE_URL}/emsal-arama?q={search_term_string}`,
    },
    "query-input": "required name=search_term_string",
  },
};

const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Hukukçu Yapay Zekası",
  alternateName: "Emsal Karar Arama",
  url: SITE_URL,
  logo: `${SITE_URL}/logo.png`,
  description:
    "İcra ve tahsilat hukuku odaklı Yapay Zeka destekli emsal karar arama platformu.",
  // sameAs yalnızca DOĞRULANMIŞ profillerle doldurulmalı. Var olmayan profillere
  // işaret etmek zayıf/negatif entity sinyali verir; profiller açılınca eklenir.
  // (SEO_ANALIZ B5)
};

type Feature = {
  icon: typeof Search;
  title: string;
  description: string;
  href: string;
  badge?: string;
};

const features: Feature[] = [
  {
    icon: Search,
    title: "Emsal Karar Arama",
    description:
      "Yargıtay, Danıştay ve AİHM kararları arasında doğal dilde arama yapın. İcra, tahsilat ve ihtar konularında uyumlu emsalleri saniyeler içinde bulun.",
    href: "/emsal-arama",
    badge: "En çok kullanılan",
  },
  {
    icon: FileText,
    title: "Emsal-Bağlamlı Dilekçe",
    description:
      "Davanızı anlatın, Yapay Zeka ilgili Yargıtay emsallerine atıfla profesyonel dilekçe taslağı hazırlasın. İtirazın iptali, menfi tespit, ihalenin feshi destekli.",
    href: "/dilekce",
  },
  {
    icon: FileSearch,
    title: "Karar Özetleyici",
    description:
      "Uzun karar metinlerini saniyeler içinde özetleyin. Hüküm fıkrası, gerekçe ve atıflar otomatik çıkarılır.",
    href: "/karar-ozet",
  },
  {
    icon: Calculator,
    title: "Faiz & Tahsilat Hesaplayıcı",
    description:
      "Yasal faiz, ticari avans faizi, TCMB reeskont oranları ile icra takibinde tam tahsilat tutarını hesaplayın. İİK harçları ve vekalet ücreti dahildir.",
    href: "/faiz-hesaplayici",
  },
  {
    icon: Clock,
    title: "Zamanaşımı Hesaplayıcı",
    description:
      "Alacak türüne göre zamanaşımı süresini, kesilme ve durma hallerini hesaplayın. TBK ve TTK hükümleri uyumlu.",
    href: "/zamanasimi",
  },
  {
    icon: Mail,
    title: "İhtarname Üretici",
    description:
      "Noter onaylı ihtarname taslağını dakikalar içinde hazırlayın. Tahsilat, fesih ve temerrüt ihtarları için hazır şablonlar.",
    href: "/ihtarname",
  },
  {
    icon: TrendingUp,
    title: "Karar Trend Paneli",
    description:
      "Belirli konularda Yargıtay içtihat eğilimlerini görselleştirin. Daire bazlı kabul/red oranları ve son güncellemeler.",
    href: "/trend",
  },
  {
    icon: Shield,
    title: "Karşı Argüman Öngörüsü",
    description:
      "Dilekçenize karşı tarafın olası savunmalarını Yapay Zeka ile öngörün, hazırlığınızı güçlendirin.",
    href: "/karsi-argument",
  },
  {
    icon: ScrollText,
    title: "KVKK Uyum Checklist",
    description:
      "Sektör ve veri türlerinize göre KVKK uyum maddelerinizi çıkarın; uyum skorunuzu görün.",
    href: "/kvkk",
  },
  {
    icon: ScrollText,
    title: "Sözleşme Analizi",
    description:
      "Sözleşmelerinizi madde madde risk analizinden geçirin; eksik ve riskli maddeleri tespit edin.",
    href: "/sozlesme-analizi",
  },
];

const trustedItems = [
  { value: "10.000+", label: "Emsal karar" },
  { value: "Yargıtay", label: "12. Hukuk Dairesi" },
  { value: "Danıştay", label: "İdari yargı kararları" },
  { value: "AİHM", label: "HUDOC veritabanı" },
];

const howItWorks = [
  {
    step: "01",
    title: "Sorunuzu yazın",
    description:
      "Doğal dilde hukuki sorunuzu veya olay özetinizi girin. Hukuk terminolojisi gerekmez.",
    icon: Sparkles,
  },
  {
    step: "02",
    title: "Yapay Zeka emsallere bakar",
    description:
      "Sistem, vektör arama ile 10.000+ Yargıtay, Danıştay ve AİHM kararını analiz eder.",
    icon: Database,
  },
  {
    step: "03",
    title: "Sonuç + atıflar",
    description:
      "İlgili emsaller, atıflar ve hukuki gerekçelerle birlikte yapılandırılmış cevap sunulur.",
    icon: CheckCircle2,
  },
];

const dataSources = [
  {
    name: "Yargıtay Kararları",
    description:
      "Hukuk ve Ceza Genel Kurulu, daireler bazında güncel içtihatlar. Özellikle 12. Hukuk Dairesi (icra-iflas) ve 8. Hukuk Dairesi (icra hukuku) odaklı.",
    icon: BookOpen,
  },
  {
    name: "Danıştay Kararları",
    description:
      "İdari yargı, vergi uyuşmazlıkları ve kamu hukuku alanında daire ve İçtihatları Birleştirme Kurulu kararları.",
    icon: BookOpen,
  },
  {
    name: "AİHM (HUDOC)",
    description:
      "Avrupa İnsan Hakları Mahkemesi'nin Türkiye ile ilgili kararları, mülkiyet ve adil yargılanma hakkı odaklı içtihatlar.",
    icon: BookOpen,
  },
];

const faqs = [
  {
    q: "Yargıtay 12. Hukuk Dairesi kararları nasıl bulunur?",
    a: "Emsal Karar Arama sayfasında konunuzu doğal dilde yazıp filtre olarak 'Yargıtay 12. HD' seçmeniz yeterli. Sistem icra-iflas ile ilgili tüm güncel kararları benzerlik skoruna göre sıralar. Esas/karar numarası, tarih ve hüküm özeti birlikte sunulur.",
  },
  {
    q: "İcra takibinde tahsilat faizi nasıl hesaplanır?",
    a: "İcra takibinde uygulanan faiz; alacağın türüne göre yasal faiz, ticari avans faizi veya TCMB reeskont oranı olabilir. Faiz & Tahsilat Hesaplayıcı aracımız; anapara, temerrüt tarihi ve vade tarihini girdiğinizde yıllık değişen oranları otomatik uygular, İİK harçları ile vekalet ücretini de ekleyerek toplam tahsilat tutarını verir.",
  },
  {
    q: "İhtarname örneği nasıl hazırlanır?",
    a: "İhtarname Üretici aracımız; tahsilat, kira fesih, temerrüt ve sözleşmeden dönme senaryoları için noter onayına hazır şablonlar üretir. Tarafların bilgilerini ve talebinizi girmeniz yeterlidir; sistem TBK md. 117 ve ilgili mevzuata atıfla taslağı oluşturur.",
  },
  {
    q: "2026 yılı yasal faiz oranı nedir?",
    a: "Yasal faiz oranı, 3095 sayılı Kanun çerçevesinde Cumhurbaşkanlığı kararıyla belirlenir ve dönemlere göre değişir. Hesaplayıcımız güncel resmi oranları otomatik olarak uygular; geçmiş dönem hesapları için tarih aralığına göre değişen oranları doğru biçimde dikkate alır.",
  },
  {
    q: "Yapay Zeka ile hazırlanan dilekçe avukat denetimi gerektirir mi?",
    a: "Evet. Platform; emsal karar atıflarıyla zenginleştirilmiş bir taslak hazırlar fakat bu içerik hukuki danışmanlık niteliği taşımaz. Mahkemeye sunulmadan önce mutlaka bir avukatın denetiminden geçirilmesini öneririz.",
  },
  {
    q: "Emsal karar veritabanı ne sıklıkla güncellenir?",
    a: "Yargıtay ve Danıştay kararları haftalık, AİHM (HUDOC) içeriği ise aylık olarak güncellenir. Karar Trend Paneli üzerinden son eklenen içtihatları görebilir, ilgilendiğiniz konularda bildirim alabilirsiniz.",
  },
  {
    q: "Menfi tespit davası dilekçesi hazırlanır mı?",
    a: "Evet. Dilekçe üretici aracımızda 'Menfi Tespit' türünü seçerek davaya konu olay özetini girdiğinizde, sistem Yargıtay 19. ve 12. HD emsallerine atıfla menfi tespit dilekçe taslağını hazırlar.",
  },
  {
    q: "Zamanaşımı süreleri nasıl hesaplanır?",
    a: "Zamanaşımı Hesaplayıcı; alacak türüne (TBK md. 146, 147, TTK md. 749 vb.) göre süre, kesilme halleri ve duran süreleri otomatik dikkate alır. Genel zamanaşımı 10 yıl, dönemsel edimler 5 yıl olarak öntanımlıdır.",
  },
];

export default function HomePage() {
  return (
    <>
      <JsonLd data={websiteJsonLd} />
      <JsonLd data={organizationJsonLd} />
      {/* SSS rich result — sayfadaki 8 soruyu FAQPage schema'sına bağla (B4) */}
      <JsonLd
        data={buildFaqJsonLd(
          faqs.map((f) => ({ question: f.q, answer: f.a }))
        )}
      />

      <main className="flex flex-col">
        {/* HERO */}
        <section
          aria-labelledby="hero-heading"
          className="relative overflow-hidden border-b bg-gradient-to-b from-secondary/60 to-background"
        >
          <div className="mx-auto flex max-w-6xl flex-col items-center px-4 py-20 text-center sm:py-28">
            <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-1.5 text-sm font-medium text-foreground/80 shadow-sm">
              <Sparkles className="h-4 w-4 text-accent" aria-hidden />
              İcra ve Tahsilat Hukukuna Özel Yapay Zeka
            </span>
            <h1
              id="hero-heading"
              className="max-w-4xl text-4xl font-bold tracking-tight text-foreground sm:text-5xl md:text-6xl"
            >
              İcra ve Tahsilat Hukukunun En İyisiyle Çalışıyorsunuz
            </h1>
            <p className="mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">
              10.000&apos;i aşkın Yargıtay ve Danıştay kararıyla oluşturduğumuz
              emsal arşivi ve Yapay Zeka desteğiyle, alanında fark yaratıyoruz.
            </p>
            <div className="mt-10 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg" className="text-lg px-8 py-6 font-semibold">
                <Link href="/emsal-arama" aria-label="Emsal karar aramayı başlat">
                  Ücretsiz Dene
                  <ArrowRight className="ml-2 h-5 w-5" aria-hidden />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="text-base">
                <Link href="#nasil-calisir">Nasıl çalışır?</Link>
              </Button>
            </div>

            {/* TRUSTED BY */}
            <div
              aria-label="Veri kaynaklarımız"
              className="mt-16 grid w-full max-w-4xl grid-cols-2 gap-6 border-t pt-10 sm:grid-cols-4"
            >
              {trustedItems.map((item) => (
                <div key={item.label} className="flex flex-col items-center">
                  <span className="text-2xl font-bold text-foreground sm:text-3xl">
                    {item.value}
                  </span>
                  <span className="mt-1 text-sm text-muted-foreground">
                    {item.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ÖZELLİKLER */}
        <section
          aria-labelledby="features-heading"
          className="mx-auto w-full max-w-6xl px-4 py-20"
        >
          <div className="mb-12 text-center">
            <h2
              id="features-heading"
              className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
            >
              Avukatlar için 9 güçlü araç
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              Emsal karar aramadan dilekçe üretimine, faiz hesaplamadan KVKK
              sözleşme analizine kadar pratik avukatlığa özel modüller.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <Card
                  key={feature.href}
                  className="group flex flex-col p-6 transition-shadow hover:shadow-md"
                >
                  <div className="mb-4 flex items-center justify-between">
                    <div
                      className={cn(
                        "flex h-11 w-11 items-center justify-center rounded-lg",
                        "bg-secondary text-secondary-foreground group-hover:bg-primary group-hover:text-primary-foreground",
                        "transition-colors"
                      )}
                      aria-hidden
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    {feature.badge ? (
                      <span className="rounded-full bg-accent/15 px-2.5 py-1 text-xs font-medium text-accent-foreground dark:text-accent">
                        {feature.badge}
                      </span>
                    ) : null}
                  </div>
                  <h3 className="text-lg font-semibold text-foreground">
                    {feature.title}
                  </h3>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                    {feature.description}
                  </p>
                  <Link
                    href={feature.href}
                    className="mt-4 inline-flex items-center text-sm font-medium text-primary hover:underline"
                    aria-label={`${feature.title} sayfasına git`}
                  >
                    Aracı kullan
                    <ArrowRight
                      className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-0.5"
                      aria-hidden
                    />
                  </Link>
                </Card>
              );
            })}
          </div>
        </section>

        {/* NASIL ÇALIŞIR */}
        <section
          id="nasil-calisir"
          aria-labelledby="how-heading"
          className="border-y bg-secondary/40"
        >
          <div className="mx-auto w-full max-w-6xl px-4 py-20">
            <div className="mb-12 text-center">
              <h2
                id="how-heading"
                className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
              >
                Nasıl çalışır?
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
                3 adımda Türk hukukunda emsal karar bulun ve dilekçenize atıfla
                hazırlayın.
              </p>
            </div>

            <ol className="grid grid-cols-1 gap-8 md:grid-cols-3">
              {howItWorks.map((step) => {
                const Icon = step.icon;
                return (
                  <li key={step.step} className="relative">
                    <Card className="h-full p-6">
                      <div className="mb-4 flex items-center gap-3">
                        <span className="text-2xl font-bold text-muted-foreground/50">
                          {step.step}
                        </span>
                        <Icon
                          className="h-6 w-6 text-primary"
                          aria-hidden
                        />
                      </div>
                      <h3 className="text-lg font-semibold text-foreground">
                        {step.title}
                      </h3>
                      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        {step.description}
                      </p>
                    </Card>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>

        {/* ORTA CTA */}
        <section aria-label="Hemen başla" className="mx-auto w-full max-w-4xl px-4 pb-6 pt-2 text-center">
          <Button asChild size="lg" className="text-lg px-8 py-6 font-semibold">
            <Link href="/emsal-arama" aria-label="Emsal karar aramayı başlat">
              Ücretsiz Dene
              <ArrowRight className="ml-2 h-5 w-5" aria-hidden />
            </Link>
          </Button>
        </section>

        {/* VERİ KAYNAKLARI */}
        <section
          aria-labelledby="sources-heading"
          className="mx-auto w-full max-w-6xl px-4 py-20"
        >
          <div className="mb-12 text-center">
            <h2
              id="sources-heading"
              className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
            >
              Güvenilir veri kaynakları
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              Sadece resmi yargı veritabanlarından beslenen güncel içtihat
              havuzu.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {dataSources.map((source) => {
              const Icon = source.icon;
              return (
                <Card key={source.name} className="p-6 transition-shadow hover:shadow-md">
                  <Icon
                    className="h-8 w-8 text-primary"
                    aria-hidden
                  />
                  <h3 className="mt-4 text-lg font-semibold text-foreground">
                    {source.name}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {source.description}
                  </p>
                </Card>
              );
            })}
          </div>
        </section>

        {/* FAQ */}
        <section
          aria-labelledby="faq-heading"
          className="border-y bg-secondary/40"
        >
          <div className="mx-auto w-full max-w-3xl px-4 py-20">
            <div className="mb-12 text-center">
              <h2
                id="faq-heading"
                className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
              >
                Sıkça sorulan sorular
              </h2>
              <p className="mt-4 text-lg text-muted-foreground">
                Türk hukukunda emsal karar arama, dilekçe ve faiz hesaplama
                konularında yanıtlar.
              </p>
            </div>

            <div className="space-y-3">
              {faqs.map((item, idx) => (
                <details
                  key={item.q}
                  className="group rounded-lg border bg-card p-5 transition-shadow hover:shadow-sm [&_summary::-webkit-details-marker]:hidden"
                  {...(idx === 0 ? { open: true } : {})}
                >
                  <summary className="flex cursor-pointer items-center justify-between text-base font-semibold text-foreground">
                    <h3 className="pr-4">{item.q}</h3>
                    <ArrowRight
                      className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90"
                      aria-hidden
                    />
                  </summary>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {item.a}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* CTA FOOTER */}
        <section
          aria-labelledby="cta-heading"
          className="bg-primary-900 text-white dark:bg-primary-950"
        >
          <div className="mx-auto flex w-full max-w-4xl flex-col items-center px-4 py-20 text-center">
            <h2
              id="cta-heading"
              className="text-3xl font-bold tracking-tight sm:text-4xl"
            >
              Hukuk pratiğinizi Yapay Zeka ile hızlandırın
            </h2>
            <p className="mt-4 max-w-2xl text-lg text-slate-300 dark:text-slate-400">
              Ücretsiz hesap oluşturun, ilk 50 emsal karar aramanız bizden.
              Kredi kartı gerekmez.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg" className="text-lg px-8 py-6 font-semibold">
                <Link href="/emsal-arama" aria-label="Emsal karar aramayı başlat">
                  Ücretsiz Dene
                  <ArrowRight className="ml-2 h-5 w-5" aria-hidden />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-slate-700 text-white hover:bg-slate-800"
              >
                <Link href="/emsal-arama">Demoyu gör</Link>
              </Button>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
