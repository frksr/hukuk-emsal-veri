"""Publisher API v1 — blog paylaşım otomasyonu.

Dış sistemler (örn. claude-blog-automation) taslak gönderir; taslak
`status='pending'` kaydedilir ve admin'e onay maili atılır. Maildeki iki
adımlı akışla (onay sayfası → 'Yayınla' butonu) yazı yayınlanır.

Kimlik doğrulama:
  - /drafts (POST, GET), /health : Authorization: Bearer <PUBLISHER_API_KEY>
  - /approve, /reject            : URL'deki tek kullanımlık token (API key YOK)
  - /preview/{id}                : tahmin edilemez preview_id (kimlik YOK, noindex)

Tek dilli (TR). Şema için bkz. infra/db/27_publisher.sql.

Uçlar:
  POST /api/publisher/drafts               → taslak al, kaydet, onay maili gönder
  GET  /api/publisher/approve              → iki adımlı onay sayfası (yayınlamaz)
  POST /api/publisher/approve              → yayınla (onay sayfasındaki buton)
  GET  /api/publisher/reject               → iki adımlı red sayfası
  POST /api/publisher/reject               → reddet
  GET  /api/publisher/drafts/{draft_id}    → durum sorgu (Bearer)
  GET  /api/publisher/preview/{preview_id} → önizleme verisi (frontend için)
  GET  /api/publisher/health               → bağlantı testi (Bearer)
"""
from __future__ import annotations

import base64
import hmac
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Path, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from api.concurrency import run_blocking
from api.db import service_session
from api.deps import rate_limit
from services.blog_storage import upload_blog_image
from services.seo_uret import seo_skor_hesapla, slugify

log = logging.getLogger("api.publisher")
router = APIRouter()

TOKEN_TTL_DAYS = 7
MAX_TOTAL_IMAGE_BYTES = 15 * 1024 * 1024  # gövde/görsel toplam üst sınırı
SITE_NAME = os.environ.get("SITE_NAME", "Hukukçu Yapay Zekası")

_EXT_CONTENT_TYPE = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "gif": "image/gif", "svg": "image/svg+xml",
}


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _site_url() -> str:
    return os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukcuyapayzekasi.com").rstrip("/")


def _api_base() -> str:
    """Onay/red maillerindeki linkler için herkese açık API kökü."""
    base = (
        os.environ.get("PUBLISHER_PUBLIC_URL")
        or os.environ.get("NEXT_PUBLIC_API_URL")
        or _site_url()
    )
    return base.rstrip("/")


def _admin_email() -> str | None:
    return os.environ.get("ADMIN_EMAIL") or os.environ.get("FEEDBACK_ADMIN_EMAIL")


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    """Bearer API key — constant-time karşılaştırma. Yanlış/eksik → 401."""
    key = os.environ.get("PUBLISHER_API_KEY", "")
    if not key:
        raise HTTPException(503, "Publisher API yapılandırılmamış (PUBLISHER_API_KEY yok).")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Yetkisiz.")
    supplied = authorization[len("Bearer "):]
    if not hmac.compare_digest(supplied, key):
        raise HTTPException(401, "Yetkisiz.")


def _guess_content_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _EXT_CONTENT_TYPE.get(ext, "image/png")


def _decode_b64(data: str) -> bytes:
    """base64 (opsiyonel data-URL önekiyle) → bytes. Hatalıysa 422."""
    if data.startswith("data:"):
        _, _, data = data.partition(",")
    try:
        return base64.b64decode(data, validate=True)
    except Exception:
        raise HTTPException(422, "Görsel base64 çözülemedi.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _html_page(title: str, message: str, link: tuple[str, str] | None = None,
               status_code: int = 200) -> HTMLResponse:
    link_html = ""
    if link:
        url, label = link
        link_html = (
            f'<p style="margin-top:24px;"><a href="{url}" style="display:inline-block;'
            f'padding:12px 24px;background:#1e3a5f;color:#fff;text-decoration:none;'
            f'border-radius:6px;font-weight:600;">{label}</a></p>'
        )
    html = f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>{title}</title></head>
