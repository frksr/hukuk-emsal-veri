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
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=8080 HOSTNAME=0.0.0.0
# NOT: standalone server.js yerine TAM "next start" kullaniyoruz. Standalone
# sunucu bu uygulamada tum sayfalari /giris'e yonlendiren bir routing sorunu
# yaratiyordu (lokalde `next start` calisirken Cloud Run standalone'da donguye
# giriyordu). next start lokalde dogru calistigi icin prod'da da onu kullaniyoruz.
# Bu yaklasim ayni zamanda bcrypt native binary tracing sorununu da ortadan kaldirir
# (tam node_modules kopyalandigi icin).
COPY --from=build /app/public ./public
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/next.config.mjs ./next.config.mjs
COPY --from=build /app/next.config.js ./next.config.js
EXPOSE 8080
CMD ["node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "8080"]
