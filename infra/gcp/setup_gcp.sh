#!/usr/bin/env bash
# =============================================================================
# setup_gcp.sh — Tek seferlik GCP kurulumu + deploy (idempotent).
#
# deploy.env ve secrets.env'i okur. Var olan kaynakları ATLAR, eksikleri kurar.
#
# KULLANIM:
#   chmod +x infra/gcp/setup_gcp.sh
#   ./infra/gcp/setup_gcp.sh all          # baştan sona (migration HARİÇ)
#   ./infra/gcp/setup_gcp.sh <faz>        # tek faz çalıştır
#
# Fazlar:  apis  registry  buckets  data  dbusers  secrets  iam  deploy  verify
#
# Migration ayrı: önce bu scriptin "secrets/dbusers" fazları, sonra
#   ./infra/gcp/migrate_db.sh   (Cloud SQL proxy gerektirir)
# en son ./infra/gcp/setup_gcp.sh deploy
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"

# ---- env yükle --------------------------------------------------------------
[ -f "$HERE/deploy.env" ]  || { echo "HATA: $HERE/deploy.env yok"; exit 1; }
set -a; . "$HERE/deploy.env"; [ -f "$HERE/secrets.env" ] && . "$HERE/secrets.env"; set +a

for v in PROJECT_ID REGION SQL_INSTANCE_ID DB_NAME DB_OWNER_USER DB_APP_USER DATA_BUCKET TS_BUCKET; do
  val="${!v:-}"
  if [ -z "$val" ] || [ "$val" = "__DOLDUR__" ]; then
    echo "HATA: deploy.env içinde '$v' doldurulmamış."; exit 1
  fi
done

gcloud config set project "$PROJECT_ID" >/dev/null

# Cloud SQL bağlantı adını otomatik bul (PROJECT:REGION:INSTANCE)
SQL_CONN="$(gcloud sql instances describe "$SQL_INSTANCE_ID" --format='value(connectionName)' 2>/dev/null || true)"
[ -n "$SQL_CONN" ] || { echo "HATA: '$SQL_INSTANCE_ID' instance bulunamadı (proje/region doğru mu?)"; exit 1; }
echo ">> SQL_CONN = $SQL_CONN"

# 3 DSN'i DB kullanıcı/parolalarından türet (Cloud SQL unix socket)
DSN_APP="postgresql://${DB_APP_USER}:${DB_APP_PASSWORD}@/${DB_NAME}?host=/cloudsql/${SQL_CONN}"
DSN_OWNER="postgresql://${DB_OWNER_USER}:${DB_OWNER_PASSWORD}@/${DB_NAME}?host=/cloudsql/${SQL_CONN}"

# ---- yardımcılar ------------------------------------------------------------
secret_put() {  # ad değer  → yoksa create, varsa yeni sürüm ekle
  local name="$1" value="$2"
  if [ -z "$value" ] || [ "$value" = "__DOLDUR__" ]; then
    echo "   ATLA  $name (değer boş)"; return 0
  fi
  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- >/dev/null
    echo "   ↑ sürüm  $name"
  else
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- >/dev/null
    echo "   + yeni   $name"
  fi
}

# ---- fazlar -----------------------------------------------------------------
ph_apis() {
  echo "== APIs enable =="
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    sqladmin.googleapis.com secretmanager.googleapis.com \
    artifactregistry.googleapis.com storage.googleapis.com
}

ph_registry() {
  echo "== Artifact Registry =="
  gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1 \
    && echo "   var: $AR_REPO" \
    || gcloud artifacts repositories create "$AR_REPO" --repository-format=docker --location="$REGION"
}

ph_buckets() {
  echo "== GCS bucket'lar =="
  for b in "$DATA_BUCKET" "$TS_BUCKET"; do
    if gcloud storage buckets describe "gs://$b" >/dev/null 2>&1; then
      echo "   var: gs://$b"
    else
      gcloud storage buckets create "gs://$b" --location="$REGION"
    fi
  done
}

