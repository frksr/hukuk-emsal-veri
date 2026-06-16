"""Faiz hesaplama router — deterministik Decimal aritmetiği (LLM yok)."""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.deps import rate_limit
from api.auth import get_optional_user, CurrentUser
from api.schemas import APIResponse, FaizIstegi
from services.faiz_hesaplayici import hesapla, FAIZ_TABLOLARI, UYARI_METNI
from services.uretim_gunlugu import kaydet_uretim

# Faiz türü etiketleri — geçmişte okunabilir başlık için.
_FAIZ_ETIKET = {
    "yasal": "Yasal faiz",
    "ticari_avans": "Ticari avans faizi",
    "tcmb_reeskont": "TCMB reeskont faizi",
}

log = logging.getLogger("api.faiz")
router = APIRouter()


def _json_safe(value: Any) -> Any:
    """Decimal ve date değerlerini JSON-uyumlu hale getir."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    return value


@router.post("/", response_model=APIResponse,
             summary="Temerrüt faizi + İİK harç + vekalet hesabı")
async def faiz_hesapla(
    istek: FaizIstegi,
    background: BackgroundTasks,
    _=Depends(rate_limit),
    user: CurrentUser | None = Depends(get_optional_user),
) -> APIResponse:
    """TBK 88 yasal / TCMB ticari avans / reeskont faiz türleri için hesaplar.

    Yanıt Decimal değerleri string olarak JSON'a serileştirilir.
    """
    if istek.faiz_turu not in FAIZ_TABLOLARI:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Geçersiz faiz_turu: {istek.faiz_turu!r}. "
                f"Geçerli: {list(FAIZ_TABLOLARI.keys())}"
            ),
        )
    if istek.anapara is None or istek.anapara < 0:
        raise HTTPException(status_code=400, detail="Anapara negatif olamaz.")

    try:
        sonuc = hesapla(
            anapara=istek.anapara,
            temerrut_tarihi=istek.temerrut_tarihi,
            vade_tarihi=istek.vade_tarihi,
            faiz_turu=istek.faiz_turu,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("Faiz hesabı başarısız")
        raise HTTPException(status_code=500, detail=f"Hesap başarısız: {e}")

    if user:
        etiket = _FAIZ_ETIKET.get(istek.faiz_turu, istek.faiz_turu)
        baslik = f"Faiz hesabı — {etiket}"
        girdi = f"Anapara: {istek.anapara} ₺ · Temerrüt: {istek.temerrut_tarihi}"
        if istek.vade_tarihi:
            girdi += f" · Vade: {istek.vade_tarihi}"
        cikti = (
            f"Faiz tutarı: {sonuc.get('faiz_tutari')} ₺\n"
            f"Toplam alacak: {sonuc.get('toplam_alacak')} ₺\n"
            f"Gün sayısı: {sonuc.get('gun_sayisi')}\n"
            f"Cezaevi harcı: {sonuc.get('cezaevi_harci')} ₺ · "
            f"Tahsil harcı: {sonuc.get('tahsil_harci')} ₺ · "
            f"Vekalet: {sonuc.get('vekalet_ucreti')} ₺"
        )
        background.add_task(
            kaydet_uretim, user.user_id, user.tenant_id, "faiz",
            alt_tur=istek.faiz_turu, baslik=baslik, girdi_ozeti=girdi, cikti=cikti,
            meta={"faiz_turu": istek.faiz_turu},
        )
    return APIResponse(ok=True, data=_json_safe(sonuc), message=UYARI_METNI)


@router.get("/options", response_model=APIResponse,
            summary="Desteklenen faiz türleri ve oran tabloları")
async def faiz_options() -> APIResponse:
    """Geçerli faiz türleri ve yıl bazlı oranları döndürür."""
    from services.faiz_oranlari import oran_meta, oran_overrides

    # Statik fallback + JSON override'larını birleştirerek dön
    oranlar: dict = {}
    for tur, tablo in FAIZ_TABLOLARI.items():
        birlesik = dict(tablo)
        try:
            birlesik.update(oran_overrides(tur))
        except Exception:
            pass
        oranlar[tur] = birlesik

    data = {
        "faiz_turleri": list(FAIZ_TABLOLARI.keys()),
        "oranlar": oranlar,
        "oran_kaynagi": oran_meta(),
        "uyari": UYARI_METNI,
    }
    return APIResponse(ok=True, data=data)
