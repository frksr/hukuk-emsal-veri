import { Verifier } from "./verifier";

export default function DogrulamaPage({
  searchParams,
}: {
  searchParams: { token?: string };
}) {
  return (
    <div className="container max-w-md py-16 text-center">
      <h1 className="text-3xl font-bold mb-3">E-posta Doğrulama</h1>
      <Verifier token={searchParams.token} />
    </div>
  );
}
