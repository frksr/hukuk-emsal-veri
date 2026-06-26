// Blog/rehber makalelerinin tek kaynağı (single source of truth).
// Yeni makale eklerken: buraya bir kayıt + app/blog/<slug>/page.tsx ekleyin
// ve app/sitemap.ts'e /blog/<slug> satırını koyun.

export interface Makale {
  slug: string;
  baslik: string;
  ozet: string;
  yayinTarihi: string; // ISO
  guncelleme?: string; // ISO
  yazar: string;
  ilgiliArac?: { etiket: string; href: string };
}

export const MAKALELER: Makale[] = [
  {
    slug: "emsal-karar-nedir",
    baslik: "Emsal Karar Nedir? Yargıtay ve Danıştay Kararları Nasıl Kullanılır?",
    ozet:
      "Emsal karar kavramı, bağlayıcılığı, içtihatla farkı ve bir davada emsal kararın nasıl gerekçe olarak kullanılacağı.",
    yayinTarihi: "2026-06-26",
    yazar: "Hukukçu Yapay Zekası Editör Ekibi",
    ilgiliArac: { etiket: "Emsal karar arama", href: "/emsal-arama" },
  },
  {
    slug: "ihtarname-nasil-cekilir",
    baslik: "İhtarname Nasıl Çekilir? Adım Adım Noter İhtarnamesi Rehberi",
    ozet:
      "İhtarnamenin hukuki işlevi, noter ihtarnamesi süreci, alacak ve kira tahliye ihtarnamelerinde dikkat edilecekler.",
    yayinTarihi: "2026-06-26",
    yazar: "Hukukçu Yapay Zekası Editör Ekibi",
    ilgiliArac: { etiket: "İhtarname üretici", href: "/ihtarname" },
  },
];

export function makaleBul(slug: string): Makale | undefined {
  return MAKALELER.find((m) => m.slug === slug);
}
