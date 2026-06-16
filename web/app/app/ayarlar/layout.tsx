import Link from "next/link";

const TABS = [
  { href: "/app/ayarlar", label: "Profil" },
  { href: "/app/ayarlar/guvenlik", label: "Güvenlik" },
  { href: "/app/ayarlar/kvkk", label: "KVKK & Veriler" },
];

export default function AyarlarLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Ayarlar</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Profil, güvenlik ve KVKK haklarınızı yönetin.
        </p>
      </div>
      <nav className="flex gap-1 border-b overflow-x-auto">
        {TABS.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className="px-4 py-2 text-sm hover:text-foreground text-muted-foreground border-b-2 border-transparent hover:border-primary transition-colors whitespace-nowrap"
          >
            {t.label}
          </Link>
        ))}
      </nav>
      <div>{children}</div>
    </div>
  );
}
