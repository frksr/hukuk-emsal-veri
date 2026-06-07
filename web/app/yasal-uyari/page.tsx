import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Yasal Uyarı",
  description: "Hukuk Emsal platformunun yasal uyarı ve sorumluluk reddi açıklaması.",
  path: "/yasal-uyari",
});

export default function YasalUyariPage() {
  return (
    <div className="container py-10 max-w-3xl prose prose-slate">
      <h1>Yasal Uyarı</h1>
      <p>
        Hukuk Emsal platformu, hukuk profesyonellerine ve genel kullanıcılara yardımcı bir <strong>AI
        destekli araç</strong>tır. Sunulan içerikler ve üretilen taslaklar profesyonel hukuk
        danışmanlığının yerine geçmez.
      </p>
      <h2>Sorumluluk Reddi</h2>
      <ul>
        <li>Üretilen dilekçe, ihtarname ve sözleşme analizleri <strong>taslak niteliğindedir</strong>; mahkemeye veya nota sunulmadan önce mutlaka bir avukat tarafından incelenmelidir.</li>
        <li>Faiz, zamanaşımı ve KVKK hesaplamaları <strong>yaklaşık değerlerdir</strong>; resmi süreçte yetkili mercilerin hesaplaması esastır.</li>
        <li>Emsal karar metinleri resmi sitelerden derlenmiştir; tam doğruluk için orijinal kaynağa başvurunuz.</li>
        <li>Platform, içeriklerin kullanımından doğan herhangi bir maddi/manevi zarar için sorumluluk kabul etmez.</li>
      </ul>
      <h2>Veri Kaynakları</h2>
      <p>Tüm emsal kararlar resmi açık kaynaklardan toplanmıştır: Yargıtay karararama, Danıştay karararama ve HUDOC (AİHM).</p>
      <h2>İletişim</h2>
      <p>Soru ve geri bildirimleriniz için <a href="mailto:info@hukukemsal.tr">info@hukukemsal.tr</a></p>
    </div>
  );
}