<body style="font-family:-apple-system,Segoe UI,Arial,sans-serif;background:#f5f5f7;
margin:0;padding:48px 16px;text-align:center;color:#333;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:10px;padding:40px;">
<h1 style="color:#1e3a5f;font-size:22px;">{title}</h1>
<div style="line-height:1.6;font-size:15px;">{message}</div>{link_html}
</div></body></html>"""
    return HTMLResponse(content=html, status_code=status_code)


def _confirm_page(action_path: str, draft_id: str, token: str, title: str,
                  btn_label: str, btn_color: str, heading: str) -> HTMLResponse:
    """İki adımlı akış: butona basınca POST eder (mail ön-taraması yayına yol açmaz)."""
    html = f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>{heading}</title></head>
<body style="font-family:-apple-system,Segoe UI,Arial,sans-serif;background:#f5f5f7;
margin:0;padding:48px 16px;text-align:center;color:#333;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:10px;padding:40px;">
<h1 style="color:#1e3a5f;font-size:22px;">{heading}</h1>
<p style="line-height:1.6;font-size:16px;"><strong>{title}</strong></p>
<form method="POST" action="{action_path}">
<input type="hidden" name="draft_id" value="{draft_id}">
<input type="hidden" name="token" value="{token}">
<button type="submit" style="margin-top:16px;padding:14px 32px;background:{btn_color};
color:#fff;border:none;border-radius:6px;font-weight:600;font-size:15px;cursor:pointer;">
{btn_label}</button>
</form></div></body></html>"""
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# İstek modelleri
# ---------------------------------------------------------------------------
class ImageIn(BaseModel):
    filename: str
    alt: str | None = None
    data_base64: str


class FaqIn(BaseModel):
    q: str
    a: str


class DraftIn(BaseModel):
    title: str = Field(..., min_length=1)
    body_markdown: str = Field(..., min_length=1)
    meta_description: str = Field(..., min_length=1)
    cover_image: ImageIn
    slug: str | None = None
    excerpt: str | None = None
    keyword: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    faq: list[FaqIn] = Field(default_factory=list)
    images: list[ImageIn] = Field(default_factory=list)
    author: str | None = None
    source: str | None = None
    sent_at: str | None = None


