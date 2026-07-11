"""Blog görselleri — herkese açık (public-read) GCS bucket'a yükleme.

Kapak görseli ve makale gövdesi içindeki resimler buradan geçer. Bu, UYAP
belgeleri için kullanılan `services/tenant_storage.py`'den KASITLI olarak
ayrı: o bucket özel/şifreli (avukat-müvekkil belgeleri), ASLA public
yapılmamalı. Blog görselleri zaten public sayfada gösteriliyor, gizlilik
gerektirmiyor.

YENİ bucket açmak yerine mevcut `hukuk-emsal-bucket` (RAG tohum verisi —
chroma_db/parquet, çalışma zamanında hiçbir container'a mount edilmiyor,
yalnızca Cloud Build'in fetch-data adımında okunuyor) yeniden kullanılıyor;
görseller onun altında ayrı bir `blog/` prefix'inde tutulur ve YALNIZCA o
prefix IAM condition ile public yapılır — parquet/chroma_db verisi private
kalır.

Ortam değişkeni:
  BLOG_IMAGES_BUCKET — bucket adı (varsayılan: hukuk-emsal-bucket)

Bucket kurulumu (bir kerelik, GCP tarafında — bu kod bunu YAPMAZ):
  gcloud storage buckets update gs://hukuk-emsal-bucket --uniform-bucket-level-access

  # Yalnızca blog/ prefix'ini herkese açık yap (parquet/chroma_db private kalır):
  gcloud storage buckets add-iam-policy-binding gs://hukuk-emsal-bucket \\
    --member=allUsers --role=roles/storage.objectViewer \\
    --condition='expression=resource.name.startsWith("projects/_/buckets/hukuk-emsal-bucket/objects/blog/"),title=public-blog-only'

  # Cloud Run runtime servis hesabına bu bucket'ta yazma izni:
  gcloud storage buckets add-iam-policy-binding gs://hukuk-emsal-bucket \\
    --member=serviceAccount:971380818626-compute@developer.gserviceaccount.com \\
    --role=roles/storage.objectAdmin
"""
from __future__ import annotations

import logging
import os
import uuid

log = logging.getLogger("services.blog_storage")

BLOG_IMAGES_BUCKET = os.environ.get("BLOG_IMAGES_BUCKET", "hukuk-emsal-bucket")
BLOG_IMAGE_PREFIX = "blog"  # bucket paylaşımlı — yalnızca bu prefix public
BLOG_IMAGE_MAX_SIZE = 8 * 1024 * 1024  # 8 MB — kapak/gövde görseli için yeterli

_EXT_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
}
_ALLOWED_EXT = set(_EXT_BY_CONTENT_TYPE.values())


def _guess_ext(filename: str, content_type: str | None) -> str:
    name_ext = (filename.rsplit(".", 1)[-1].lower() if "." in filename else "")
    if name_ext in _ALLOWED_EXT:
        return name_ext
    return _EXT_BY_CONTENT_TYPE.get(content_type or "", "jpg")


def upload_blog_image(content: bytes, filename: str, content_type: str | None) -> str:
    """Senkron (bloklayıcı) — çağıran taraf `run_blocking` ile sarmalamalı.

    Yükler ve herkese açık URL döner. Bucket zaten uniform bucket-level access
    + allUsers:objectViewer IAM ile public olmalı; bu yüzden ayrıca
    `blob.make_public()` ÇAĞRILMAZ (o, object-ACL modunu gerektirir ve
    uniform-access bucket'ta hata verir).
    """
    from google.cloud import storage  # lazy import — yalnızca bu yol kullanınca gerekli

    ext = _guess_ext(filename or "gorsel", content_type)
    blob_name = f"{BLOG_IMAGE_PREFIX}/uploads/{uuid.uuid4().hex}.{ext}"

    client = storage.Client()
    bucket = client.bucket(BLOG_IMAGES_BUCKET)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(
        content, content_type=content_type or "application/octet-stream"
    )
    log.info("Blog görseli yüklendi: %s (%d bytes)", blob_name, len(content))
    return f"https://storage.googleapis.com/{BLOG_IMAGES_BUCKET}/{blob_name}"
