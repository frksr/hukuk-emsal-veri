import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sayfa bulunamadı",
  description: "Aradığınız sayfa mevcut değil ya da taşınmış olabilir.",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <div className="container-main flex flex-col items-center justify-center py-24 text-center">
      <p className="text-sm font-semibold uppercase tracking-wider text-accent-600">
        404
      </p>
      <h1 className="mt-2">Sayfa bulunamadı</h1>
      <p className="mt-4 max-w-prose text-muted-foreground">
        Aradığınız sayfa mevcut değil, taşınmış ya da silinmiş olabilir.
      </p>
      <Link
        href="/"
        className="mt-8 inline-flex h-10 items-center justify-center rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground transition hover:bg-primary-600"
      >
        Anasayfaya dön
      </Link>
    </div>
  );
}
