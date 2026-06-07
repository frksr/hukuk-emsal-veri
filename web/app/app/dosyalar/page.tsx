import { DosyalarPanel } from "./dosyalar-panel";

export const dynamic = "force-dynamic";

export default function DosyalarPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">UYAP Dosyalarım</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Şifreli olarak saklanan kişisel dava dosyalarınız. Her dosya sadece size özeldir.
        </p>
      </div>
      <DosyalarPanel />
    </div>
  );
}
