import { FaizForm } from "@/app/faiz-hesaplayici/faiz-form";

export const dynamic = "force-dynamic";

export default function PanelFaizPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Faiz & Tahsilat Hesaplayıcı</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Yasal faiz, ticari avans faizi ve İİK harçları ile tam tahsilat tutarını hesaplayın.
        </p>
      </div>
      <FaizForm />
    </div>
  );
}
