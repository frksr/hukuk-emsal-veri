import { SorguPanel } from "./sorgu-panel";

export const dynamic = "force-dynamic";

export default function SorguPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">AI Sorgu</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Kendi UYAP dosyalarınızda ve emsal kararlarda AI ile sorgu yapın.
        </p>
      </div>
      <SorguPanel />
    </div>
  );
}
