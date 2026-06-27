import { DilekceForm } from "@/app/dilekce/dilekce-form";

export const dynamic = "force-dynamic";

export default function PanelDilecePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dilekçe Üretici</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Davanızı anlatın; Yapay Zeka Yargıtay emsallerine atıfla dilekçe taslağı hazırlasın.
        </p>
      </div>
      <DilekceForm />
    </div>
  );
}
