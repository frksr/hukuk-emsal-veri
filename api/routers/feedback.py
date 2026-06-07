"""Public feedback endpoint — kullanıcılar her sayfada bildirimde bulunabilir."""
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from api.audit import audit
from api.auth import CurrentUser, get_optional_user
from api.db import service_session
from api.schemas import APIResponse

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

    # Kritik feedback'leri admin'lere bildir
    if payload.severity == "critical":
        try:
            from services.email import send_email, _wrap
            site = "https://hukukemsal.tr"
            body = (
                f"<p><strong>KRİTİK geri bildirim alındı.</strong></p>"
                f"<p>Tip: {payload.feedback_type}<br>"
                f"Konu: {payload.subject or '(yok)'}<br>"
                f"Mesaj: {payload.message[:500]}</p>"
                f"<p><a href='{site}/app/admin/feedback'>Admin panelinden yönet</a></p>"
            )
            await send_email(
                to="admin@hukukemsal.tr",
                subject=f"🚨 Kritik geri bildirim — {payload.feedback_type}",
                html=_wrap("Kritik Geri Bildirim", body),
            )
        except Exception:
            pass

    return APIResponse(
        ok=True,
        data={"id": str(feedback_id)},
        message="Geri bildiriminiz için teşekkürler — birkaç gün içinde inceleyeceğiz.",
    )
