import Link from "next/link";
import { Button } from "@/components/ui/button";

/**
 * Fiyatlandırma sayfası plan butonu — bekleme listesi modu.
 * Tüm planlar için bekleme listesine yönlendirir.
 * Platform hazır olduğunda bu bileşen eski akışa döndürülecek.
 */
export function PlanCta({
  planKey,
  label: _label,
  highlight,
}: {
  planKey: string | null;
  label: string;
  highlight?: boolean;
}) {
  const href = `/bekleme-listesi${planKey ? `?plan=${planKey}` : ""}`;

  return (
    <Button
      asChild
      className="mt-6 w-full"
      variant={highlight ? "default" : "outline"}
    >
      <Link href={href}>Bekleme Listesine Katıl</Link>
    </Button>
  );
}
