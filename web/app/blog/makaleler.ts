// ARTIK KULLANILMIYOR — tüm blog/rehber makaleleri artık `blog_articles`
// veritabanı tablosundan, admin panel (İçerik/Blog Yönetimi) üzerinden
// yönetiliyor (bkz. api/routers/icerik.py, web/app/panel/admin/icerik/).
// Burada statik olarak tutulan "emsal-karar-nedir" ve "ihtarname-nasil-cekilir"
// makaleleri veritabanına taşındı ve app/blog/<slug>/page.tsx statik route'ları
// kaldırıldı — aksi halde bu sabit route'lar admin panelde görünmeyen ve her
// zaman placeholder kapak gösteren "gizli/yönetilemeyen" içerik olarak
// kalıyordu. Bu dosya geriye dönük uyumluluk için boş bırakıldı; yeni kod
// buraya referans EKLEMEMELİDİR.

export interface Makale {
  slug: string;
  baslik: string;
  ozet: string;
  yayinTarihi: string;
  guncelleme?: string;
  yazar: string;
  ilgiliArac?: { etiket: string; href: string };
}

export const MAKALELER: Makale[] = [];

export function makaleBul(slug: string): Makale | undefined {
  return MAKALELER.find((m) => m.slug === slug);
}
