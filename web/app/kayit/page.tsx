import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { KayitForm } from "./form";

export const metadata: Metadata = buildMetadata({
  title: "Ücretsiz Hesap Aç",
  description:
    "Hukuk Emsal ücretsiz hesap açın. Geçmiş aramalar, daha yüksek limitler ve e-mail bildirimleri kullanıma sunulur.",
  path: "/kayit",
  noIndex: true,
});

export default function KayitPage() {
  return (
    <div className="container max-w-md py-16">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold mb-2">Ücretsiz Hesap Aç</h1>
        <p className="text-sm text-muted-foreground">
          Zaten üye misiniz?{" "}
          <a href="/giris" className="text-primary hover:underline font-medium">Giriş yapın</a>
        </p>
      </div>
      <KayitForm />
    </div>
  );
}
