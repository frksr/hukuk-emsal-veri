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

# Data (production'da bu volume mount edilebilir)
COPY data/final/all_decisions.parquet ./data/final/all_decisions.parquet
COPY data/chroma_db ./data/chroma_db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -fs http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
