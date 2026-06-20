#!/usr/bin/env bash
# =============================================================================
# migrate_db.sh — DB şemasını uygula + app_user yetkileri + ilk admin.
#
# Cloud SQL Auth Proxy üzerinden çalışır (localhost:5432). Proxy yoksa indirir.
# deploy.env'i okur. setup_gcp.sh'in "dbusers" fazından SONRA çalıştır.
#
# KULLANIM:
#   chmod +x infra/gcp/migrate_db.sh
#   ./infra/gcp/migrate_db.sh
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"

[ -f "$HERE/deploy.env" ] || { echo "HATA: deploy.env yok"; exit 1; }
set -a; . "$HERE/deploy.env"; set +a

gcloud config set project "$PROJECT_ID" >/dev/null
SQL_CONN="$(gcloud sql instances describe "$SQL_INSTANCE_ID" --format='value(connectionName)')"
echo ">> SQL_CONN = $SQL_CONN"

# ---- Cloud SQL Auth Proxy bul/indir ----------------------------------------
PROXY="$HERE/cloud-sql-proxy"
if [ ! -x "$PROXY" ]; then
  echo ">> cloud-sql-proxy indiriliyor..."
  OS="$(uname -s | tr '[:upper:]' '[:lower:]')"   # linux / darwin
  ARCH="$(uname -m)"; [ "$ARCH" = "x86_64" ] && ARCH="amd64"; [ "$ARCH" = "aarch64" ] && ARCH="arm64"
  curl -sL "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.11.0/cloud-sql-proxy.${OS}.${ARCH}" -o "$PROXY"
  chmod +x "$PROXY"
fi

# ---- Proxy'yi başlat --------------------------------------------------------
"$PROXY" --port 5432 "$SQL_CONN" &
PROXY_PID=$!
trap 'kill $PROXY_PID 2>/dev/null || true' EXIT
echo ">> Proxy başlatıldı (pid $PROXY_PID), hazır olması bekleniyor..."
for i in $(seq 1 30); do
  (echo > /dev/tcp/127.0.0.1/5432) >/dev/null 2>&1 && break
  sleep 1
done

# ---- Migration (owner/admin DSN, localhost) ---------------------------------
export ADMIN_DATABASE_URL="postgresql://${DB_OWNER_USER}:${DB_OWNER_PASSWORD}@localhost:5432/${DB_NAME}"
echo ">> Migration uygulanıyor (scripts/init_db.py)..."
cd "$ROOT"
python scripts/init_db.py

# ---- app_user tablo yetkileri ----------------------------------------------
echo ">> app_user yetkileri veriliyor..."
PGPASSWORD="$DB_OWNER_PASSWORD" psql \
  "host=localhost port=5432 dbname=${DB_NAME} user=${DB_OWNER_USER}" <<SQL
GRANT USAGE ON SCHEMA public TO ${DB_APP_USER};
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ${DB_APP_USER};
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ${DB_APP_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${DB_APP_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO ${DB_APP_USER};
SQL

# ---- İlk admin kullanıcı ----------------------------------------------------
if [ -n "${APP_ADMIN_PASSWORD:-}" ] && [ "${APP_ADMIN_PASSWORD}" != "__DOLDUR__" ]; then
  echo ">> İlk admin oluşturuluyor: $APP_ADMIN_EMAIL"
  python scripts/create_admin.py --email "$APP_ADMIN_EMAIL" \
    --password "$APP_ADMIN_PASSWORD" --name "${APP_ADMIN_NAME:-Admin}" || \
    echo "   (admin zaten var olabilir — atlandı)"
else
  echo ">> APP_ADMIN_PASSWORD boş → admin oluşturma atlandı."
fi

echo ">> Migration tamam. Şimdi: ./infra/gcp/setup_gcp.sh deploy"
