import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Liste sayfaları için tutarlı yükleme iskeleti — yalnız bir spinner yerine
 * içeriğin şekline benzeyen shimmer'lı placeholder satırları gösterir.
 */
export function ListSkeleton({ rows = 4, cols = 1 }: { rows?: number; cols?: 1 | 2 }) {
  return (
    <div className={cols === 2 ? "grid sm:grid-cols-2 gap-3" : "space-y-2"}>
      {Array.from({ length: rows }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-4 flex items-center gap-3">
            <Skeleton className="h-9 w-9 rounded-md shrink-0" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
