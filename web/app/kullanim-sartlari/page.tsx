import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Kullanım Şartları",
  description: "Hukuk Emsal platformu kullanım şartları ve hizmet koşulları.",
  path: "/kullanim-sartlari",
});

export default function KullanimPage() {
  return (
    <div className="container py-10 max-w-3xl prose prose-slate">
      <h1>Kullanım Şartları</h1>
      <p>Bu platformu kullanarak aşağıdaki şartları kabul etmiş sayılırsınız.</p>
      <h2>Hizmetin Niteliği</h2>
      <p>Hukuk Emsal, Yapay Zeka destekli hukuki bilgi ve taslak üretim platformudur. <strong>Hukuki danışmanlık hizmeti vermez.</strong></p>
      <h2>Kullanıcı Yükümlülükleri</h2>
      <ul>
        <li>Platformu yasalara aykırı amaçlarla kullanmamak</li>
        <li>Üretilen içerikleri profesyonel inceleme olmadan resmi sürece sokmamak</li>
        <li>Hesabınızın güvenliğinden sorumlu olmak</li>
        <li>Telif hakkı korunan içerikleri yetkisiz şekilde paylaşmamak</li>
      </ul>
      <h2>Fikri Mülkiyet</h2>
      <p>Platform üzerindeki tasarım, kod ve markalar Hukuk Emsal'e aittir. Resmi kaynaklardan alınan emsal kararlar kamu malıdır.</p>
      <h2>Hizmet Değişiklikleri</h2>
      <p>Hizmet kapsamı önceden bildirim yapılmaksızın değiştirilebilir. Önemli değişiklikler kullanıcılara e-posta veya site bildirimi ile duyurulur.</p>
      <h2>İletişim</h2>
      <p><a href="mailto:info@hukukcuyapayzekasi.com">info@hukukcuyapayzekasi.com</a></p>
    </div>
  );
}
