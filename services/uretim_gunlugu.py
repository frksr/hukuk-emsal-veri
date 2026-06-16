"""AI üretimlerini ve kullanım olaylarını DB'ye kaydeden yardımcılar.

- generated_documents: kullanıcının ürettiği dilekçe/ihtarname/özet/denetim vb. geçmişi
  (RLS'e tabi → db_session ile kullanıcı bağlamında yazılır).
- usage_events: sistem iyileştirme/analitik için her AI kullanımının logu
  (service_session ile yazılır; rate_limit._log_event ile aynı model).

Tüm yazımlar background task olarak çağrılır; hata yutulur, asıl yanıtı bozmaz.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from api.db import db_session, service_session

log = logging.getLogger("services.uretim_gunlugu")


def _ai_provider_meta(tool: str) -> dict:
    """AI (LLM kullanan) araçlar için {'provider': varsayılan} — yoksa {}.

    Yalnızca varsayılan sağlayıcıyı kaydeder (API çağrısı yapmaz). usage_events
    analitiğinde sağlayıcı dağılımını ileriye dönük doğru göstermek için.
    """
    try:
        from api.rate_limit import AI_MODULES
        if tool not in AI_MODULES:
            return {}
        from llm.provider import _get_default_provider
        return {"provider": _get_default_provider()}
    except Exception:
        return {}


def _kisalt(s: Optional[str], n: int) -> Optional[str]:
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else s[:n] + "…"


async def gecmis_acik_mi(user_id: Optional[str]) -> bool:
    """Kullanıcının 'geçmişimi tut' tercihini döndürür (history_enabled).

    Kişisel geçmiş (generated_documents / user_searches) yazımından önce kontrol
    edilir. Tercih FALSE ise yeni geçmiş yazılmaz. Hata/eksik durumunda güvenli
    varsayılan TRUE (eski davranış). usage_events bu kontrolden etkilenmez.
    """
    if not user_id:
        return True
    try:
        async with service_session() as conn:
            val = await conn.fetchval(
                "SELECT history_enabled FROM users WHERE id = $1", user_id,
            )
        return True if val is None else bool(val)
    except Exception as e:
        log.warning("history_enabled okunamadı (%s): %s", user_id, e)
        return True


async def kaydet_kullanim(
    user_id: Optional[str],
    tenant_id: Optional[str],
    tool: str,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    """Hafif kullanım logu — yalnızca usage_events (üretim/belge yok).

    Hesaplayıcılar (faiz, zamanaşımı) ve checklist (kvkk) gibi 'üretim' sayılmayan
    ama rapora yansıması gereken araçlar için. Hata yutulur.
    """
    if not user_id:
        return
    try:
        _meta = dict(meta or {})
        if "provider" not in _meta:
            _meta.update(_ai_provider_meta(tool))
        async with service_session() as conn:
            await conn.execute(
                """INSERT INTO usage_events (user_id, tenant_id, event_type, metadata)
                   VALUES ($1, $2, $3, $4::jsonb)""",
                user_id, tenant_id, tool,
                json.dumps(_meta, ensure_ascii=False),
            )
    except Exception as e:
        log.warning("usage_events (kullanım) yazımı başarısız (%s): %s", tool, e)


async def kaydet_uretim(
    user_id: Optional[str],
    tenant_id: Optional[str],
    tool: str,
    *,
    alt_tur: Optional[str] = None,
    baslik: Optional[str] = None,
    girdi_ozeti: Optional[str] = None,
    cikti: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
    log_usage: bool = True,
) -> None:
    """Bir üretimi/etkinliği geçmişe (generated_documents) + opsiyonel usage_events'e yazar.

    log_usage=False → yalnızca geçmiş yazılır (usage_events'i başka yerde —ör. rate_limit_for—
    zaten loglanan araçlarda çift sayımı önlemek için, ör. emsal arama).
    Hatalar sessizce yutulur.
    """
    if not user_id:
        return  # anonim kullanıcı (zaten gate engelliyor) — kayıt yok

    # 1) Üretim geçmişi (RLS: kendi satırı) — yalnızca kullanıcı geçmiş tutmayı
    #    açık bıraktıysa yazılır. Tercih FALSE ise kişisel geçmiş atlanır;
    #    usage_events (aşağıdaki analitik/limit logu) bundan etkilenmez.
    if await gecmis_acik_mi(user_id):
        try:
            async with db_session(user_id=user_id, tenant_id=tenant_id) as conn:
                await conn.execute(
                    """INSERT INTO generated_documents
                           (user_id, tenant_id, tool, alt_tur, baslik, girdi_ozeti, cikti, meta)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)""",
                    user_id,
                    tenant_id,
                    tool,
                    alt_tur,
                    _kisalt(baslik, 300),
                    _kisalt(girdi_ozeti, 2000),
                    cikti,
                    json.dumps(meta or {}, ensure_ascii=False),
                )
        except Exception as e:
            log.warning("generated_documents yazımı başarısız (%s): %s", tool, e)

    # 2) Kullanım logu (analitik / sistem iyileştirme)
    if not log_usage:
        return
    try:
        _meta = {"alt_tur": alt_tur} if alt_tur else {}
        mod = (meta or {}).get("mode")
        if mod:
            _meta["mode"] = mod
        # Şablon (LLM'siz) modunda sağlayıcı eklenmez → analitikte AI sayım/maliyet/
        # sağlayıcı dağılımı dışında tutulur (mode='sablon' ile işaretli).
        if mod != "sablon":
            _meta.update(_ai_provider_meta(tool))
        async with service_session() as conn:
            await conn.execute(
                """INSERT INTO usage_events (user_id, tenant_id, event_type, metadata)
                   VALUES ($1, $2, $3, $4::jsonb)""",
                user_id,
                tenant_id,
                tool,
                json.dumps(_meta, ensure_ascii=False),
            )
    except Exception as e:
        log.warning("usage_events yazımı başarısız (%s): %s", tool, e)
