import { RaporlarPanel } from "./raporlar-panel";

export const dynamic = "force-dynamic";

export default function RaporlarPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Raporlar & Kullanım</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Geçmiş sorgular, kullanım istatistikleri ve fatura geçmişi.
        </p>
      </div>
      <RaporlarPanel />
    </div>
  );
}
