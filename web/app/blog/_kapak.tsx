import { Scale } from "lucide-react";

/**
 * Kapak görseli tanımlanmamış makaleler için — marka renkleriyle tutarlı,
 * slug'a göre hafif değişen bir gradyan + Scale ikonu. Liste kartlarında ve
 * makale detay sayfasının hero alanında ortak kullanılır.
 */
export function KapakYerTutucu({ slug }: { slug: string }) {
  const varyant = slug.length % 3;
  const gradyan = [
    "from-primary/25 via-primary/10 to-accent/20",
    "from-accent/25 via-primary/10 to-primary/25",
    "from-primary/20 via-accent/10 to-primary/20",
  ][varyant];
  return (
    <div
      className={`flex h-full w-full items-center justify-center bg-gradient-to-br ${gradyan}`}
    >
      <Scale className="h-10 w-10 text-primary/50" aria-hidden="true" />
    </div>
  );
}
