import { KVKKForm } from "@/app/kvkk/form";

export const dynamic = "force-dynamic";

export default function PanelKvkkPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">KVKK Uyum Checklist</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Sektör ve veri türlerinize göre KVKK uyum maddelerinizi ve uyum skorunuzu görün.
        </p>
      </div>
      <KVKKForm />
    </div>
  );
}
