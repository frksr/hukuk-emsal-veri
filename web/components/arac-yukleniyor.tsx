import { Loader2 } from "lucide-react";

/** Plan/oturum çözülene kadar gösterilen nötr yükleniyor durumu (flash önler). */
export function AracYukleniyor() {
  return (
    <div className="flex items-center justify-center py-24">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}