# ---------------------------------------------------------------------------
# 1) POST /drafts
# ---------------------------------------------------------------------------
@router.post("/drafts", dependencies=[Depends(require_api_key), Depends(rate_limit)])
async def create_draft(payload: DraftIn) -> dict:
    slug = (payload.slug or "").strip() or slugify(payload.title)
    if not slug or not re.fullmatch(r"[a-z0-9-]+", slug):
        raise HTTPException(422, "Geçerli bir slug üretilemedi.")

    # --- Görselleri çöz + boyut kontrolü ---
    coden = [("cover", payload.cover_image)] + [("body", im) for im in payload.images]
    decoded: list[tuple[str, ImageIn, bytes]] = []
    total = 0
    for kind, im in coden:
        raw = _decode_b64(im.data_base64)
        total += len(raw)
        if total > MAX_TOTAL_IMAGE_BYTES:
            raise HTTPException(413, "Toplam görsel boyutu 15 MB sınırını aştı.")
        decoded.append((kind, im, raw))

    # --- Görselleri yükle, body içindeki images/... yollarını URL'e çevir ---
    body = payload.body_markdown
    cover_url: str | None = None
    for kind, im, raw in decoded:
        try:
            url = await run_blocking(
                upload_blog_image, raw, im.filename, _guess_content_type(im.filename)
            )
        except Exception as e:
            log.exception("Publisher görsel yükleme hatası")
            raise HTTPException(500, f"Görsel yüklenemedi: {im.filename}")
        if kind == "cover":
            cover_url = url
        else:
            # ![alt](images/gorsel-1.png) → ![alt](<gcs-url>)
            body = body.replace(f"images/{im.filename}", url)

    # --- FAQ {q,a} → {soru,cevap}; keywords = keyword + tags ---
    faq = [{"soru": f.q, "cevap": f.a} for f in payload.faq if f.q and f.a]
    keywords: list[str] = []
    for kw in ([payload.keyword] if payload.keyword else []) + payload.tags:
        kw = (kw or "").strip()
        if kw and kw not in keywords:
            keywords.append(kw)

    skor, notlar = seo_skor_hesapla({
        "meta_title": payload.title, "title": payload.title,
        "meta_description": payload.meta_description, "keywords": keywords,
        "body": body, "faq": faq, "slug": slug,
    })

    approve_token = secrets.token_urlsafe(32)
    reject_token = secrets.token_urlsafe(32)
    preview_id = secrets.token_urlsafe(24)
    expires_at = _now() + timedelta(days=TOKEN_TTL_DAYS)

    import json as _json
    async with service_session() as conn:
        existing = await conn.fetchrow(
            "SELECT id, status FROM blog_articles WHERE slug = $1", slug
        )
        if existing and existing["status"] == "published":
            raise HTTPException(409, f"Bu slug zaten yayında: {slug}")

        cols_vals = dict(
            title=payload.title, excerpt=payload.excerpt, body=body,
            meta_title=payload.title, meta_description=payload.meta_description,
            keywords=keywords, faq=_json.dumps(faq), seo_score=skor,
            seo_notes=_json.dumps(notlar),
            author=payload.author or "Hukukçu Yapay Zekası Editör Ekibi",
            cover_image=cover_url, category=payload.category, tags=payload.tags,
            target_keyword=payload.keyword, source=payload.source,
            status="pending", approve_token=approve_token, reject_token=reject_token,
            token_expires_at=expires_at, preview_id=preview_id, reject_reason=None,
            published_at=None,
        )

        # jsonb kolonları metin parametreyle gelir; ::jsonb cast'i şart.
        jsonb_cols = {"faq", "seo_notes"}

        if existing:
            # Idempotency: bekleyen/taslak/red/expired taslağı üzerine yaz (yeni token).
            cols = list(cols_vals.keys())
            sets = ", ".join(
                f"{c} = ${i+1}{'::jsonb' if c in jsonb_cols else ''}"
                for i, c in enumerate(cols)
            )
            args = list(cols_vals.values())
            args.append(existing["id"])
            rec = await conn.fetchrow(
                f"UPDATE blog_articles SET {sets}, updated_at = NOW() "
                f"WHERE id = ${len(args)}::uuid RETURNING id",
                *args,
            )
            code = 200
        else:
            cols_vals["slug"] = slug
            cols = list(cols_vals.keys())
            placeholders = ", ".join(
                f"${i+1}{'::jsonb' if c in jsonb_cols else ''}"
                for i, c in enumerate(cols)
            )
            rec = await conn.fetchrow(
                f"INSERT INTO blog_articles ({', '.join(cols)}) "
                f"VALUES ({placeholders}) RETURNING id",
                *list(cols_vals.values()),
            )
            code = 201

    draft_id = str(rec["id"])
    preview_url = f"{_site_url()}/preview/{preview_id}"
    approve_url = f"{_api_base()}/api/publisher/approve?draft_id={draft_id}&token={approve_token}"
    reject_url = f"{_api_base()}/api/publisher/reject?draft_id={draft_id}&token={reject_token}"
    expires_iso = expires_at.isoformat()

    # --- Onay maili (hata taslağı DÜŞÜRMEZ) ---
    admin = _admin_email()
    if admin:
        try:
            from services.email import send_publish_approval_email
            await send_publish_approval_email(
                to=admin, site_name=SITE_NAME, title=payload.title,
                meta_description=payload.meta_description, keyword=payload.keyword,
                preview_url=preview_url, approve_url=approve_url, reject_url=reject_url,
                expires_at=expires_at.strftime("%d.%m.%Y %H:%M"),
            )
        except Exception:
            log.exception("Onay maili gönderilemedi (taslak yine de kaydedildi)")
    else:
        log.warning("ADMIN_EMAIL tanımlı değil — onay maili gönderilemedi.")

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=code,
        content={
            "draft_id": draft_id, "status": "pending",
            "preview_url": preview_url, "expires_at": expires_iso,
        },
    )


