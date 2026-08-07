# =============================================================================
# Alternatif backend imajı (Railway / self-host / docker-compose).
# Cloud Run için asıl imaj: Dockerfile.api
#
# İki aşamalı: derleme araçları final imajda kalmaz; süreç root olmayan
# kullanıcı ile çalışır.
# =============================================================================

# ---------- 1) builder -------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt


# ---------- 2) runtime -------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 LOG_FORMAT=json

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

# Source code
COPY --chown=appuser:appuser api/ ./api/
COPY --chown=appuser:appuser services/ ./services/
COPY --chown=appuser:appuser llm/ ./llm/
COPY --chown=appuser:appuser common/ ./common/
COPY --chown=appuser:appuser queries/ ./queries/
# Operasyon scriptleri (migration, volume seed, admin oluşturma, günlük cron).
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser pipelines/ ./pipelines/

# BÜYÜK VERİ IMAGE'A KOPYALANMAZ (.dockerignore ile de hariç tutulur).
# Production: kalıcı volume'u /data'ya mount edip bir kez seed edin:
#   CHROMA_DIR=/data/chroma_db python -m scripts.seed_volume --source <tgz|url|dizin>
# ve env'leri volume'a yönlendirin:
#   CHROMA_DIR=/data/chroma_db
#   DECISIONS_PARQUET=/data/final/all_decisions.parquet
# Detay: DEPLOY_VOLUME.md
RUN mkdir -p data/final data/chroma_db data/tenant_storage \
    && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000

# /api/ready DB bağlantısını da doğrular; /api/health yalnızca liveness'tır.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fs http://localhost:8000/api/ready || exit 1

# --proxy-headers + --forwarded-allow-ips: uvicorn'un XFF'i işlemesi için.
# İstemci IP'sinin nasıl çözüldüğü api/net.py'de (TRUSTED_PROXY_HOPS) tanımlı.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--proxy-headers", "--forwarded-allow-ips=*"]
