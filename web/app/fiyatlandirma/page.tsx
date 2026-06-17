import type { Metadata } from "next";
import { Check, X } from "lucide-react";

import { Card } from "@/components/ui/card";
import { buildMetadata, buildFaqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { PlanCta } from "@/components/plan-cta";
import { PlanLimitler } from "./plan-limitler";
import { cn } from "@/lib/utils";

export const metadata: Metadata = buildMetadata({
  title: "Fiyatlandırma — Planlar ve Paketler | Hukuk Emsal",
  description:
    "Ücretsiz başlayın; Pro ile sınırsız emsal arama, Yapay Zeka dilekçe ve UYAP dosya asistanı. Avukatlar ve hukuk büroları için aylık abonelik planları.",
  path: "/fiyatlandirma",
  keywords: [
    "hukuk asistanı fiyat",
    "emsal karar arama abonelik",
    "ai dilekçe programı fiyat",
    "hukuk yazılımı fiyatlandırma",
  ],
});

// NOT: emsal arama/dilekçe/özet/sözleşme gibi LİMİT satırları artık statik değil;
// <PlanLimitler tier=.../> ile admin ayarlarından (public /billing/plan-limits)
// dinamik üretilir. Aşağıdaki `features` yalnızca niteliksel (limit-dışı) maddeler.
const PLANS = [
  {
    name: "Ücretsiz",
    tier: "free",
    price: "0",
    period: "",
    tagline: "Bireysel deneme ve hafif kullanım",
    cta: { label: "Ücretsiz Başla", href: "/kayit" },
    highlight: false,
    features: [
      "Faiz + zamanaşımı hesaplayıcı (sınırsız)",
      "Arama geçmişi",
    ],
    missing: ["UYAP dosya asistanı", "Ekip üyeleri"],
  },
  {
    name: "Pro Solo",
    tier: "pro_solo",
    price: "499",
    period: "₺/ay",
    tagline: "Tek avukat — sınırsız araştırma",
    cta: { label: "Pro'ya Geç", href: "/kayit?plan=pro_solo" },
    highlight: true,
    features: [
      "Karşı argüman üretici",
      "Öncelikli işlem kuyruğu",
    ],
    missing: ["UYAP dosya asistanı", "Ekip üyeleri"],
  },
  {
    name: "Pro + UYAP",
    tier: "pro_solo_uyap",
    price: "799",
    period: "₺/ay",
    tagline: "Tek avukat + dosya asistanı",
    cta: { label: "Pro + UYAP Al", href: "/kayit?plan=pro_solo_uyap" },
    highlight: false,
    features: [
      "UYAP dosya yükleme (PDF/DOCX)",
      "Dosya içinde Yapay Zeka soru-cevap",
      "KVKK uyumlu şifreli saklama",
      "Dosya bazlı emsal eşleştirme",
    ],
    missing: ["Ekip üyeleri"],
  },
  {
    name: "Team",
    tier: "team",
    price: "1.499",
    period: "₺/ay",
    tagline: "Hukuk büroları — 5 üyeye kadar",
    cta: { label: "Ekip Planı Al", href: "/kayit?plan=team" },
    highlight: false,
    features: [
      "5 kullanıcı (ek üye eklenebilir)",
      "Ortak çalışma alanı",
      "Kullanım raporları",
      "UYAP seçeneği (+500₺/ay)",
    ],
    missing: [],
  },
];

const FAQS = [
  {
    question: "Ücretsiz plan ne kadar süre geçerli?",
    answer:
      "Süresiz. Kredi kartı gerekmez; aylık limitler dahilinde dilediğiniz kadar kullanın. Limitler her ay (hesabınızı açtığınız günün yıldönümünde) yenilenir.",
  },
  {
    question: "İstediğim zaman iptal edebilir miyim?",
    answer:
      "Evet. Abonelik ayarlarından tek tıkla iptal edersiniz; dönem sonuna kadar erişiminiz sürer, sonraki ay ücret alınmaz.",
  },
  {
    question: "Ödeme nasıl alınıyor, güvenli mi?",
    answer:
      "Ödemeler iyzico altyapısıyla alınır; kart bilgileriniz bizde saklanmaz. Tüm planlar aylık faturalıdır ve e-fatura kesilir.",
  },
  {
    question: "UYAP dosya asistanında verilerim güvende mi?",
    answer:
      "Dosyalarınız tenant bazlı ayrı anahtarlarla şifrelenir (envelope encryption), KVKK kapsamında işlenir ve Yapay Zeka'ya gönderilmeden önce kişisel veriler maskelenir.",
  },
  {
    question: "Yapay Zeka çıktıları hukuki tavsiye midir?",
    answer:
      "Hayır. Üretilen dilekçe, ihtarname ve özetler taslak niteliğindedir; mutlaka avukat kontrolünden geçirilmelidir. Platform hukuki danışmanlık hizmeti vermez.",
  },
  {
    question: "Enterprise / API erişimi var mı?",
    answer:
      "Büyük ekipler ve entegrasyonlar (büro yönetim yazılımları, API erişimi) için satis@hukukcuyapayzekasi.com adresinden bize ulaşın.",
  },
];

export default function FiyatlandirmaPage() {
  return (
    <>
      <JsonLd id="fiyat-faq" data={buildFaqJsonLd(FAQS)} />

      <div className="container py-12 md:py-16">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 bg-primary/10 text-primary text-xs font-semibold px-3 py-1 rounded-full mb-4 uppercase tracking-wide">
            Erken Erişim
          </div>
          <h1 className="text-3xl md:text-4xl font-bold mb-4">
            Seçili avukatlara özel erken erişim
          </h1>
          <p className="text-muted-foreground">
            Hukuk Emsal şu an davetli beta aşamasındadır. Bekleme listesine katılın,
            uygun görülen kullanıcılar öncelikli erişim davetini alacak.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-16">
          {PLANS.map((plan) => (
            <Card
              key={plan.name}
              className={cn(
                "p-6 flex flex-col",
                plan.highlight && "border-primary ring-1 ring-primary shadow-lg"
              )}
            >
              {plan.highlight && (
                <div className="text-xs font-semibold text-primary mb-2 uppercase tracking-wide">
                  En popüler
                </div>
              )}
              <h2 className="text-lg font-bold">{plan.name}</h2>
              <p className="text-sm text-muted-foreground mb-4">{plan.tagline}</p>
              <div className="mb-6">
                <span className="text-sm text-muted-foreground italic">Erken erişim fiyatı açıklanacak</span>
              </div>
              <div className="flex-1 space-y-2">
                {/* Limit satırları — admin ayarlarından dinamik */}
                <PlanLimitler tier={plan.tier} />
                <ul className="space-y-2 text-sm">
                  {plan.features.map((f) => (
                    <li key={f} className="flex gap-2">
                      <Check className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                      <span>{f}</span>
                    </li>
                  ))}
                  {plan.missing.map((f) => (
                    <li key={f} className="flex gap-2 text-muted-foreground/60">
                      <X className="h-4 w-4 shrink-0 mt-0.5" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <PlanCta
                planKey={
                  plan.cta.href.includes("plan=")
                    ? plan.cta.href.split("plan=")[1]
                    : null
                }
                label={plan.cta.label}
                highlight={plan.highlight}
              />
            </Card>
          ))}
        </div>

        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-center mb-8">
            Sık sorulan sorular
          </h2>
          <div className="space-y-6">
            {FAQS.map((faq) => (
              <div key={faq.question}>
                <h3 className="font-semibold mb-1">{faq.question}</h3>
                <p className="text-sm text-muted-foreground">{faq.answer}</p>
              </div>
            ))}
          </div>

          <div className="mt-12 text-center text-sm text-muted-foreground">
            Sorunuz mu var?{" "}
            <a href="mailto:satis@hukukcuyapayzekasi.com" className="text-primary hover:underline">
              satis@hukukcuyapayzekasi.com
            </a>
          </div>
        </div>
      </div>
    </>
  );
}
