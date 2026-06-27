import { ZamanasimiForm } from "@/app/zamanasimi/zamanasimi-form";

export const dynamic = "force-dynamic";

export default function PanelZamanasimiPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Zamanaşımı Hesaplayıcı</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Alacak türüne göre zamanaşımı süresini, kesilme ve durma hallerini hesaplayın.
        </p>
      </div>
      <ZamanasimiForm />
    </div>
  );
}
