"""Audit log helper — KVKK için kritik.

Her hassas işlemde `await audit(...)` çağrılır.
"""
from __future__ import annotations
from typing import Optional, Any
from fastapi import Request

from api.db import service_session


async def audit(
    action: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    resource: Optional[str] = None,
    request: Optional[Request] = None,
    success: bool = True,
    metadata: Optional[dict[str, Any]] = None,
):
    """audit_log tablosuna kayıt at.

    Args:
        action: "login", "logout", "document.read", "document.create",
                "password.reset", "tenant.invite", vb.
        resource: "document:abc-123" gibi.
    """
    import json
    ip = None
    ua = None
    if request:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            ip = fwd.split(",")[0].strip()
        elif request.client:
            ip = request.client.host
        ua = request.headers.get("user-agent", "")[:500]

    try:
        # audit_log RLS'e tabidir ve INSERT için policy yoktur; sistem yazımı
        # service_session (BYPASSRLS) ile yapılır.
        async with service_session() as conn:
            await conn.execute(
                """INSERT INTO audit_log
                   (user_id, tenant_id, action, resource, ip_address, user_agent, success, metadata)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)""",
                user_id, tenant_id, action, resource, ip, ua, success,
                json.dumps(metadata or {}),
            )
    except Exception as e:
        # Audit hata vermesin uygulamayı bozsun istemiyoruz
        import logging
        logging.getLogger("api.audit").warning(f"Audit log yazma hatası: {e}")
