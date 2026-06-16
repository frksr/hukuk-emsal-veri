"use client";
import { useEffect } from "react";
import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Portal } from "@/components/portal";

/**
 * Satın alma / işlem başarısı için belirgin onay popup'ı. Animasyonlu yeşil
 * tik + başlık + açıklama + kapat/devam butonu. Kullanıcı işlemin gerçekleştiğini
 * net görür.
 */
export function BasariModal({
  open,
  baslik,
  aciklama,
  onKapat,
  ctaHref,
  ctaLabel = "Tamam",
}: {
  open: boolean;
  baslik: string;
  aciklama?: string;
  onKapat: () => void;
  ctaHref?: string;
  ctaLabel?: string;
}) {
  // Modal açıkken arka plan kaymasını kilitle. Kaydırma çubuğu gizlenince
  // oluşacak yatay sıçramayı, çubuk genişliği kadar padding ekleyerek önle.
  useEffect(() => {
    if (!open) return;
    const sbw = window.innerWidth - document.documentElement.clientWidth;
    const oncekiOverflow = document.body.style.overflow;
    const oncekiPad = document.body.style.paddingRight;
    document.body.style.overflow = "hidden";
    if (sbw > 0) document.body.style.paddingRight = `${sbw}px`;
    return () => {
      document.body.style.overflow = oncekiOverflow;
      document.body.style.paddingRight = oncekiPad;
    };
  }, [open]);

  if (!open) return null;
  return (
    <Portal>
    <div
      className="fixed inset-0 z-[110] flex items-center justify-center bg-foreground/25 backdrop-blur-sm p-4 animate-fade-in"
      role="dialog"
      aria-modal="true"
      onClick={onKapat}
    >
      <div
        className="w-full max-w-sm rounded-2xl border bg-background p-7 text-center shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative mx-auto mb-4 flex h-16 w-16 items-center justify-center">
          <span className="absolute inset-0 rounded-full bg-emerald-500/15" />
          <span className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping" />
          <CheckCircle2 className="relative h-12 w-12 text-emerald-500 animate-pop" />
        </div>
        <h3 className="text-xl font-bold">{baslik}</h3>
        {aciklama && <p className="mt-2 text-sm text-muted-foreground">{aciklama}</p>}
        <div className="mt-6 flex justify-center gap-2">
          {ctaHref ? (
            <Button asChild onClick={onKapat}>
              <Link href={ctaHref}>{ctaLabel}</Link>
            </Button>
          ) : (
            <Button onClick={onKapat}>{ctaLabel}</Button>
          )}
        </div>
      </div>
    </div>
    </Portal>
  );
}
