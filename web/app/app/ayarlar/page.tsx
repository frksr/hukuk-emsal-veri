import { auth } from "@/auth";
import { ProfilForm } from "./profil-form";

export const dynamic = "force-dynamic";

export default async function ProfilPage() {
  const session = await auth();
  return (
    <div className="max-w-2xl">
      <ProfilForm
        initialName={session?.user?.name ?? ""}
        initialEmail={session?.user?.email ?? ""}
      />
    </div>
  );
}
