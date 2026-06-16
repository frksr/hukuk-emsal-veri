"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { usePlan } from "@/lib/use-plan";

/**
 * Fiyatlandırma sayfası plan butonu.
 *  - Giriş yapmamış → /kayit (ücretsiz kayıt; ardından doğrulama + yükseltme).
 *  - Giriş yapmış → kendi panelindeki Abonelik sayfasına gider (?plan=<key>),
 *    oradan yükseltir ve mevcut planını görür.
 *  - Zaten o plandaysa → "Mevcut Planın" (yine abonelik sayfasına götürür).
 */
export function PlanCta({
  planKey,
  label,
  highlight,
}: {
  planKey: string | null; // null → ücretsiz plan
  label: string;
  highlight?: boolean;
}) {
  const plan = usePlan();

  let href = planKey ? `/kayit?plan=${planKey}` : "/kayit";
  let text = label;

  if (plan.isLoggedIn) {
    if (!planKey) {
      href = "/app";
      text = "Panele Git";
    } else if (plan.plan === planKey) {
      href = "/app/ayarlar/abonelik";
      text = "Mevcut Planın";
    } else {
      href = `/app/ayarlar/abonelik?plan=${planKey}`;
      text = "Bu Plana Geç";
    }
  }

  return (
    <Button
      asChild
      className="mt-6 w-full"
      variant={highlight ? "default" : "outline"}
    >
      <Link href={href}>{text}</Link>
    </Button>
  );
}
