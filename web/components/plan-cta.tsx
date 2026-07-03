import Link from "next/link";
import { Button } from "@/components/ui/button";

/**
 * Fiyatlandırma sayfası plan butonu — bekleme listesi modu.
 * Ücretli planlar bekleme listesine yönlendirir (davetli beta). Ücretsiz plan
 * beklemeye tabi değil — doğrudan kayıt olup hemen kullanılabilir.
 * Platform tüm planlarda satışa açıldığında bu bileşen eski akışa döndürülecek.
 */
export function PlanCta({
  planKey,
  label,
  highlight,
}: {
  planKey: string | null;
  label: string;
  highlight?: boolean;
}) {
  const ucretsiz = planKey === "free";
  const href = ucretsiz ? "/kayit" : `/bekleme-listesi${planKey ? `?plan=${planKey}` : ""}`;

  return (
    <Button
      asChild
      className="mt-6 w-full"
      variant={highlight ? "default" : "outline"}
    >
      <Link href={href}>{ucretsiz ? label : "Bekleme Listesine Katıl"}</Link>
    </Button>
  );
}
