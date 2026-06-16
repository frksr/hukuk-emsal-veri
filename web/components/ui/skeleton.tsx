import { cn } from "@/lib/utils";

/**
 * Tutarlı yükleme iskeleti — düz gri kutu yerine hafif shimmer'lı placeholder.
 */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-md bg-muted/70",
        "before:absolute before:inset-0 before:-translate-x-full",
        "before:animate-shimmer before:bg-gradient-to-r",
        "before:from-transparent before:via-foreground/5 before:to-transparent",
        className,
      )}
      {...props}
    />
  );
}
