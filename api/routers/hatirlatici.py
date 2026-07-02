"""Hatırlatıcılar router — yalnızca ÜCRETLİ planlara açık.

Kullanıcı; bir dava/dosya, kendi notları veya sitedeki herhangi bir veriyle
ilgili DİNAMİK hatırlatıcı oluşturur. Şu aşamada e-posta ile gönderilir;
'channel' alanı ileride WhatsApp/Telegram için tasarlandı.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import CurrentUser, require_plan
from api.concurrency import run_blocking
from api.db import db_session
from api.schemas import APIResponse

try:
    from llm.provider import generate as llm_generate, is_available as llm_available
except ImportError:  # LLM yapılandırılmamışsa manuel akışa düşeriz.
    llm_generate = None  # type: ignore[assignment]
    llm_available = None  # type: ignore[assignment]

log = logging.getLogger("api.hatirlatici")
router = APIRouter()

# Tüm endpoint'ler ücretli plana kapalı (402 döner).
pro = require_plan("pro_solo")

_GECERLI_KANALLAR = {"email"}  # şimdilik yalnızca e-posta
_GECERLI_KAYNAKLAR = {"serbest", "not", "dosya", "uretim", "arama"}
_GECERLI_DURUMLAR = {"pending", "sent", "failed", "canceled"}


class HatirlaticiIstegi(BaseModel):
    baslik: str = Field(..., min_length=1, max_length=300)
    not_metni: str | None = Field(default=None, max_length=5000)
    kaynak_tip: str = Field(default="serbest", max_length=30)
    kaynak_id: str | None = Field(default=None, max_length=200)
    kaynak_ozet: str | None = Field(default=None, max_length=500)
    remind_at: datetime
    channel: str = Field(default="email", max_length=30)


class HatirlaticiGuncelle(BaseModel):
    baslik: str | None = Field(default=None, min_length=1, max_length=300)
    not_metni: str | None = Field(default=None, max_length=5000)
    remind_at: datetime | None = None
    status: str | None = None


def _row(r) -> dict:
    return {
        "id": str(r["id"]),
        "baslik": r["baslik"],
        "not_metni": r["not_metni"],
        "kaynak_tip": r["kaynak_tip"],
        "kaynak_id": r["kaynak_id"],
        "kaynak_ozet": r["kaynak_ozet"],
        "remind_at": r["remind_at"].isoformat(),
        "channel": r["channel"],
        "status": r["status"],
        "sent_at": r["sent_at"].isoformat() if r["sent_at"] else None,
        "created_at": r["created_at"].isoformat(),
        "updated_at": r["updated_at"].isoformat(),
    }


def _ileride_mi(dt: datetime) -> bool:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt > datetime.now(timezone.utc)


@router.post("/", response_model=APIResponse, summary="Hatırlatıcı oluştur")
async def create_reminder(
    istek: HatirlaticiIstegi, user: CurrentUser = Depends(pro)
):
    if not _ileride_mi(istek.remind_at):
        raise HTTPException(400, "Hatırlatma zamanı gelecekte olmalı.")
    kaynak_tip = istek.kaynak_tip if istek.kaynak_tip in _GECERLI_KAYNAKLAR else "serbest"
    channel = istek.channel if istek.channel in _GECERLI_KANALLAR else "email"

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        r = await conn.fetchrow(
            """INSERT INTO reminders
               (user_id, tenant_id, baslik, not_metni, kaynak_tip, kaynak_id,
                kaynak_ozet, remind_at, channel)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING *""",
            user.user_id, user.tenant_id, istek.baslik.strip(), istek.not_metni,
            kaynak_tip, istek.kaynak_id, istek.kaynak_ozet, istek.remind_at, channel,
        )
    return APIResponse(ok=True, data=_row(r))


@router.get("/", response_model=APIResponse, summary="Hatırlatıcıları listele")
async def list_reminders(user: CurrentUser = Depends(pro), limit: int = 200):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT * FROM reminders WHERE user_id = $1
               ORDER BY remind_at ASC LIMIT $2""",
            user.user_id, min(limit, 500),
        )
    return APIResponse(ok=True, data={"hatirlaticilar": [_row(r) for r in rows]})


@router.patch("/{rid}", response_model=APIResponse, summary="Hatırlatıcı güncelle")
async def update_reminder(
    rid: str, istek: HatirlaticiGuncelle, user: CurrentUser = Depends(pro)
):
    if istek.remind_at is not None and not _ileride_mi(istek.remind_at):
        raise HTTPException(400, "Hatırlatma zamanı gelecekte olmalı.")
    if istek.status is not None and istek.status not in _GECERLI_DURUMLAR:
        raise HTTPException(400, "Geçersiz durum.")

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        # Yalnızca verilen alanları güncelle (COALESCE ile mevcut değeri koru).
        r = await conn.fetchrow(
            """UPDATE reminders SET
                   baslik    = COALESCE($2, baslik),
                   not_metni = CASE WHEN $3::bool THEN $4 ELSE not_metni END,
                   remind_at = COALESCE($5, remind_at),
                   status    = COALESCE($6, status),
                   updated_at = NOW()
               WHERE id = $1 RETURNING *""",
            rid,
            istek.baslik,
            # not_metni açıkça None'a çekilebilsin diye "set edildi mi" bayrağı
            "not_metni" in istek.model_fields_set,
            istek.not_metni,
            istek.remind_at,
            istek.status,
        )
    if not r:
        raise HTTPException(404, "Hatırlatıcı bulunamadı.")
    return APIResponse(ok=True, data=_row(r))


