import Link from "next/link";
import { Scale } from "lucide-react";

const KATEGORI = [
  { href: "/emsal-arama", label: "Emsal Arama" },
  { href: "/dilekce", label: "Dilekçe Oluşturma" },
  { href: "/ihtarname", label: "İhtarname" },
  { href: "/sozlesme-analizi", label: "Sözleşme Analizi" },
];

const ARACLAR = [
  { href: "/faiz-hesaplayici", label: "Faiz Hesaplama" },
  { href: "/zamanasimi", label: "Zamanaşımı" },
  { href: "/kvkk", label: "KVKK Uyum" },
  { href: "/trend", label: "Yıllık Trendler" },
  { href: "/blog", label: "Hukuk Rehberi" },
];

const KURUMSAL = [
  { href: "/hakkimizda", label: "Hakkımızda" },
  { href: "/editoryal-politika", label: "Editoryal Politika" },
  { href: "/veri-kaynaklari", label: "Veri Kaynakları" },
  { href: "/fiyatlandirma", label: "Fiyatlandırma" },
];

const YASAL = [
  { href: "/yasal-uyari", label: "Yasal Uyarı" },
  { href: "/gizlilik", label: "Gizlilik Politikası" },
  { href: "/kullanim-sartlari", label: "Kullanım Koşulları" },
  { href: "/mesafeli-satis", label: "Mesafeli Satış Sözleşmesi" },
  { href: "/iade-politikasi", label: "Cayma ve İade Politikası" },
];

export function Footer() {
  const yil = new Date().getFullYear();

  return (
    <footer
      className="mt-16 border-t border-border bg-secondary/40"
      role="contentinfo"
    >
      <div className="container-main py-12">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-5">
          <div className="col-span-2 md:col-span-1">
            <Link
              href="/"
              className="flex items-center gap-2 font-heading text-lg font-bold text-primary-700"
            >
              <Scale className="h-6 w-6 text-accent-500" aria-hidden="true" />
              <span>Hukukçu Yapay Zekası</span>
            </Link>
            <p className="mt-3 max-w-xs text-sm text-muted-foreground">
              İcra ve tahsilat hukukuna özel, Yapay Zeka destekli emsal karar
              arama platformu (Hukuk Emsal).
            </p>
          </div>

          <FooterCol title="Kategoriler" items={KATEGORI} />
          <FooterCol title="Araçlar" items={ARACLAR} />
          <FooterCol title="Kurumsal" items={KURUMSAL} />
          <FooterCol title="Yasal" items={YASAL} />
        </div>

        <div className="mt-10 flex flex-col items-start justify-between gap-3 border-t border-border pt-6 text-xs text-muted-foreground md:flex-row md:items-center">
          <p>© {yil} Hukukçu Yapay Zekası. Tüm hakları saklıdır.</p>
          <p className="max-w-prose">
            Bu site hukuki bilgi sağlar; hukuki danışmanlık yerine geçmez.
            Önemli kararlarınızda mutlaka bir avukata danışın.
          </p>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({
  title,
  items,
}: {
  title: string;
  items: Array<{ href: string; label: string }>;
}) {
  return (
    <div>
      <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
        {title}
      </h2>
      <ul className="mt-3 space-y-2">
        {items.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
