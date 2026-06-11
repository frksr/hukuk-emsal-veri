import { ImageResponse } from "next/og";

export const runtime = "edge";

const SITE_NAME = "Hukuk Emsal";

/**
 * Dinamik Open Graph görseli — lib/seo.ts generateOgImageUrl() bunu çağırır.
 *   /api/og?title=Faiz+Hesaplayıcı&subtitle=İİK+harçları+dahil
 */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const title = (searchParams.get("title") ?? SITE_NAME).slice(0, 120);
  const subtitle = (
    searchParams.get("subtitle") ??
    "Yargıtay · Danıştay · AİHM emsal kararları + AI hukuki araçlar"
  ).slice(0, 160);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background: "linear-gradient(135deg, #0b172d 0%, #1e3a5f 100%)",
          color: "#ffffff",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 56,
              height: 56,
              borderRadius: 12,
              background: "#c8a24a",
              color: "#0b172d",
              fontSize: 34,
              fontWeight: 700,
            }}
          >
            §
          </div>
          <div style={{ fontSize: 32, fontWeight: 700, letterSpacing: -0.5 }}>
            {SITE_NAME}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              fontSize: title.length > 60 ? 48 : 60,
              fontWeight: 800,
              lineHeight: 1.15,
              letterSpacing: -1,
              maxWidth: 1000,
            }}
          >
            {title}
          </div>
          <div style={{ fontSize: 28, color: "#b7c4d8", maxWidth: 960 }}>
            {subtitle}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 22,
            color: "#8fa3bd",
          }}
        >
          <div>hukukemsal.tr</div>
          <div>İcra · Tahsilat · İhtar · KVKK</div>
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}