@router.delete("/{rid}", response_model=APIResponse, summary="Hatırlatıcı sil")
async def delete_reminder(rid: str, user: CurrentUser = Depends(pro)):
    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        await conn.execute("DELETE FROM reminders WHERE id = $1", rid)
    return APIResponse(ok=True, data={"ok": True})


class AiTaslaIstegi(BaseModel):
    metin: str = Field(..., min_length=3, max_length=2000)
    # İstemcinin yerel "şu an"ı (YYYY-MM-DDTHH:MM) — göreli zamanları çözmek için.
    simdi: str | None = Field(default=None, max_length=40)


def _json_cikar(text: str) -> dict | None:
    """LLM yanıtından ilk JSON nesnesini güvenle ayıkla."""
    import json
    import re
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


@router.post("/ai-tasla", response_model=APIResponse,
             summary="Serbest metinden Yapay Zeka ile hatırlatıcı taslağı")
async def ai_tasla(istek: AiTaslaIstegi, user: CurrentUser = Depends(pro)):
    """Kullanıcının serbest metnini TEK Yapay Zeka çağrısıyla yapılandırır:
    başlık + zaman + not çıkarır ve eksik alanlar için doğal sorular üretir.
    Soru-cevap ve oluşturma adımları sunucuda deterministik yapılır → ek çağrı yok,
    maliyet hatırlatıcı başına tek çağrıyla sınırlı kalır."""
    manuel_eksik = [
        {"alan": "baslik", "soru": "Hatırlatıcıya kısa bir başlık verir misiniz?"},
        {"alan": "remind_at", "soru": "Ne zaman hatırlatalım? (tarih ve saat)"},
    ]
    if llm_generate is None or (llm_available is not None and not llm_available()):
        # LLM yoksa kullanıcı manuel forma düşsün (yine de metni nota koyalım).
        return APIResponse(ok=True, data={
            "baslik": None, "remind_at": None, "not_metni": istek.metin.strip(),
            "eksik": manuel_eksik, "llm": False,
        })

    simdi = istek.simdi or datetime.now().strftime("%Y-%m-%dT%H:%M")
    system = (
        "Sen bir hukuk asistanının hatırlatıcı modülüsün. Kullanıcının serbest metninden "
        f"bir hatırlatıcı çıkarırsın. Şu anki yerel tarih-saat: {simdi}. Göreli zaman "
        "ifadelerini ('yarın', 'haftaya salı 15:00', '3 gün sonra') bu ana göre çöz. "
        "SADECE şu JSON şemasıyla yanıt ver, başka hiçbir metin yazma:\n"
        '{"baslik": string|null, "remind_at": "YYYY-MM-DDTHH:MM"|null, '
        '"not_metni": string|null, "eksik": [{"alan": "baslik"|"remind_at", "soru": string}]}\n'
        "Kurallar: Başlık kısa ve net olsun. remind_at YALNIZCA kullanıcı net bir zaman "
        "belirttiyse doldur; aksi halde null yap ve 'eksik' listesine remind_at ekle. Başlık "
        "çıkaramıyorsan baslik=null yapıp eksik'e ekle. 'soru' alanına kullanıcıya kibarca "
        "soracağın doğal, tek cümlelik Türkçe bir soru yaz (sanki sen soruyormuşsun gibi)."
    )
    try:
        raw = await run_blocking(
            llm_generate, system=system, user=istek.metin.strip(),
            max_tokens=400, temperature=0.1,
        )
    except Exception as e:
        log.warning("ai-tasla LLM hatası: %s", e)
        raise HTTPException(503, "Yapay Zeka şu an yanıt veremedi, lütfen tekrar deneyin.")

    data = _json_cikar(raw) or {}
    eksik_ham = data.get("eksik") if isinstance(data.get("eksik"), list) else []
    temiz_eksik = [
        {"alan": e["alan"], "soru": str(e["soru"])[:200]}
        for e in eksik_ham
        if isinstance(e, dict) and e.get("alan") in ("baslik", "remind_at") and e.get("soru")
    ]
    return APIResponse(ok=True, data={
        "baslik": data.get("baslik") or None,
        "remind_at": data.get("remind_at") or None,
        "not_metni": data.get("not_metni") or istek.metin.strip(),
        "eksik": temiz_eksik,
        "llm": True,
    })


