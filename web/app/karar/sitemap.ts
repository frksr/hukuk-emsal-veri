import type { MetadataRoute } from "next";

const API_BASE =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://hukukcuyapayzekasi.com";

const SAYFA_BOYU = 1000;
const SAYFA_SAYISI = 10; // pilot: ilk 10K karar

// /karar/sitemap/0.xml ... /karar/sitemap/9.xml
export async function generateSitemaps() {
  return Array.from({ length: SAYFA_SAYISI }, (_, i) => ({ id: i }));
}

export default async function sitemap({
  id,
}: {
  id: number;
}): Promise<MetadataRoute.Sitemap> {
  try {
    const res = await fetch(
      `${API_BASE}/api/karar/liste?limit=${SAYFA_BOYU}&offset=${id * SAYFA_BOYU}`,
      { next: { revalidate: 86400 } }
    );
    if (!res.ok) return [];
    const json = await res.json();
    const kararlar: Array<{ id: string; decision_date?: string }> =
      json?.data ?? [];
    return kararlar.map((k) => {
      // Gecersiz/bozuk decision_date -> Invalid Date olur ve Next sitemap'i XML'e
      // cevirirken toISOString() ile cokerdi ("Invalid time value"). Sadece GECERLI
      // tarihleri lastModified olarak ver, yoksa undefined.
      let lastModified: Date | undefined;
      if (k.decision_date) {
        const d = new Date(k.decision_date);
        if (!Number.isNaN(d.getTime())) lastModified = d;
      }
      return {
        url: `${SITE_URL}/karar/${encodeURIComponent(k.id)}`,
        lastModified,
        changeFrequency: "yearly" as const,
        priority: 0.5,
      };
    });
  } catch {
    // API erişilemezse boş sitemap — build'i kırma
    return [];
  }
}
