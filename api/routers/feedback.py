"""Public feedback endpoint — kullanıcılar her sayfada bildirimde bulunabilir."""
from __future__ import annotations
import json
import logging
import os
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from api.audit import audit
from api.auth import CurrentUser, get_current_user, get_optional_user
from api.db import service_session
from api.schemas import APIResponse

log = logging.getLogger("api.feedback")
router = APIRouter()


class FeedbackReq(BaseModel):
    feedback_type: str = Field(default="other")  # bug | feature | praise | complaint | question
    severity: str = "normal"
    subject: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=5, max_length=4000)
    page_url: str | None = None
    contact_email: str | None = None
    screen_resolution: str | None = None


@router.post("/", response_model=APIResponse)
async def submit_feedback(
    payload: FeedbackReq,
    request: Request,
    user: CurrentUser | None = Depends(get_optional_user),
):
    """Anonim veya kayıtlı kullanıcı geri bildirim gönder."""
    valid_types = {"bug", "feature", "praise", "complaint", "question", "other"}
    valid_severities = {"low", "normal", "high", "critical"}
    if payload.feedback_type not in valid_types:
        payload.feedback_type = "other"
    if payload.severity not in valid_severities:
        payload.severity = "normal"

    ua = request.headers.get("user-agent", "")[:500]

    # Anonim de olabilir (user None); public sistem yazımı → service_session.
    async with service_session() as conn:
        feedback_id = await conn.fetchval(
            """INSERT INTO feedback
               (user_id, tenant_id, feedback_type, severity, page_url,
                user_agent, screen_resolution, subject, message, contact_email,
                metadata)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
               RETURNING id""",
            user.user_id if user else None,
            user.tenant_id if user else None,
            payload.feedback_type, payload.severity,
            payload.page_url, ua, payload.screen_resolution,
            payload.subject, payload.message,
            payload.contact_email or (user.email if user else None),
            json.dumps({}),
        )

    await audit(
        action="feedback.submitted",
        user_id=user.user_id if user else None,
        tenant_id=user.tenant_id if user else None,
        resource=f"feedback:{feedback_id}",
        request=request,
        metadata={"type": payload.feedback_type, "severity": payload.severity},
    )

    # Anlamlı her talepte admin'e e-posta gönder.
    # Kritik olanlar vurgulu (🚨); öneri/eksiklik/hata/diğer ise normal bilgilendirme.
    notify_types = {"feature", "complaint", "bug", "other", "question"}
    is_critical = payload.severity == "critical"
    if is_critical or payload.feedback_type in notify_types:
        try:
            from services.email import send_email, _wrap
            admin_to = os.environ.get("ADMIN_EMAIL") or os.environ.get(
                "FEEDBACK_ADMIN_EMAIL"
            ) or "admin@hukukcuyapayzekasi.com"
            site = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://hukukcuyapayzekasi.com")

            type_label = {
                "feature": "Öneri",
                "complaint": "Eksiklik / Şikayet",
                "bug": "Hata bildirimi",
                "question": "Soru",
                "praise": "Teşekkür",
                "other": "Diğer",
            }.get(payload.feedback_type, payload.feedback_type)

            who = (user.email if user else None) or payload.contact_email or "(anonim)"

            if is_critical:
                title = "Kritik Geri Bildirim"
                subject = f"🚨 Kritik geri bildirim — {type_label}"
                lead = "<p><strong>🚨 KRİTİK geri bildirim alındı.</strong></p>"
            else:
                title = "Yeni Geri Bildirim"
                subject = f"Yeni geri bildirim — {type_label}"
                lead = "<p>Yeni bir kullanıcı talebi alındı.</p>"

            body = (
                f"{lead}"
                f"<p>Tür: <strong>{type_label}</strong><br>"
                f"Gönderen: {who}<br>"
                f"Konu: {payload.subject or '(yok)'}<br>"
                f"Sayfa: {payload.page_url or '(belirtilmedi)'}</p>"
                f"<p style='white-space:pre-wrap;'>{payload.message[:1000]}</p>"
                f"<p><a href='{site}/app/admin/feedback'>Admin panelinden yönet</a></p>"
            )
            gonderildi = await send_email(
                to=admin_to,
                subject=subject,
                html=_wrap(title, body),
            )
            if not gonderildi:
                log.warning(
                    "Geri bildirim e-postası gönderilemedi (id=%s, to=%s). "
                    "SMTP yapılandırmasını kontrol edin.", feedback_id, admin_to,
                )
        except Exception:
            log.exception("Geri bildirim e-posta gönderiminde hata (id=%s)", feedback_id)

    return APIResponse(
        ok=True,
        data={"id": str(feedback_id)},
        message="Geri bildiriminiz için teşekkürler — birkaç gün içinde inceleyeceğiz.",
    )


@router.get("/mine", response_model=APIResponse)
async def my_feedback(user: CurrentUser = Depends(get_current_user)):
    """Giriş yapan kullanıcının kendi gönderdiği talepleri döndür."""
    async with service_session() as conn:
        rows = await conn.fetch(
            """SELECT id, feedback_type, severity, subject, message,
                      status, created_at
               FROM feedback
               WHERE user_id = $1
               ORDER BY created_at DESC
               LIMIT 100""",
            user.user_id,
        )
    items = [
        {
            "id": str(r["id"]),
            "type": r["feedback_type"],
            "severity": r["severity"],
            "subject": r["subject"],
            "message": r["message"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return APIResponse(ok=True, data={"feedback": items})