# ---------------------------------------------------------------------------
# 2) Onay — iki adımlı
# ---------------------------------------------------------------------------
async def _load_by_token(conn, draft_id: str, token: str, field: str):
    try:
        rec = await conn.fetchrow(
            f"SELECT id, slug, title, status, {field}, token_expires_at "
            f"FROM blog_articles WHERE id = $1::uuid",
            draft_id,
        )
    except Exception:
        return None, "invalid"
    if not rec or not rec[field]:
        return None, "invalid"
    if not hmac.compare_digest(str(rec[field]), token):
        return None, "invalid"
    if rec["status"] not in ("pending",):
        return rec, "used"
    if rec["token_expires_at"] and rec["token_expires_at"] < _now():
        return rec, "expired"
    return rec, "ok"


@router.get("/approve", response_class=HTMLResponse)
async def approve_page(draft_id: str, token: str) -> HTMLResponse:
    async with service_session() as conn:
        rec, state = await _load_by_token(conn, draft_id, token, "approve_token")
    if state == "invalid":
        return _html_page("Geçersiz bağlantı", "Bu onay bağlantısı geçerli değil.", status_code=410)
    if state == "used":
        return _html_page("Zaten işlendi", "Bu taslak zaten yayınlanmış veya işlenmiş.", status_code=410)
    if state == "expired":
        return _html_page("Süresi doldu", "Bu onay bağlantısının süresi dolmuş.", status_code=410)
    return _confirm_page(
        "/api/publisher/approve", draft_id, token, rec["title"],
        "✅ Yayınla", "#15803d", "Yazıyı yayınlamak üzeresiniz",
    )


@router.post("/approve", response_class=HTMLResponse)
async def approve_publish(draft_id: str = Form(...), token: str = Form(...)) -> HTMLResponse:
    async with service_session() as conn:
        rec, state = await _load_by_token(conn, draft_id, token, "approve_token")
        if state == "invalid":
            return _html_page("Geçersiz bağlantı", "Bu onay bağlantısı geçerli değil.", status_code=410)
        if state == "used":
            return _html_page("Zaten işlendi", "Bu taslak zaten işlenmiş.", status_code=410)
        if state == "expired":
            return _html_page("Süresi doldu", "Bu onay bağlantısının süresi dolmuş.", status_code=410)
        await conn.execute(
            """UPDATE blog_articles
               SET status='published', published_at=COALESCE(published_at, NOW()),
                   approve_token=NULL, reject_token=NULL, updated_at=NOW()
               WHERE id=$1::uuid""",
            draft_id,
        )
    # Public liste cache'ini temizle (icerik router ile paylaşımlı davranış).
    try:
        from api.routers.icerik import _liste_cache
        _liste_cache.clear()
    except Exception:
        pass
    live = f"{_site_url()}/blog/{rec['slug']}"
    log.info("Publisher: taslak yayınlandı slug=%s", rec["slug"])
    return _html_page("✅ Yayınlandı", "Yazı canlıya alındı.", link=(live, "Canlı yazıyı gör"))


