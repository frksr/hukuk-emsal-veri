"""Kullanıcı kendi profili + kullanım + tenant + hesap silme."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from api.audit import audit
from api.auth import CurrentUser, get_current_user
from api.db import db_session
from api.schemas import APIResponse
from services import krediler

router = APIRouter()


@router.get("/krediler", response_model=APIResponse, summary="Modül bazlı kredi bakiyeleri")
async def kredilerim(user: CurrentUser = Depends(get_current_user)):
    """Kullanıcının ek paket kredileri (modül bazlı bakiye) + son hareketler."""
    bakiyeler = await krediler.tum_bakiyeler(user.user_id)
    hareketler = await krediler.hareketler(user.user_id, limit=30)
    return APIResponse(ok=True, data={
        "bakiyeler": [
            {"module": m, "modul_etiket": krediler.MODUL_ETIKET.get(m, m), "balance": b}
            for m, b in sorted(bakiyeler.items())
        ],
        "hareketler": hareketler,
    })


@router.get("/", response_model=APIResponse)
async def me(user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT email_verified, kvkk_accepted_at, marketing_consent,
                      history_enabled, billing, created_at, last_login_at,
                      onboarding_done
               FROM users WHERE id = $1""",
            user.user_id,
        )
    import json as _json
    _billing = {}
    if row and row["billing"]:
        _billing = row["billing"] if isinstance(row["billing"], dict) else _json.loads(row["billing"])
    return APIResponse(ok=True, data={
        "user": {
            "id": user.user_id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "email_verified": bool(row and row["email_verified"]),
            "marketing_consent": bool(row and row["marketing_consent"]),
            "history_enabled": bool(row["history_enabled"]) if row and row["history_enabled"] is not None else True,
            "onboarding_done": bool(row and row["onboarding_done"]),
            "billing": _billing,
            "created_at": row["created_at"].isoformat() if row else None,
            "last_login_at": row["last_login_at"].isoformat() if row and row["last_login_at"] else None,
        },
        "tenant": {
            "id": user.tenant_id,
            "plan": user.tenant_plan,
            "role": user.tenant_role,
        } if user.tenant_id else None,
    })


