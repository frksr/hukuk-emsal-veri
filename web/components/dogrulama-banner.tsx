"use client";
import Link from "next/link";
import { MailWarning } from "lucide-react";
import { usePlan } from "@/lib/use-plan";

/**
 * E-posta doğrulanmamış kullanıcılar için uyarı şeridi. AI üretimi, UYAP ve
 * ödeme işlemleri doğrulama gerektirir; doğrulanana kadar bu şerit gösterilir.
 */
export function DogrulamaBanner() {
  const plan = usePlan();
  if (plan.loading || !plan.isLoggedIn || plan.emailVerified) return null;

  return (
    <div className="mb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-amber-400/40 bg-amber-400/10 p-3 text-sm">
      <div className="flex items-start gap-2">
        <MailWarning className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <span>
          <strong>E-postanızı doğrulayın.</strong> Yapay Zeka araçları, UYAP ve
          ödeme işlemleri için e-posta doğrulaması gerekir.
        </span>
      </div>
      <Link
        href="/giris/dogrulama"
        className="shrink-0 rounded-md bg-amber-500 px-3 py-1.5 font-medium text-amber-950 hover:bg-amber-400 text-center"
      >
        Şimdi doğrula
      </Link>
    </div>
  );
}
