import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { GirisForm } from "./form";

export const metadata: Metadata = buildMetadata({
  title: "Giriş Yap",
  description: "Hukuk Emsal hesabınızla giriş yapın.",
  path: "/giris",
});

export default function GirisPage() {
  return (
    <div className="container max-w-md py-16">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold mb-2">Giriş Yap</h1>
        <p className="text-sm text-muted-foreground">
          Hesabınız yok mu?{" "}
          <a href="/kayit" className="text-primary hover:underline font-medium">Kayıt olun</a>
        </p>
      </div>
      <GirisForm />
    </div>
  );
}