# ---------------------------------------------------------------------------
# 3) Red — iki adımlı
# ---------------------------------------------------------------------------
@router.get("/reject", response_class=HTMLResponse)
async def reject_page(draft_id: str, token: str) -> HTMLResponse:
    async with service_session() as conn:
        rec, state = await _load_by_token(conn, draft_id, token, "reject_token")
    if state == "invalid":
        return _html_page("Geçersiz bağlantı", "Bu red bağlantısı geçerli değil.", status_code=410)
    if state == "used":
        return _html_page("Zaten işlendi", "Bu taslak zaten işlenmiş.", status_code=410)
    if state == "expired":
        return _html_page("Süresi doldu", "Bu bağlantının süresi dolmuş.", status_code=410)
    return _confirm_page(
        "/api/publisher/reject", draft_id, token, rec["title"],
        "❌ Reddet", "#b91c1c", "Yazıyı reddetmek üzeresiniz",
    )


@router.post("/reject", response_class=HTMLResponse)
async def reject_do(draft_id: str = Form(...), token: str = Form(...),
                    reason: str | None = Form(default=None)) -> HTMLResponse:
    async with service_session() as conn:
        rec, state = await _load_by_token(conn, draft_id, token, "reject_token")
        if state == "invalid":
            return _html_page("Geçersiz bağlantı", "Bu red bağlantısı geçerli değil.", status_code=410)
        if state == "used":
            return _html_page("Zaten işlendi", "Bu taslak zaten işlenmiş.", status_code=410)
        if state == "expired":
            return _html_page("Süresi doldu", "Bu bağlantının süresi dolmuş.", status_code=410)
        await conn.execute(
            """UPDATE blog_articles
               SET status='rejected', reject_reason=$2,
                   approve_token=NULL, reject_token=NULL, updated_at=NOW()
               WHERE id=$1::uuid""",
            draft_id, reason,
        )
    log.info("Publisher: taslak reddedildi slug=%s", rec["slug"])
    return _html_page("Reddedildi", "Taslak reddedildi, yayınlanmadı.")


# ---------------------------------------------------------------------------
# 4) Durum sorgu (Bearer)
# ---------------------------------------------------------------------------
@router.get("/drafts/{draft_id}", dependencies=[Depends(require_api_key)])
async def draft_status(draft_id: str = Path(...)) -> dict:
    async with service_session() as conn:
        try:
            rec = await conn.fetchrow(
                "SELECT slug, status, published_at FROM blog_articles WHERE id=$1::uuid",
                draft_id,
            )
        except Exception:
            raise HTTPException(404, "Taslak bulunamadı.")
    if not rec:
        raise HTTPException(404, "Taslak bulunamadı.")
    out: dict = {"draft_id": draft_id, "status": rec["status"]}
    if rec["status"] == "published":
        out["published_url"] = f"{_site_url()}/blog/{rec['slug']}"
        out["published_at"] = rec["published_at"].isoformat() if rec["published_at"] else None
    return out


# ---------------------------------------------------------------------------
# 5) Önizleme verisi (frontend /preview/[id] için — kimliksiz, tahmin edilemez)
# ---------------------------------------------------------------------------
@router.get("/preview/{preview_id}")
async def preview_data(preview_id: str = Path(..., min_length=8)) -> dict:
    async with service_session() as conn:
        rec = await conn.fetchrow(
            """SELECT slug, title, excerpt, body, meta_description, keywords, faq,
                      author, cover_image, status
               FROM blog_articles WHERE preview_id=$1""",
            preview_id,
        )
    if not rec:
        raise HTTPException(404, "Önizleme bulunamadı.")
    import json as _json
    d = dict(rec)
    if isinstance(d.get("faq"), str):
        try:
            d["faq"] = _json.loads(d["faq"])
        except Exception:
            d["faq"] = []
    return {"ok": True, "data": d}


# ---------------------------------------------------------------------------
# 6) Health (Bearer)
# ---------------------------------------------------------------------------
@router.get("/health", dependencies=[Depends(require_api_key)])
async def health() -> dict:
    return {"ok": True, "service": "publisher", "version": "1"}