ph_data() {
  echo "== Vektör verisini yükle =="
  if gcloud storage ls "gs://$DATA_BUCKET/chroma_db/" >/dev/null 2>&1 \
     && [ -n "$(gcloud storage ls "gs://$DATA_BUCKET/chroma_db/" 2>/dev/null | head -1)" ]; then
    echo "   zaten dolu: gs://$DATA_BUCKET/chroma_db (atlandı)"
  elif [ -d "$ROOT/data/chroma_db" ]; then
    gcloud storage rsync -r "$ROOT/data/chroma_db" "gs://$DATA_BUCKET/chroma_db"
    [ -f "$ROOT/data/final/all_decisions.parquet" ] && \
      gcloud storage cp "$ROOT/data/final/all_decisions.parquet" "gs://$DATA_BUCKET/all_decisions.parquet"
  else
    echo "   UYARI: lokalde $ROOT/data/chroma_db yok. Veriyi elle yükle (bkz. SENIN_YAPACAKLARIN.md)."
  fi
}

ph_dbusers() {
  echo "== Cloud SQL kullanıcıları =="
  for pair in "$DB_OWNER_USER:$DB_OWNER_PASSWORD" "$DB_APP_USER:$DB_APP_PASSWORD"; do
    u="${pair%%:*}"; p="${pair#*:}"
    [ -n "$p" ] && [ "$p" != "__DOLDUR__" ] || { echo "   HATA: $u parolası deploy.env'de boş"; exit 1; }
    if gcloud sql users list --instance="$SQL_INSTANCE_ID" --format='value(name)' | grep -qx "$u"; then
      gcloud sql users set-password "$u" --instance="$SQL_INSTANCE_ID" --password="$p"
      echo "   parola güncellendi: $u"
    else
      gcloud sql users create "$u" --instance="$SQL_INSTANCE_ID" --password="$p"
      echo "   oluşturuldu: $u"
    fi
  done
}

ph_secrets() {
  echo "== Secret Manager =="
  # boşsa otomatik üret
  : "${NEXTAUTH_SECRET:=}"; [ -z "$NEXTAUTH_SECRET" ] && NEXTAUTH_SECRET="$(openssl rand -base64 32)"
  : "${MASTER_ENCRYPTION_KEY:=}"; [ -z "$MASTER_ENCRYPTION_KEY" ] && MASTER_ENCRYPTION_KEY="$(openssl rand -base64 32)"
  # türetilen DSN'ler
  secret_put DATABASE_URL          "$DSN_APP"
  secret_put SERVICE_DATABASE_URL  "$DSN_OWNER"
  secret_put ADMIN_DATABASE_URL    "$DSN_OWNER"
  # üretilen anahtarlar
  secret_put NEXTAUTH_SECRET       "$NEXTAUTH_SECRET"
  secret_put MASTER_ENCRYPTION_KEY "$MASTER_ENCRYPTION_KEY"
  # secrets.env'den gelenler
  for s in ANTHROPIC_API_KEY GOOGLE_API_KEY \
           IYZICO_API_KEY IYZICO_SECRET_KEY IYZICO_WEBHOOK_SECRET \
           IYZICO_PLAN_PRO_SOLO IYZICO_PLAN_PRO_UYAP IYZICO_PLAN_TEAM IYZICO_PLAN_TEAM_UYAP \
           SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASS SMTP_FROM ADMIN_EMAIL; do
    secret_put "$s" "${!s:-}"
  done
}

ph_iam() {
  echo "== IAM (Cloud Build + runtime servis hesapları) =="
  local NUM CB RUNTIME
  NUM="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
  CB="${NUM}@cloudbuild.gserviceaccount.com"
  RUNTIME="${NUM}-compute@developer.gserviceaccount.com"   # varsayılan Compute SA (Cloud Run runtime)
  for ROLE in run.admin iam.serviceAccountUser cloudsql.client \
              secretmanager.secretAccessor artifactregistry.writer storage.objectViewer; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:$CB" --role="roles/$ROLE" --condition=None >/dev/null
  done
  for ROLE in cloudsql.client secretmanager.secretAccessor; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:$RUNTIME" --role="roles/$ROLE" --condition=None >/dev/null
  done
  # tenant-storage bucket'ında runtime'a yazma yetkisi
  gcloud storage buckets add-iam-policy-binding "gs://$TS_BUCKET" \
    --member="serviceAccount:$RUNTIME" --role="roles/storage.objectAdmin" >/dev/null
  echo "   bitti (CB=$CB, RUNTIME=$RUNTIME)"
}

ph_deploy() {
  echo "== Cloud Build → build + deploy (api + web) =="
  gcloud builds submit "$ROOT" --config "$ROOT/cloudbuild.yaml" \
    --substitutions=_REGION="$REGION",_AR_REPO="$AR_REPO",\
_DATA_BUCKET="$DATA_BUCKET",_TS_BUCKET="$TS_BUCKET",_SQL_INSTANCE="$SQL_CONN",\
_API_SERVICE="$API_SERVICE",_WEB_SERVICE="$WEB_SERVICE",\
_SITE_URL="$SITE_URL",_API_PUBLIC_URL="$API_PUBLIC_URL"
}

ph_verify() {
  echo "== Doğrulama =="
  local url
  url="$(gcloud run services describe "$API_SERVICE" --region="$REGION" --format='value(status.url)')"
  echo "   API URL: $url"
  echo "   /api/health:"
  curl -s "$url/api/health" || true; echo
  url="$(gcloud run services describe "$WEB_SERVICE" --region="$REGION" --format='value(status.url)' 2>/dev/null || true)"
  [ -n "$url" ] && echo "   WEB URL: $url"
}

# ---- dispatcher -------------------------------------------------------------
case "${1:-all}" in
  apis)     ph_apis ;;
  registry) ph_registry ;;
  buckets)  ph_buckets ;;
  data)     ph_data ;;
  dbusers)  ph_dbusers ;;
  secrets)  ph_secrets ;;
  iam)      ph_iam ;;
  deploy)   ph_deploy ;;
  verify)   ph_verify ;;
  all)
    ph_apis; ph_registry; ph_buckets; ph_data; ph_dbusers; ph_secrets; ph_iam
    echo
    echo ">> Kurulum tamam. ŞİMDİ migration çalıştır:  ./infra/gcp/migrate_db.sh"
    echo ">> Sonra deploy et:                          ./infra/gcp/setup_gcp.sh deploy"
    ;;
  *) echo "Bilinmeyen faz: $1"; echo "Fazlar: apis registry buckets data dbusers secrets iam deploy verify all"; exit 1 ;;
esac
