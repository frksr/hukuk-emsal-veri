FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2, pypdf, chromadb
RUN apt-get update && apt-get install -y \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code
COPY api/ ./api/
COPY services/ ./services/
COPY llm/ ./llm/
COPY common/ ./common/
COPY queries/ ./queries/
# Operasyon scriptleri (migration, volume seed, admin oluşturma vb.)
COPY scripts/ ./scripts/

# BÜYÜK VERİ IMAGE'A KOPYALANMAZ (.dockerignore ile de hariç tutulur).
# Production: kalıcı volume'u /data'ya mount edip bir kez seed edin:
#   CHROMA_DIR=/data/chroma_db python -m scripts.seed_volume --source <tgz|url|dizin>
# ve env'leri volume'a yönlendirin:
#   CHROMA_DIR=/data/chroma_db
#   DECISIONS_PARQUET=/data/final/all_decisions.parquet
# Detay: DEPLOY_VOLUME.md
RUN mkdir -p data/final data/chroma_db data/tenant_storage

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -fs http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
