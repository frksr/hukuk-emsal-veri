import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";
import { ForgotForm, ResetForm } from "./forms";

export const metadata: Metadata = buildMetadata({
  title: "Şifre Sıfırlama",
  description: "Hukuk Emsal hesap şifrenizi sıfırlayın.",
  path: "/sifre-sifirla",
  noIndex: true,
});

export default function SifreSifirlaPage({
  searchParams,
}: {
  searchParams: { token?: string };
}) {
  const token = searchParams.token;
  return (
    <div className="container max-w-md py-16">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold mb-2">
          {token ? "Yeni Şifre Belirle" : "Şifre Sıfırlama"}
        </h1>
      </div>
      {token ? <ResetForm token={token} /> : <ForgotForm />}
    </div>
  );
}
