"""api/routers/v1.py — Public API anahtarı yetkilendirmesi.

KİLİTLENEN AÇIK: `require_api_key` yalnızca `api_keys.aktif = TRUE` kontrol
ediyor, `users` tablosuna hiç JOIN yapmıyordu. Sonuç: admin panelinden askıya
alınan (is_active=FALSE) veya kısıtlanan (restricted_at) bir kullanıcı, daha
önce ürettiği `he_live_...` anahtarıyla API'yi kullanmaya DEVAM ediyordu.
JWT ve eklenti token yolları is_active'i kontrol ediyordu; burası tek istisnaydı.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
V1_KAYNAK = (ROOT / "api" / "routers" / "v1.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Sorgunun kendisi (statik kontrol — DB olmadan da regresyonu yakalar)
# ---------------------------------------------------------------------------

def test_sorgu_users_tablosuna_join_yapiyor():
    assert re.search(r"JOIN\s+users\s+u\s+ON\s+u\.id\s*=\s*ak\.user_id",
                     V1_KAYNAK, re.IGNORECASE), \
        "api_keys sorgusu users tablosuna JOIN yapmıyor — askıya alınan " \
        "kullanıcının anahtarı çalışmaya devam eder."


def test_sorgu_is_active_kontrol_ediyor():
    assert re.search(r"u\.is_active\s*=\s*TRUE", V1_KAYNAK, re.IGNORECASE), \
        "is_active kontrolü yok — suspend edilen hesap API'den erişebilir."


def test_sorgu_restricted_at_kontrol_ediyor():
    assert re.search(r"u\.restricted_at\s+IS\s+NULL", V1_KAYNAK, re.IGNORECASE), \
        "restricted_at kontrolü yok — kısıtlanan hesap API'den erişebilir."


def test_anahtarin_kendisi_de_aktif_olmali():
    assert re.search(r"ak\.aktif\s*=\s*TRUE", V1_KAYNAK, re.IGNORECASE)


# ---------------------------------------------------------------------------
# Suspend akışı anahtarları da iptal ediyor mu?
# ---------------------------------------------------------------------------

def test_suspend_api_anahtarlarini_da_iptal_ediyor():
    kaynak = (ROOT / "api" / "routers" / "admin.py").read_text(encoding="utf-8")
    m = re.search(r"async def admin_suspend_user.*?(?=\n@router)", kaynak, re.DOTALL)
    assert m, "admin_suspend_user bulunamadı"
    govde = m.group(0)
    assert "api_keys" in govde and "aktif = FALSE" in govde, \
        "Hesap askıya alınırken API anahtarları iptal edilmiyor (cascade revoke yok)."


# ---------------------------------------------------------------------------
# Davranışsal: sahte DB ile
# ---------------------------------------------------------------------------

class _SahteConn:
    """fetchrow None döndürür → kullanıcı pasif/kısıtlı senaryosu."""

    def __init__(self, row=None):
        self._row = row

    async def fetchrow(self, *a, **kw):
        return self._row

    async def execute(self, *a, **kw):
        return None


class _SahteSession:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *a):
        return False


@pytest.mark.asyncio
async def test_pasif_kullanicinin_anahtari_401(monkeypatch):
    """JOIN filtresi satır döndürmediğinde 401 verilmeli."""
    import api.routers.v1 as v1
    from fastapi import HTTPException

    monkeypatch.setattr(v1, "service_session", lambda: _SahteSession(_SahteConn(None)))

    with pytest.raises(HTTPException) as ex:
        await v1.require_api_key(x_api_key="he_live_abc123")
    assert ex.value.status_code == 401


@pytest.mark.asyncio
async def test_anahtarsiz_istek_401():
    import api.routers.v1 as v1
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ex:
        await v1.require_api_key(x_api_key=None)
    assert ex.value.status_code == 401


@pytest.mark.asyncio
async def test_yanlis_onekli_anahtar_db_ye_hic_gitmez(monkeypatch):
    """`he_` öneki yoksa DB sorgusu bile yapılmamalı (ucuz reddetme)."""
    import api.routers.v1 as v1
    from fastapi import HTTPException

    def _patlat():
        raise AssertionError("DB'ye gidilmemeliydi")

    monkeypatch.setattr(v1, "service_session", _patlat)
    with pytest.raises(HTTPException) as ex:
        await v1.require_api_key(x_api_key="baska_onek_xyz")
    assert ex.value.status_code == 401
