"use client";
import { useRouter } from "next/navigation";
import { Sparkles, Lock, Check, Package } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

/**
 * Tam-ekran "Pro özelliği" upsell'i. Yetkisi olmayan kullanıcıya formun YERİNE
 * gösterilir (form hiç render olmaz). Girişsizse kayda, girişliyse kendi panelindeki
 * Abonelik sayfasına yönlendirir (oradan yükseltir + mevcut planını görür).
 */
export function ProUpsell({
  baslik,
  aciklama,
  ozellikler,
  isLoggedIn,
  modul,
}: {
  baslik: string;
  aciklama: string;
  ozellikler: string[];
  isLoggedIn: boolean;
  /** Bu araca karşılık gelen modül anahtarı — ek paket bağlantısı için. */
  modul?: string;
}) {
  const router = useRouter();
  const ekPaketHref = modul
    ? `/panel/ayarlar/ek-paketler?modul=${encodeURIComponent(modul)}`
    : "/panel/ayarlar/ek-paketler";
  return (
    <Card className="max-w-2xl mx-auto border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
      <CardHeader>
        <div className="flex items-center gap-2">
          <div className="rounded-full bg-primary/10 p-2 text-primary">
            <Lock className="h-5 w-5" />
          </div>
          <span className="text-[10px] uppercase tracking-wider rounded-full bg-primary/10 text-primary px-2 py-0.5">
            Pro özelliği
          </span>
        </div>
        <CardTitle className="mt-3 text-xl">{baslik}</CardTitle>
        <CardDescription>{aciklama}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <ul className="space-y-2 text-sm">
          {ozellikler.map((o) => (
            <li key={o} className="flex items-start gap-2">
              <Check className="h-4 w-4 text-primary mt-0.5 shrink-0" /> {o}
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => router.push(isLoggedIn ? "/panel/ayarlar/abonelik" : "/kayit")}>
            <Sparkles className="h-4 w-4 mr-1.5" />
            {isLoggedIn ? "Planı Yükselt" : "Ücretsiz kayıt ol"}
          </Button>
          {isLoggedIn && modul && (
            <Button variant="outline" onClick={() => router.push(ekPaketHref)}>
              <Package className="h-4 w-4 mr-1.5" />
              Ek paket al
            </Button>
          )}
          {!isLoggedIn && (
            <button
              type="button"
              onClick={() => router.push("/giris")}
              className="text-sm text-muted-foreground hover:text-foreground underline"
            >
              Zaten hesabın var mı? Giriş yap
            </button>
          )}
        </div>
        {isLoggedIn && modul && (
          <p className="text-xs text-muted-foreground">
            Üst pakete geçmek istemiyorsanız, yalnızca bu araç için ek kullanım paketi
            satın alabilirsiniz — krediler hesabınıza tanımlanır, süresiz geçerlidir.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
