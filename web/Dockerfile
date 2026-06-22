# =============================================================================
# Production frontend image (Cloud Run) — Next.js 14 standalone.
# Build context = web/ (kök .dockerignore web/'i hariç tuttuğu için context web/).
#
# NEXT_PUBLIC_* değişkenleri DERLEME ANINDA gömülür → build-arg ile verilir.
# NEXTAUTH_SECRET / DATABASE_URL gibi sunucu sırları RUNTIME'da (Cloud Run env/secret).
# =============================================================================
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Public (NEXT_PUBLIC_*) değişkenler derlemede inline edilir.
ARG NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
# HOSTNAME=0.0.0.0 ZORUNLU: Next standalone server.js process.env.HOSTNAME'e bind eder;
# Docker bunu konteyner ID'sine ayarlar → 0.0.0.0:8080 yerine yanlis host'a baglanip
# dinleyemez (Cloud Run "failed to listen on PORT 8080"). 0.0.0.0'a sabitle.
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=8080 HOSTNAME=0.0.0.0
# Standalone çıktı (next.config: output: "standalone")
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 8080
CMD ["node", "server.js"]
