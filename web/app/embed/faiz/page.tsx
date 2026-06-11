import type { Metadata } from "next";
import { FaizForm } from "@/app/faiz-hesaplayici/faiz-form";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukemsal.tr";

// Embed sayfası — iframe içinde gösterilir; indekslenmemeli.
export const metadata: Metadata = {
  title: "Faiz Hesaplayıcı | Hukuk Emsal",
  robots: { index: false, follow: false },
};

export default function EmbedFaizPage() {
  return (
    <div className="p-4 max-w-2xl mx-auto">
      <FaizForm />
      <div className="mt-4 text-center text-xs text-muted-foreground">
        <a
          href={`${SITE_URL}/faiz-hesaplayici?utm_source=embed&utm_medium=widget`}
          target="_blank"
          rel="noopener"
          className="hover:underline"
        >
          ⚖️ hukukemsal.tr — emsal karar arama ve hukuki hesaplama araçları
        </a>
      </div>
    </div>
  );
}
