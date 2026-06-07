import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/seo/json-ld";
import { KVKKForm } from "./form";

export const metadata: Metadata = buildMetadata({
  title: "KVKK Uyum Kontrol Listesi | Sektör Bazlı Checklist Üretici",
  description:
    "KVKK uyumluluğu için sektör ve veri türüne özel 30+ maddelik checklist. Aydınlatma metni, VERBİS, açık rıza, veri ihlali bildirimi dahil.",
  path: "/kvkk",
  keywords: [
    "kvkk uyum", "kvkk checklist", "aydınlatma metni", "verbis kayıt",
    "açık rıza", "veri ihlali bildirimi", "kvkk kontrol listesi",
  ],
});

export default function KVKKPage() {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Ana Sayfa", url: "/" }, { name: "KVKK", url: "/kvkk" }])} />
      <div className="container py-10 max-w-6xl">
        <nav className="text-sm text-muted-foreground mb-4">
          <a href="/" className="hover:text-foreground">Ana Sayfa</a> / <span>KVKK Uyum</span>
        </nav>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">KVKK Uyum Kontrol Listesi</h1>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          Sektör ve işlenen veri türlerini seçin; KVKK 5, 6, 9, 10, 11, 12 ve ilgili yönetmelikler
          çerçevesinde uyum kontrol listesi üretsin. Uyum skorunuzu canlı görün.
        </p>
        <KVKKForm />
      </div>
    </>
  );
}
