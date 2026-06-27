import { AramaForm } from "@/app/emsal-arama/arama-form";

export const dynamic = "force-dynamic";

export default function PanelEmsalAramaPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Emsal Karar Arama</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Yargıtay, Danıştay ve AİHM kararları arasında doğal dilde arama yapın.
        </p>
      </div>
      <AramaForm />
    </div>
  );
}
