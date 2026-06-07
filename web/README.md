# Hukuk Emsal — Web (Next.js 14)

Production-ready frontend for the Turkish legal precedent AI assistant.

## Stack

- **Next.js 14** App Router + React 18 + TypeScript
- **Tailwind CSS** + shadcn/ui pattern
- **TanStack Query** for server state
- **next-sitemap** for SEO sitemap
- **schema-dts** for JSON-LD structured data

## Setup

```bash
cd web
npm install
cp .env.local.example .env.local
# .env.local'i düzenle (NEXT_PUBLIC_API_URL backend adresi)
npm run dev
```

Tarayıcıda: <http://localhost:3000>

## Build & Deploy

```bash
npm run build
npm start
```

### Vercel deploy
```bash
vercel --prod
```
Environment variables:
- `NEXT_PUBLIC_API_URL` = FastAPI backend URL
- `NEXT_PUBLIC_SITE_URL` = domain URL

## Pages

- `/` — Anasayfa (SEO landing)
- `/emsal-arama` — RAG arama
- `/dilekce` — Emsal-bağlamlı dilekçe
- `/karar-ozet` — (yapılacak)
- `/faiz-hesaplayici` — İcra faiz + harçlar
- `/zamanasimi` — (yapılacak)
- `/ihtarname` — (yapılacak)
- `/trend` — (yapılacak)
- `/karsi-argument` — (yapılacak)
- `/kvkk` — (yapılacak)
- `/sozlesme-analizi` — (yapılacak)

## SEO Özellikleri

- Her sayfa: unique title, description, OG image, canonical
- JSON-LD: LegalService, BreadcrumbList, FAQPage, HowTo
- robots.txt, sitemap.xml (App Router native)
- Türkçe locale, lang="tr"
- H tag hiyerarşisi (H1 → H2 → H3)
- Mobile-first responsive
- Lighthouse hedefi: 95+ tüm metriklerde

## Önemli Yapı

```
web/
├── app/
│   ├── layout.tsx           # Root + Header + Footer + Providers
│   ├── page.tsx             # Anasayfa (Server)
│   ├── sitemap.ts           # Otomatik sitemap
│   ├── robots.ts            # Otomatik robots
│   ├── globals.css
│   └── [feature]/
│       ├── page.tsx         # Server: SEO metadata + breadcrumb + JSON-LD
│       └── *-form.tsx       # Client: interaktif form
├── components/
│   ├── ui/                  # shadcn primitives
│   ├── layout/              # header, footer
│   ├── seo/                 # JsonLd
│   └── providers.tsx        # React Query
├── lib/
│   ├── api.ts               # FastAPI client + types
│   ├── seo.ts               # buildMetadata, JSON-LD helpers
│   └── utils.ts             # cn, formatTRY, formatTarih
└── next.config.mjs
```
