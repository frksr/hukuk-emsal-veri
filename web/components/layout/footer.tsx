import Link from "next/link";
import { Scale, Github, Twitter, Linkedin } from "lucide-react";

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

const YASAL = [
  { href: "/fiyatlandirma", label: "Fiyatlandırma" },
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
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <Link
              href="/"
              className="flex items-center gap-2 font-heading text-lg font-bold text-primary-700"
            >
              <Scale className="h-6 w-6 text-accent-500" aria-hidden="true" />
              <span>Hukuk Emsal</span>
            </Link>
            <p className="mt-3 max-w-xs text-sm text-muted-foreground">
              Yargıtay, Danıştay ve AİHM emsal kararları + Yapay Zeka destekli hukuki
              araçlar.
            </p>

            <div className="mt-4 flex items-center gap-3">
              <a
                href="https://github.com"
                aria-label="GitHub"
                target="_blank"
                rel="noreferrer noopener"
                className="text-muted-foreground hover:text-foreground"
              >
                <Github className="h-5 w-5" />
              </a>
              <a
                href="https://twitter.com"
                aria-label="Twitter"
                target="_blank"
                rel="noreferrer noopener"
                className="text-muted-foreground hover:text-foreground"
              >
                <Twitter className="h-5 w-5" />
              </a>
              <a
                href="https://linkedin.com"
                aria-label="LinkedIn"
                target="_blank"
                rel="noreferrer noopener"
                className="text-muted-foreground hover:text-foreground"
              >
                <Linkedin className="h-5 w-5" />
              </a>
            </div>
          </div>

          <FooterCol title="Kategoriler" items={KATEGORI} />
          <FooterCol title="Araçlar" items={ARACLAR} />
          <FooterCol title="Yasal" items={YASAL} />
        </div>

        <div className="mt-10 flex flex-col items-start justify-between gap-3 border-t border-border pt-6 text-xs text-muted-foreground md:flex-row md:items-center">
          <p>© {yil} Hukuk Emsal. Tüm hakları saklıdır.</p>
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
