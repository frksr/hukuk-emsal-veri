"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Scale, Lock, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePlan } from "@/lib/use-plan";

/**
 * "Yapay Zeka özetini çıkar" butonu.
 *  - Ücretli plan → /karar-ozet?id=... (özet orada otomatik üretilir)
 *  - Ücretsiz/giriş yok → kilitli; tıklayınca fiyatlandırmaya yönlendirir.
 */
export function AiOzetButton({ decisionId }: { decisionId: string }) {
  const { loading, isPaid, isLoggedIn } = usePlan();
  const router = useRouter();

  if (loading) {
    return (
      <Button size="sm" variant="outline" disabled>
        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> Yapay Zeka özetini çıkar
      </Button>
    );
  }

  if (isPaid) {
    return (
      <Button asChild size="sm" variant="outline">
        <Link href={`/karar-ozet?id=${encodeURIComponent(decisionId)}`}>
          <Scale className="h-3.5 w-3.5 mr-1.5" /> Yapay Zeka özetini çıkar
        </Link>
      </Button>
    );
  }

  // Ücretsiz: kilitli — yükseltmeye yönlendir
  return (
    <Button
      size="sm"
      variant="outline"
      title={isLoggedIn ? "Yapay Zeka özet Pro aboneliğe özeldir" : "Kullanmak için ücretsiz kayıt olun"}
      onClick={() => router.push(isLoggedIn ? "/fiyatlandirma" : "/kayit")}
      className="opacity-90"
    >
      <Lock className="h-3.5 w-3.5 mr-1.5" /> Yapay Zeka özetini çıkar
      <span className="ml-1.5 text-[10px] rounded-full bg-primary/10 text-primary px-1.5 py-0.5">Pro</span>
    </Button>
  );
}
