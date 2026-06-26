"""İçerik (blog/rehber) yönetimi — admin CMS + public yayın endpoint'leri.

Public:
  GET  /api/icerik/liste            → yayınlanan makaleler (özet liste)
  GET  /api/icerik/makale/{slug}    → yayınlanan tek makale

Admin (role=admin):
  GET    /api/icerik/admin/liste              → tümü (taslak dahil)
  GET    /api/icerik/admin/makale/{id}        → tek makale (id ile)
  POST   /api/icerik/admin/makale             → oluştur
  PUT    /api/icerik/admin/makale/{id}        → güncelle
  POST   /api/icerik/admin/makale/{id}/seo    → otomatik SEO üret + kaydet
  POST   /api/icerik/admin/makale/{id}/yayinla→ yayınla
  POST   /api/icerik/admin/makale/{id}/taslak → taslağa al
  DELETE /api/icerik/admin/makale/{id}        → sil

Tablo GLOBAL (RLS yok, bkz. infra/db/20_blog_articles.sql). Admin yazımları
service_session ile yapılır; public okuma yalnız status='published' filtreler.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from api.auth import CurrentUser, get_current_user
from api.cache import TTLCache
from api.concurrency import run_blocking
from api.db import db_session, service_session
from api.schemas import APIResponse
from services.seo_uret import makale_seo_uret, slugify, seo_skor_hesapla

log = logging.getLogger("api.icerik")
router = APIRouter()

# Public liste 5 dk cache (yayın sonrası kısa gecikme kabul edilebilir).
_liste_cache = TTLCache(maxsize=8, ttl=300)

_JSON_FIELDS = {"faq", "seo_notes"}


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(403, "Bu işlem yalnızca admin kullanıcılara açık.")
    return user


def _row(rec) -> dict:
    """asyncpg Record → dict; jsonb alanlarını parse et, keywords listesini garanti et."""
    d = dict(rec)
    for f in _JSON_FIELDS:
        v = d.get(f)
        if isinstance(v, str):
            try:
                d[f] = json.loads(v)
            except Exception:
                d[f] = []
    if d.get("keywords") is None:
        d["keywords"] = []
    return d


# ---------------------------------------------------------------------------
# Pydantic modelleri
# ---------------------------------------------------------------------------
class MakaleCreate(BaseModel):
    title: str
    body: str = ""
    slug: str | None = None
    excerpt: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    keywords: list[str] | None = None
    faq: list[dict] | None = None
    author: str | None = None
    cover_image: str | None = None


class MakaleUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    slug: str | None = None
    excerpt: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    keywords: list[str] | None = None
    faq: list[dict] | None = None
    author: str | None = None
    cover_image: str | None = None


# ---------------------------------------------------------------------------
# PUBLIC
# ---------------------------------------------------------------------------
@router.get("/liste", response_model=APIResponse, summary="Yayınlanan makaleler")
async def public_liste() -> APIResponse:
    cached = _liste_cache.get("pub")
    if cached is not None:
        return APIResponse(ok=True, data=cached)
    async with db_session() as conn:
        rows = await conn.fetch(
            """SELECT slug, title, excerpt, meta_description, keywords,
                      author, published_at
               FROM blog_articles
               WHERE status = 'published'
               ORDER BY published_at DESC NULLS LAST"""
        )
    data = [_row(r) for r in rows]
    _liste_cache.set("pub", data)
    return APIResponse(ok=True, data=data)


@router.get("/makale/{slug}", response_model=APIResponse, summary="Yayınlanan makale")
async def public_makale(slug: str = Path(..., min_length=1, max_length=120)) -> APIResponse:
    async with db_session() as conn:
        rec = await conn.fetchrow(
            """SELECT slug, title, excerpt, body, meta_title, meta_description,
                      keywords, faq, author, cover_image, published_at, updated_at
               FROM blog_articles
               WHERE slug = $1 AND status = 'published'""",
            slug,
        )
    if not rec:
        raise HTTPException(404, "Makale bulunamadı veya yayında değil.")
    return APIResponse(ok=True, data=_row(rec))


# ---------------------------------------------------------------------------
# ADMIN
# ---------------------------------------------------------------------------
@router.get("/admin/liste", response_model=APIResponse)
async def admin_liste(admin: CurrentUser = Depends(require_admin)) -> APIResponse:
    async with service_session() as conn:
        rows = await conn.fetch(
            """SELECT id, slug, title, excerpt, status, seo_score,
                      author, published_at, updated_at, created_at
               FROM blog_articles
               ORDER BY updated_at DESC"""
        )
    return APIResponse(ok=True, data=[_row(r) for r in rows])


@router.get("/admin/makale/{makale_id}", response_model=APIResponse)
async def admin_makale(
    makale_id: str = Path(...),
    admin: CurrentUser = Depends(require_admin),
) -> APIResponse:
    async with service_session() as conn:
        rec = await conn.fetchrow(
            "SELECT * FROM blog_articles WHERE id = $1::uuid", makale_id
        )
    if not rec:
        raise HTTPException(404, "Makale bulunamadı.")
    return APIResponse(ok=True, data=_row(rec))


@router.post("/admin/makale", response_model=APIResponse)
async def admin_olustur(
    payload: MakaleCreate,
    admin: CurrentUser = Depends(require_admin),
) -> APIResponse:
    if not payload.title.strip():
        raise HTTPException(422, "Başlık zorunlu.")
    slug = (payload.slug or "").strip() or slugify(payload.title)
    if not slug:
        raise HTTPException(422, "Geçerli bir slug üretilemedi.")

    makale = {
        "title": payload.title,
        "body": payload.body or "",
        "slug": slug,
        "meta_title": payload.meta_title,
        "meta_description": payload.meta_description,
        "keywords": payload.keywords or [],
        "faq": payload.faq or [],
    }
    skor, notlar = seo_skor_hesapla(makale)

    try:
        async with service_session() as conn:
            rec = await conn.fetchrow(
                """INSERT INTO blog_articles
                     (slug, title, excerpt, body, meta_title, meta_description,
                      keywords, faq, seo_score, seo_notes, author, cover_image)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10::jsonb,
                           COALESCE($11,'Hukukçu Yapay Zekası Editör Ekibi'),$12)
                   RETURNING *""",
                slug, payload.title, payload.excerpt, payload.body or "",
                payload.meta_title, payload.meta_description,
                payload.keywords or [], json.dumps(payload.faq or []),
                skor, json.dumps(notlar), payload.author, payload.cover_image,
            )
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, f"Bu slug zaten kullanılıyor: {slug}")
        log.exception("Makale oluşturma hatası")
        raise HTTPException(500, str(e))
    return APIResponse(ok=True, data=_row(rec), message="Makale oluşturuldu (taslak).")


@router.put("/admin/makale/{makale_id}", response_model=APIResponse)
async def admin_guncelle(
    makale_id: str,
    payload: MakaleUpdate,
    admin: CurrentUser = Depends(require_admin),
) -> APIResponse:
    alanlar = payload.model_dump(exclude_unset=True)
    if not alanlar:
        return APIResponse(ok=True, message="Değişiklik yok.")

    sets: list[str] = []
    args: list = []

    def add(col: str, val, cast: str = ""):
        args.append(val)
        sets.append(f"{col} = ${len(args)}{cast}")

    for col in ("title", "body", "excerpt", "meta_title", "meta_description",
                "author", "cover_image", "slug"):
        if col in alanlar:
            add(col, alanlar[col])
    if "keywords" in alanlar:
        add("keywords", alanlar["keywords"] or [])
    if "faq" in alanlar:
        add("faq", json.dumps(alanlar["faq"] or []), "::jsonb")

    sets.append("updated_at = NOW()")
    args.append(makale_id)

    try:
        async with service_session() as conn:
            rec = await conn.fetchrow(
                f"UPDATE blog_articles SET {', '.join(sets)} "
                f"WHERE id = ${len(args)}::uuid RETURNING *",
                *args,
            )
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Bu slug başka makalede kullanılıyor.")
        log.exception("Makale güncelleme hatası")
        raise HTTPException(500, str(e))
    if not rec:
        raise HTTPException(404, "Makale bulunamadı.")
    _liste_cache.clear()
    return APIResponse(ok=True, data=_row(rec), message="Makale güncellendi.")


@router.post("/admin/makale/{makale_id}/seo", response_model=APIResponse)
async def admin_seo_uret(
    makale_id: str,
    admin: CurrentUser = Depends(require_admin),
) -> APIResponse:
    """Makalenin başlık+gövdesinden otomatik SEO alanlarını üretip kaydeder."""
    async with service_session() as conn:
        rec = await conn.fetchrow(
            "SELECT title, body, slug FROM blog_articles WHERE id = $1::uuid",
            makale_id,
        )
        if not rec:
            raise HTTPException(404, "Makale bulunamadı.")

        seo = await run_blocking(
            makale_seo_uret, rec["title"], rec["body"] or "", rec["slug"])

        updated = await conn.fetchrow(
            """UPDATE blog_articles
               SET meta_title = $1, meta_description = $2, keywords = $3,
                   faq = $4::jsonb, seo_score = $5, seo_notes = $6::jsonb,
                   updated_at = NOW()
               WHERE id = $7::uuid
               RETURNING *""",
            seo["meta_title"], seo["meta_description"], seo["keywords"],
            json.dumps(seo["faq"]), seo["seo_score"], json.dumps(seo["seo_notes"]),
            makale_id,
        )
    _liste_cache.clear()
    return APIResponse(
        ok=True, data=_row(updated),
        message=f"SEO üretildi ({seo['kaynak']}). Skor: {seo['seo_score']}/100",
    )


@router.post("/admin/makale/{makale_id}/yayinla", response_model=APIResponse)
async def admin_yayinla(
    makale_id: str,
    admin: CurrentUser = Depends(require_admin),
) -> APIResponse:
    async with service_session() as conn:
        rec = await conn.fetchrow(
            """UPDATE blog_articles
               SET status = 'published',
                   published_at = COALESCE(published_at, NOW()),
                   updated_at = NOW()
               WHERE id = $1::uuid
               RETURNING slug, status, published_at""",
            makale_id,
        )
    if not rec:
        raise HTTPException(404, "Makale bulunamadı.")
    _liste_cache.clear()
    return APIResponse(ok=True, data=_row(rec), message="Makale yayınlandı.")


@router.post("/admin/makale/{makale_id}/taslak", response_model=APIResponse)
async def admin_taslak(
    makale_id: str,
    admin: CurrentUser = Depends(require_admin),
) -> APIResponse:
    async with service_session() as conn:
        rec = await conn.fetchrow(
            """UPDATE blog_articles SET status = 'draft', updated_at = NOW()
               WHERE id = $1::uuid RETURNING slug, status""",
            makale_id,
        )
    if not rec:
        raise HTTPException(404, "Makale bulunamadı.")
    _liste_cache.clear()
    return APIResponse(ok=True, data=_row(rec), message="Makale taslağa alındı.")


@router.delete("/admin/makale/{makale_id}", response_model=APIResponse)
async def admin_sil(
    makale_id: str,
    admin: CurrentUser = Depends(require_admin),
) -> APIResponse:
    async with service_session() as conn:
        rec = await conn.fetchrow(
            "DELETE FROM blog_articles WHERE id = $1::uuid RETURNING id", makale_id
        )
    if not rec:
        raise HTTPException(404, "Makale bulunamadı.")
    _liste_cache.clear()
    return APIResponse(ok=True, message="Makale silindi.")