class UpdateProfileReq(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    marketing_consent: bool | None = None
    history_enabled: bool | None = None
    # Onboarding turu tamamlandı/geçildi bayrağı (panel ilk giriş turu)
    onboarding_done: bool | None = None
    # Fatura bilgileri (profil): {unvan, vergi_no, vergi_dairesi, adres, sehir, posta, telefon}
    billing: dict | None = None


@router.patch("/", response_model=APIResponse)
async def update_profile(
    payload: UpdateProfileReq,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    updates = []
    args: list = []
    if payload.name is not None:
        updates.append(f"name = ${len(args) + 1}")
        args.append(payload.name)
    if payload.marketing_consent is not None:
        updates.append(f"marketing_consent = ${len(args) + 1}")
        args.append(payload.marketing_consent)
    if payload.history_enabled is not None:
        updates.append(f"history_enabled = ${len(args) + 1}")
        args.append(payload.history_enabled)
    if payload.onboarding_done is not None:
        updates.append(f"onboarding_done = ${len(args) + 1}")
        args.append(payload.onboarding_done)
    if payload.billing is not None:
        import json as _json
        # Yalnızca beklenen alanları al (güvenlik), stringe çevir.
        izinli = {"unvan", "vergi_no", "vergi_dairesi", "adres", "sehir", "posta", "telefon"}
        temiz = {k: str(v)[:300] for k, v in payload.billing.items() if k in izinli and v is not None}
        updates.append(f"billing = ${len(args) + 1}::jsonb")
        args.append(_json.dumps(temiz, ensure_ascii=False))
    if not updates:
        return APIResponse(ok=True, message="Değişiklik yok.")

    args.append(user.user_id)
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        await conn.execute(
            f"UPDATE users SET {', '.join(updates)}, updated_at = NOW() "
            f"WHERE id = ${len(args)}",
            *args,
        )

    await audit(action="profile.updated", user_id=user.user_id, request=request)
    return APIResponse(ok=True, message="Profil güncellendi.")


@router.get("/rapor", response_model=APIResponse)
async def kullanim_raporu(user: CurrentUser = Depends(get_current_user)):
    """Dinamik kullanım raporu — her araç için toplam/30g/7g kullanım sayısı.

    usage_events (her AI kullanımı + arama) + generated_documents + user_searches'ten
    beslenir; kullanıcı bir özelliği kullandığında anında yansır.
    """
    now = datetime.now(timezone.utc)
    # Kota penceresi: ücretli kullanıcı için abonelik gününe, free için kayıt
    # gününe demirlenmiş AYLIK pencere (kota.py ile birebir aynı mantık).
    from api.rate_limit import kullanici_donem_penceresi
    d1, donem_bitis, _ = await kullanici_donem_penceresi(user.user_id, user.tenant_id)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        toplam = await conn.fetch(
            "SELECT event_type, COUNT(*) c FROM usage_events WHERE user_id=$1 GROUP BY event_type",
            user.user_id,
        )
        s30 = await conn.fetch(
            "SELECT event_type, COUNT(*) c FROM usage_events WHERE user_id=$1 AND created_at>$2 GROUP BY event_type",
            user.user_id, d30,
        )
        s7 = await conn.fetch(
            "SELECT event_type, COUNT(*) c FROM usage_events WHERE user_id=$1 AND created_at>$2 GROUP BY event_type",
            user.user_id, d7,
        )
        # Bu ay (takvim ayı başından) — aylık plan kotasından kalanı hesaplamak için.
        s1 = await conn.fetch(
            "SELECT event_type, COUNT(*) c FROM usage_events WHERE user_id=$1 AND created_at>=$2 GROUP BY event_type",
            user.user_id, d1,
        )
        uretim_toplam = await conn.fetchval(
            "SELECT COUNT(*) FROM generated_documents WHERE user_id=$1", user.user_id,
        )
        arama_toplam = await conn.fetchval(
            "SELECT COUNT(*) FROM user_searches WHERE user_id=$1", user.user_id,
        )

    from api.rate_limit import tool_daily_limit
    from services import app_config

    # Plan limit override (admin panelden ayarlanabilir) — bir kez çek.
    override = await app_config.get_plan_limits()

    tmap = {r["event_type"]: r["c"] for r in toplam}
    m30 = {r["event_type"]: r["c"] for r in s30}
    m7 = {r["event_type"]: r["c"] for r in s7}
    m1 = {r["event_type"]: r["c"] for r in s1}
    araclar = ["arama", "dilekce", "ihtarname", "ozet", "denetim",
               "karsi_argument", "sozlesme", "kvkk", "faiz", "zamanasimi"]
    for ev in tmap:
        if ev not in araclar:
            araclar.append(ev)

    # Modül bazlı ek-paket kredi bakiyeleri (kalan kullanım hakları) — rapora yansır.
    kredi_bakiyeleri = await krediler.tum_bakiyeler(user.user_id)

    # Her araç için kalan = AYLIK plan limitinden kalan (bu ay) + ek-paket kredisi.
    # Pahalı araçlar (sözleşme) Pro'da bile plan limitine tabidir; diğer AI araçları
    # Pro+ sınırsız; faiz/zamanaşımı pratikte sınırsız. Ek paket kredisi süresizdir.
    # Admin → sistemi izleyen ana kullanıcı, her şey sınırsız (enterprise).
    tier = "enterprise" if user.role == "admin" else (user.tenant_plan or "free")

    def _kalan(tool: str) -> dict:
        kredi = kredi_bakiyeleri.get(tool, 0)
        limit = tool_daily_limit(tier, tool, override)  # None → sınırsız
        if limit is None or limit >= 10_000:
            return {"sinirsiz": True, "plan_kalan": None, "kalan_toplam": None}
        plan_kalan = max(int(limit) - m1.get(tool, 0), 0)
        return {"sinirsiz": False, "plan_kalan": plan_kalan,
                "gunluk_limit": int(limit), "kalan_toplam": plan_kalan + kredi}

    breakdown = [
        {
            "tool": t,
            "toplam": tmap.get(t, 0),
            "son30": m30.get(t, 0),
            "son7": m7.get(t, 0),
            "kredi": kredi_bakiyeleri.get(t, 0),
            **_kalan(t),
        }
        for t in araclar
    ]
    return APIResponse(ok=True, data={
        "tier": tier,
        "uretim_toplam": uretim_toplam or 0,
        "arama_toplam": arama_toplam or 0,
        "toplam_kullanim": sum(tmap.values()),
        "araclar": breakdown,
        "krediler": kredi_bakiyeleri,
        "donem_bitis": donem_bitis.isoformat(),
        "guncel": now.isoformat(),
    })


@router.get("/usage", response_model=APIResponse)
async def usage_stats(user: CurrentUser = Depends(get_current_user)):
    """Tier'a göre limitler + gerçek kullanım."""
    from api.rate_limit import DAILY_LIMITS, UNLIMITED_TIERS

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    month_ago = now - timedelta(days=30)

    tier = user.tenant_plan or "free"
    unlimited = tier in UNLIMITED_TIERS
    limits = None if unlimited else DAILY_LIMITS.get(tier, DAILY_LIMITS["anonim"])

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        daily = await conn.fetch(
            """SELECT event_type, COUNT(*) c FROM usage_events
               WHERE user_id = $1 AND created_at > $2 GROUP BY event_type""",
            user.user_id, day_ago,
        )
        monthly = await conn.fetch(
            """SELECT event_type, COUNT(*) c FROM usage_events
               WHERE user_id = $1 AND created_at > $2 GROUP BY event_type""",
            user.user_id, month_ago,
        )

    daily_map = {r["event_type"]: r["c"] for r in daily}
    monthly_map = {r["event_type"]: r["c"] for r in monthly}

    breakdown = []
    for ev, lim in (limits or {}).items():
        used = daily_map.get(ev, 0)
        breakdown.append({
            "event_type": ev,
            "daily_used": used,
            "daily_limit": lim,
            "monthly_used": monthly_map.get(ev, 0),
            "remaining": max(lim - used, 0),
            "percent": min(100, int(used * 100 / lim)) if lim else 0,
        })

    return APIResponse(ok=True, data={
        "tier": tier,
        "unlimited": unlimited,
        "breakdown": breakdown,
        "reset_at": (now + timedelta(hours=24)).isoformat(),
    })


@router.get("/tenants", response_model=APIResponse)
async def my_tenants(user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT t.id, t.name, t.slug, t.type, t.plan_tier, tm.role,
                      t.plan_expires_at, t.trial_ends_at
               FROM tenant_members tm
               JOIN tenants t ON t.id = tm.tenant_id
               WHERE tm.user_id = $1 AND t.is_active = TRUE
               ORDER BY tm.created_at""",
            user.user_id,
        )
    return APIResponse(ok=True, data={
        "tenants": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "slug": r["slug"],
                "type": r["type"],
                "plan": r["plan_tier"],
                "role": r["role"],
                "plan_expires_at": r["plan_expires_at"].isoformat() if r["plan_expires_at"] else None,
                "trial_ends_at": r["trial_ends_at"].isoformat() if r["trial_ends_at"] else None,
            }
            for r in rows
        ],
    })


@router.get("/searches", response_model=APIResponse)
async def my_searches(
    user: CurrentUser = Depends(get_current_user),
    limit: int = 50,
    favorites_only: bool = False,
):
    """Geçmiş aramalar (Free hesap özelliği)."""
    where = "WHERE user_id = $1"
    if favorites_only:
        where += " AND is_favorite = TRUE"
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            f"""SELECT id, query, result_count, filters, is_favorite, tags, created_at
                FROM user_searches {where}
                ORDER BY created_at DESC LIMIT $2""",
            user.user_id, min(limit, 200),
        )
    return APIResponse(ok=True, data={
        "searches": [
            {
                "id": str(r["id"]),
                "query": r["query"],
                "result_count": r["result_count"],
                "filters": r["filters"],
                "is_favorite": bool(r["is_favorite"]) if "is_favorite" in r else False,
                "tags": r["tags"] if "tags" in r else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    })


@router.get("/uretimler", response_model=APIResponse)
async def my_generations(
    user: CurrentUser = Depends(get_current_user),
    limit: int = 50,
    tool: str | None = None,
):
    """AI üretim geçmişi (dilekçe/ihtarname/özet/denetim vb.)."""
    where = "WHERE user_id = $1"
    params: list = [user.user_id]
    if tool:
        where += " AND tool = $2"
        params.append(tool)
    params.append(min(limit, 200))
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            f"""SELECT id, tool, alt_tur, baslik, girdi_ozeti, cikti, created_at
                FROM generated_documents {where}
                ORDER BY created_at DESC LIMIT ${len(params)}""",
            *params,
        )
    return APIResponse(ok=True, data={
        "uretimler": [
            {
                "id": str(r["id"]),
                "tool": r["tool"],
                "alt_tur": r["alt_tur"],
                "baslik": r["baslik"],
                "girdi_ozeti": r["girdi_ozeti"],
                "cikti": r["cikti"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    })


@router.delete("/uretimler/{kayit_id}", response_model=APIResponse,
               summary="Geçmişten tek kaydı sil")
async def uretim_sil(
    kayit_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Kullanıcının kendi geçmiş kaydını siler (RLS ile kendi satırı)."""
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM generated_documents WHERE id = $1 AND user_id = $2",
            kayit_id, user.user_id,
        )
    if result.endswith("0"):
        raise HTTPException(404, "Kayıt bulunamadı.")
    return APIResponse(ok=True, message="Kayıt silindi.")


@router.delete("/uretimler", response_model=APIResponse,
               summary="Geçmişi temizle (tümü veya araç bazlı)")
async def uretim_temizle(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    tool: str | None = None,
):
    """Kullanıcının geçmişini siler. `tool` verilirse yalnızca o araç, yoksa tümü.

    'arama' kayıtları hem generated_documents hem user_searches'te tutulduğundan,
    tümü temizlenirken (veya tool='arama') user_searches de temizlenir.
    """
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        async with conn.transaction():
            if tool:
                res = await conn.execute(
                    "DELETE FROM generated_documents WHERE user_id = $1 AND tool = $2",
                    user.user_id, tool,
                )
                if tool == "arama":
                    await conn.execute(
                        "DELETE FROM user_searches WHERE user_id = $1", user.user_id,
                    )
            else:
                res = await conn.execute(
                    "DELETE FROM generated_documents WHERE user_id = $1", user.user_id,
                )
                await conn.execute(
                    "DELETE FROM user_searches WHERE user_id = $1", user.user_id,
                )
    silinen = res.rsplit(" ", 1)[-1] if res else "0"
    await audit(action="history.cleared", user_id=user.user_id,
                tenant_id=user.tenant_id, request=request,
                metadata={"tool": tool or "all", "count": silinen})
    return APIResponse(ok=True, message="Geçmiş temizlendi.", data={"silinen": silinen})


@router.post("/searches/{search_id}/favorite", response_model=APIResponse)
async def toggle_favorite(
    search_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT is_favorite FROM user_searches WHERE id = $1 AND user_id = $2",
            search_id, user.user_id,
        )
        if not row:
            raise HTTPException(404, "Bulunamadı.")
        new_val = not bool(row.get("is_favorite") if row.get("is_favorite") is not None else False)
        await conn.execute(
            "UPDATE user_searches SET is_favorite = $1 WHERE id = $2",
            new_val, search_id,
        )
    return APIResponse(ok=True, data={"is_favorite": new_val})


@router.delete("/account", response_model=APIResponse)
async def delete_account(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """KVKK madde 7 — silme hakkı.
    Hesap pasifleştirilir, kişisel veriler 30 gün sonra otomatik silinir."""
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        async with conn.transaction():
            await conn.execute(
                """UPDATE users SET is_active = FALSE, email = $1, name = '[silindi]',
                          password_hash = NULL, metadata = metadata || '{"deleted_at": "' || NOW() || '"}'::jsonb
                   WHERE id = $2""",
                f"deleted-{user.user_id}@hukukcuyapayzekasi.com",
                user.user_id,
            )
            await conn.execute(
                "DELETE FROM sessions WHERE user_id = $1",
                user.user_id,
            )

    await audit(
        action="account.deleted",
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        request=request,
    )
    return APIResponse(ok=True, message="Hesap silme talebiniz alındı. Verileriniz 30 gün içinde tamamen silinir.")


# =============================================================================
# Kaydedilen kararlar (favoriler) — karar bazlı yıldızlama + klasörleme
# =============================================================================

from pydantic import BaseModel as _BaseModel, Field as _Field


class KararKaydetIstegi(_BaseModel):
    decision_id: str = _Field(..., min_length=1, max_length=200)
    chunk_id: str | None = _Field(None, max_length=200)
    klasor: str | None = _Field(None, max_length=120)
    baslik: str | None = _Field(None, max_length=300)
    ozet: str | None = _Field(None, max_length=4000)
    meta: dict | None = None
    not_metni: str | None = _Field(None, max_length=2000)


@router.post("/kararlar", response_model=APIResponse,
             summary="Emsal kararı kaydet (yıldızla)")
async def karar_kaydet(
    istek: KararKaydetIstegi,
    user: CurrentUser = Depends(get_current_user),
):
    import json as _json
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO user_saved_decisions
                   (user_id, decision_id, chunk_id, klasor, baslik, ozet, meta, not_metni)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
               ON CONFLICT (user_id, decision_id, chunk_id)
               DO UPDATE SET klasor = EXCLUDED.klasor,
                             baslik = EXCLUDED.baslik,
                             not_metni = EXCLUDED.not_metni
               RETURNING id""",
            user.user_id, istek.decision_id, istek.chunk_id or "",
            istek.klasor, istek.baslik, istek.ozet,
            _json.dumps(istek.meta or {}), istek.not_metni,
        )
    return APIResponse(ok=True, data={"id": str(row["id"])},
                       message="Karar kaydedildi.")


@router.get("/kararlar", response_model=APIResponse,
            summary="Kaydedilen kararları listele")
async def kararlar_listele(
    user: CurrentUser = Depends(get_current_user),
    klasor: str | None = None,
    limit: int = 100,
):
    where = "WHERE user_id = $1"
    params: list = [user.user_id]
    if klasor:
        where += " AND klasor = $2"
        params.append(klasor)
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            f"""SELECT id, decision_id, chunk_id, klasor, baslik, ozet,
                       meta, not_metni, created_at
                FROM user_saved_decisions {where}
                ORDER BY created_at DESC LIMIT {min(int(limit), 500)}""",
            *params,
        )
        klasorler = await conn.fetch(
            """SELECT klasor, COUNT(*) AS adet FROM user_saved_decisions
               WHERE user_id = $1 AND klasor IS NOT NULL
               GROUP BY klasor ORDER BY klasor""",
            user.user_id,
        )
    return APIResponse(ok=True, data={
        "kararlar": [
            {
                "id": str(r["id"]),
                "decision_id": r["decision_id"],
                "chunk_id": r["chunk_id"] or None,
                "klasor": r["klasor"],
                "baslik": r["baslik"],
                "ozet": r["ozet"],
                "meta": r["meta"],
                "not_metni": r["not_metni"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "klasorler": [
            {"klasor": k["klasor"], "adet": k["adet"]} for k in klasorler
        ],
    })


@router.delete("/kararlar/{kayit_id}", response_model=APIResponse,
               summary="Kaydedilen kararı sil")
async def karar_sil(
    kayit_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM user_saved_decisions WHERE id = $1 AND user_id = $2",
            kayit_id, user.user_id,
        )
    if result.endswith("0"):
        raise HTTPException(404, "Kayıt bulunamadı.")
    return APIResponse(ok=True, message="Silindi.")


# =============================================================================
# Emsal alarmı — "bu konuda yeni karar çıkınca haber ver"
# =============================================================================


class AlarmIstegi(_BaseModel):
    query: str = _Field(..., min_length=3, max_length=300)
    filters: dict | None = None


@router.post("/alerts", response_model=APIResponse,
             summary="Aramayı takibe al (yeni emsal çıkınca e-posta)")
async def alarm_olustur(
    istek: AlarmIstegi,
    user: CurrentUser = Depends(get_current_user),
):
    import json as _json
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO saved_search_alerts (user_id, query, filters)
               VALUES ($1, $2, $3::jsonb)
               ON CONFLICT (user_id, query)
               DO UPDATE SET aktif = TRUE, filters = EXCLUDED.filters
               RETURNING id""",
            user.user_id, istek.query.strip(), _json.dumps(istek.filters or {}),
        )
    return APIResponse(ok=True, data={"id": str(row["id"])},
                       message="Takibe alındı — yeni emsal çıkınca e-posta alacaksınız.")


@router.get("/alerts", response_model=APIResponse, summary="Takip edilen aramalar")
async def alarm_listele(user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT id, query, filters, aktif, son_bildirim, created_at
               FROM saved_search_alerts WHERE user_id = $1
               ORDER BY created_at DESC""",
            user.user_id,
        )
    return APIResponse(ok=True, data={"alerts": [
        {
            "id": str(r["id"]),
            "query": r["query"],
            "filters": r["filters"],
            "aktif": r["aktif"],
            "son_bildirim": r["son_bildirim"].isoformat() if r["son_bildirim"] else None,
            "created_at": r["created_at"].isoformat(),
        } for r in rows
    ]})


@router.delete("/alerts/{alarm_id}", response_model=APIResponse,
               summary="Takibi durdur")
async def alarm_sil(
    alarm_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM saved_search_alerts WHERE id = $1 AND user_id = $2",
            alarm_id, user.user_id,
        )
    if result.endswith("0"):
        raise HTTPException(404, "Alarm bulunamadı.")
    return APIResponse(ok=True, message="Takip durduruldu.")


# =============================================================================
# API anahtarları (enterprise/entegrasyon) — anahtar yalnızca oluşturulurken
# bir kez gösterilir; DB'de sadece sha256 hash'i tutulur.
# =============================================================================


class ApiKeyIstegi(_BaseModel):
    name: str = _Field(..., min_length=1, max_length=100)
    daily_quota: int = _Field(1000, ge=1, le=100_000)


@router.post("/api-keys", response_model=APIResponse,
             summary="API anahtarı oluştur")
async def apikey_olustur(
    istek: ApiKeyIstegi,
    user: CurrentUser = Depends(get_current_user),
):
    import hashlib
    import secrets

    tam_anahtar = "he_live_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(tam_anahtar.encode("utf-8")).hexdigest()
    prefix = tam_anahtar[:12] + "…"

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO api_keys (user_id, tenant_id, name, key_prefix, key_hash, daily_quota)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
            user.user_id, user.tenant_id, istek.name, prefix, key_hash,
            istek.daily_quota,
        )
    await audit(action="apikey.created", user_id=user.user_id,
                tenant_id=user.tenant_id, metadata={"name": istek.name})
    return APIResponse(ok=True, data={
        "id": str(row["id"]),
        "api_key": tam_anahtar,  # YALNIZCA bu yanıtta görünür
        "prefix": prefix,
    }, message="Anahtarı şimdi kaydedin — bir daha gösterilmeyecek.")


@router.get("/api-keys", response_model=APIResponse, summary="API anahtarlarım")
async def apikey_listele(user: CurrentUser = Depends(get_current_user)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT id, name, key_prefix, aktif, daily_quota, last_used_at, created_at
               FROM api_keys WHERE user_id = $1 ORDER BY created_at DESC""",
            user.user_id,
        )
    return APIResponse(ok=True, data={"keys": [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "prefix": r["key_prefix"],
            "aktif": r["aktif"],
            "daily_quota": r["daily_quota"],
            "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
            "created_at": r["created_at"].isoformat(),
        } for r in rows
    ]})


@router.delete("/api-keys/{key_id}", response_model=APIResponse,
               summary="API anahtarını iptal et")
async def apikey_iptal(
    key_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        result = await conn.execute(
            "UPDATE api_keys SET aktif = FALSE WHERE id = $1 AND user_id = $2",
            key_id, user.user_id,
        )
    if result.endswith("0"):
        raise HTTPException(404, "Anahtar bulunamadı.")
    await audit(action="apikey.revoked", user_id=user.user_id,
                tenant_id=user.tenant_id, metadata={"key_id": key_id})
    return APIResponse(ok=True, message="Anahtar iptal edildi.")