@router.get("/kaynaklar", response_model=APIResponse, summary="Seçilebilir dinamik kaynaklar")
async def list_kaynaklar(user: CurrentUser = Depends(pro)):
    """Hatırlatıcı oluştururken seçilebilecek DİNAMİK kaynaklar:
    kullanıcının notları, AI üretim geçmişi ve (varsa) dosyaları."""
    notlar: list[dict] = []
    uretimler: list[dict] = []
    dosyalar: list[dict] = []

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        # Notlar
        try:
            rows = await conn.fetch(
                """SELECT id, baslik, icerik FROM user_notes
                   WHERE user_id = $1 ORDER BY updated_at DESC LIMIT 50""",
                user.user_id,
            )
            for r in rows:
                ozet = (r["baslik"] or r["icerik"] or "Not").strip()[:120]
                notlar.append({"id": str(r["id"]), "baslik": ozet})
        except Exception as e:
            log.warning("Kaynak (notlar) okunamadı: %s", e)

        # AI üretim geçmişi
        try:
            rows = await conn.fetch(
                """SELECT id, tool, baslik FROM generated_documents
                   WHERE user_id = $1 ORDER BY created_at DESC LIMIT 50""",
                user.user_id,
            )
            for r in rows:
                etiket = (r["baslik"] or r["tool"] or "Üretim").strip()[:120]
                uretimler.append(
                    {"id": str(r["id"]), "tool": r["tool"], "baslik": etiket}
                )
        except Exception as e:
            log.warning("Kaynak (üretimler) okunamadı: %s", e)

        # Dosyalar (UYAP / tenant_documents) — tenant context ile RLS'e tabi.
        if user.tenant_id:
            try:
                rows = await conn.fetch(
                    """SELECT id, title, case_no FROM tenant_documents
                       WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 50""",
                    user.tenant_id,
                )
                for r in rows:
                    baslik = (r["title"] or "Dosya").strip()[:120]
                    if r["case_no"]:
                        baslik = f"{baslik} ({r['case_no']})"
                    dosyalar.append({"id": str(r["id"]), "baslik": baslik})
            except Exception as e:
                log.warning("Kaynak (dosyalar) okunamadı: %s", e)

    return APIResponse(
        ok=True,
        data={"notlar": notlar, "uretimler": uretimler, "dosyalar": dosyalar},
    )


# ---------------------------------------------------------------------------
# Takvim (.ics) exportu — Google/Outlook/Apple Takvim'e ekleme
# ---------------------------------------------------------------------------

def _ics_kacir(s: str) -> str:
    """ICS TEXT alanı kaçışları (RFC 5545)."""
    return (
        (s or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _ics_zaman(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _vevent(r) -> str:
    """Tek hatırlatıcı → VEVENT (1 saat önce VALARM ile)."""
    return "\r\n".join([
        "BEGIN:VEVENT",
        f"UID:hatirlatici-{r['id']}@hukukemsal",
        f"DTSTAMP:{_ics_zaman(datetime.now(timezone.utc))}",
        f"DTSTART:{_ics_zaman(r['remind_at'])}",
        f"SUMMARY:{_ics_kacir(r['baslik'])}",
        *(
            [f"DESCRIPTION:{_ics_kacir(r['not_metni'])}"]
            if r["not_metni"] else []
        ),
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_ics_kacir(r['baslik'])}",
        "TRIGGER:-PT1H",
        "END:VALARM",
        "END:VEVENT",
    ])


def _vcalendar(events: list[str]) -> str:
    return "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Hukuk Emsal//Hatirlaticilar//TR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        *events,
        "END:VCALENDAR",
        "",
    ])


@router.get("/export/ics", summary="Tüm bekleyen hatırlatıcıları .ics indir")
async def export_ics(user: CurrentUser = Depends(pro)):
    from fastapi.responses import Response

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT id, baslik, not_metni, remind_at FROM reminders
               WHERE user_id = $1 AND status = 'pending'
               ORDER BY remind_at""",
            user.user_id,
        )
    icerik = _vcalendar([_vevent(r) for r in rows])
    return Response(
        content=icerik,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="hatirlaticilar.ics"'},
    )


@router.get("/{rid}/ics", summary="Hatırlatıcıyı .ics olarak indir")
async def tekil_ics(rid: str, user: CurrentUser = Depends(pro)):
    from fastapi.responses import Response

    async with db_session(user_id=user.user_id, tenant_id=user.tenant_id) as conn:
        r = await conn.fetchrow(
            """SELECT id, baslik, not_metni, remind_at FROM reminders
               WHERE id = $1::uuid AND user_id = $2""",
            rid, user.user_id,
        )
    if not r:
        raise HTTPException(404, "Hatırlatıcı bulunamadı.")
    icerik = _vcalendar([_vevent(r)])
    return Response(
        content=icerik,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="hatirlatici-{rid}.ics"'},
    )
