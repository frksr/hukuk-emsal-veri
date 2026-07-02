"""Birleşik kota + kredi kapısı.

Bir modül çağrısına erişim şu sırayla değerlendirilir:
  1) Plan kapsamı: Pro+ ilgili modülde sınırsız; ücretsiz/anonim için günlük kota
     (DAILY_LIMITS). min_tier verilmişse (Yapay Zeka araçları) ücretsiz plan kapsam
     DIŞINDADIR — krediyle kullanılır.
  2) Kredi: plan kapsamı bittiyse, kullanıcının o modüldeki ek-paket kredisinden
     1 düşülür (varsa erişim verilir).
  3) Hiçbiri yoksa 402 — yanıt gövdesinde hem 'üst pakete geç' hem 'ek paket al'
     bilgisi döner (frontend ikisini birden gösterir).

Çift sayımı önlemek için kota usage_event'i YALNIZCA metered modüllerde (min_tier
yok; ör. emsal arama) yazar. Yapay Zeka modüllerinde (min_tier verilmiş) usage_event
zaten router'ın kaydet_uretim çağrısıyla (başarıda) yazıldığından kota tekrar yazmaz.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request

from api.auth import CurrentUser, get_optional_user
from api.rate_limit import (
    UNLIMITED_TIERS, tool_daily_limit, _current_count, _log_event, _client_ip,
    kullanici_donem_penceresi, AI_MODULES, atomik_kota_kullan,
)
from services import krediler
from services import app_config

_TIER_ORDER = {
    "free": 0, "anonim": 0,
    "pro_solo": 1, "pro_solo_uyap": 2,
    "team": 3, "team_uyap": 4, "enterprise": 5,
}


def kota(event_type: str, min_tier: str | None = None):
    """Modül erişim kapısı (dependency factory).

    Kullanım:
        user: CurrentUser = Depends(kota("ozet", "pro_solo"))   # Yapay Zeka aracı
        user = Depends(kota("arama"))                            # ücretsiz/metered
    """
    gereken_rank = _TIER_ORDER.get(min_tier, 99) if min_tier else 0

    async def check(
        request: Request,
        user: Optional[CurrentUser] = Depends(get_optional_user),
    ) -> Optional[CurrentUser]:
        tier = (user.tenant_plan or "free") if user else "anonim"
        user_id = user.user_id if user else None
        tenant_id = user.tenant_id if user else None
        ip = _client_ip(request)
        ua = request.headers.get("user-agent", "")

        # Admin: sistemi izleyen ana kullanıcı → her şey açık. Sınırsız (enterprise)
        # sayılır; kota, doğrulama ve plan kapıları uygulanmaz (kullanım yine loglanır).
        is_admin = bool(user and getattr(user, "role", None) == "admin")
        if is_admin:
            tier = "enterprise"

        rank = _TIER_ORDER.get(tier, 0)

        # 0) E-posta doğrulama kapısı — giriş yapmış ama doğrulanmamış kullanıcı
        # AI üretimi / UYAP araçlarını kullanamaz (arama + hesaplayıcılar serbest).
        # Anonim kullanıcının doğrulayacak hesabı yoktur, admin ise muaftır.
        if not is_admin and user_id and event_type in AI_MODULES and not getattr(user, "email_verified", False):
            raise HTTPException(
                403,
                {
                    "error": "email_dogrulanmadi",
                    "module": event_type,
                    "message": (
                        "Bu özelliği kullanmadan önce e-posta adresinizi doğrulayın. "
                        "Size gönderdiğimiz 6 haneli kodu girin."
                    ),
                    "verify_url": "/giris/dogrulama",
                },
            )

        # Kota penceresi: ücretli kullanıcı için abonelik gününe, free için kayıt
        # gününe demirlenmiş AYLIK pencere (takvim ayı değil). reset_at için bitiş.
        donem_bas, donem_bit, _ = await kullanici_donem_penceresi(user_id, tenant_id)

        # usage_event yalnızca metered modüllerde burada yazılır (sayım için).
        # Yapay Zeka modüllerinde (min_tier) router'ın kaydet_uretim'i loglar.
        log_burada = min_tier is None

        # 1) Plan kapsamı
        plan_ok = False
        limit: int | None = None
        if is_admin:
            # Admin → sınırsız (sözleşme gibi plan-bazlı araçlar dahil).
            plan_ok = True
            if log_burada:
                await _log_event(event_type, user_id, tenant_id, ip, ua)
            return user
        elif min_tier and rank < gereken_rank:
            # (Eski yol) min_tier'in altındaki kullanıcı plan kapsamı dışı.
            plan_ok = False
        else:
            # Birleşik limit: pahalı araçlar her planda kendi limitine tabi
            # (Pro'da bile), diğerleri Pro+ sınırsız (None). Admin override (DB)
            # varsa onu uygula.
            override = await app_config.get_plan_limits()
            limit = tool_daily_limit(tier, event_type, override)
            # Sayım + log TEK transaction'da (advisory lock) — eşzamanlı
            # isteklerle limit AŞILAMAZ. log_et=False (AI modülleri) durumunda
            # da kilit, eşzamanlı kontrolleri sıralar.
            plan_ok = await atomik_kota_kullan(
                event_type, user_id, tenant_id, ip, ua,
                limit, donem_bas, log_et=log_burada,
            )

        if plan_ok:
            return user

        # 2) Kredi (ek paket) — yalnızca giriş yapmış kullanıcı
        if user_id and await krediler.dus(user_id, event_type, 1):
            if log_burada:
                await _log_event(event_type, user_id, tenant_id, ip, ua)
            return user

        # 3) Erişim yok — yükselt veya ek paket al
        etiket = krediler.MODUL_ETIKET.get(event_type, event_type)
        oturum_var = bool(user_id)
        if not oturum_var:
            mesaj = f"{etiket} kullanmak için ücretsiz hesap açın."
        elif min_tier:
            mesaj = (
                f"{etiket} bir Pro özelliğidir. Pro pakete geçebilir (sınırsız) "
                f"veya bu modülden ek paket alabilirsiniz."
            )
        else:
            mesaj = (
                f"Bu ayki {etiket} hakkınız doldu. Üst pakete geçebilir "
                f"veya ek paket alabilirsiniz."
            )
        raise HTTPException(
            402,
            {
                "error": "kota_doldu",
                "module": event_type,
                "modul_etiket": etiket,
                "tier": tier,
                "min_tier": min_tier,
                "can_buy": oturum_var,
                "packs": await krediler.modul_paketleri_async(event_type),
                "upgrade_url": "/panel/ayarlar/abonelik" if oturum_var else "/kayit",
                "message": mesaj,
                "reset_at": (donem_bit.isoformat() if limit is not None else None),
            },
        )

    return check
