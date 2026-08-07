"""Plan limitleri tek kaynaktan mı geliyor? (api/routers/billing.PLAN_LIMITS)

Eskiden aynı CASE WHEN bloğu üç yerde kopyalıydı (callback inline,
_tenant_plani_uygula, admin.manual_upgrade). Yeni bir plan eklendiğinde
biri unutulursa admin paneli ile ödeme webhook'u FARKLI limitler yazıyordu.
Bu testler o tekilliği ve tabloyla şema arasındaki tutarlılığı kilitler.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from api.routers.billing import PLAN_LIMITS, plan_limitleri

ROOT = Path(__file__).resolve().parent.parent

#: services/billing.PLAN_PRICING'de satılan planlar + ücretsiz/kurumsal
BEKLENEN_PLANLAR = {
    "free", "pro_solo", "pro_solo_uyap", "team", "team_uyap", "enterprise",
}


def test_tum_planlar_tanimli():
    assert set(PLAN_LIMITS) == BEKLENEN_PLANLAR


def test_her_planda_ucu_de_var():
    for plan, lim in PLAN_LIMITS.items():
        assert set(lim) == {"max_uyap_documents", "max_monthly_queries", "max_users"}, plan
        assert all(isinstance(v, int) and v >= 0 for v in lim.values()), plan


def test_satilan_planlar_pricing_ile_ortusuyor():
    """PLAN_PRICING'e yeni bir plan eklenirse limit tablosu da güncellenmeli."""
    from services.billing import PLAN_PRICING

    eksik = set(PLAN_PRICING) - set(PLAN_LIMITS)
    assert not eksik, f"PLAN_LIMITS'te limiti tanımlanmamış plan(lar): {eksik}"


@pytest.mark.parametrize("plan", ["team", "team_uyap"])
def test_team_planlari_cok_kullanicili(plan):
    assert PLAN_LIMITS[plan]["max_users"] > 1


@pytest.mark.parametrize("plan", ["free", "pro_solo"])
def test_uyapsiz_planlarda_uyap_kotasi_sifir(plan):
    assert PLAN_LIMITS[plan]["max_uyap_documents"] == 0
    assert PLAN_LIMITS[plan]["max_monthly_queries"] == 0


@pytest.mark.parametrize("plan", ["pro_solo_uyap", "team_uyap", "enterprise"])
def test_uyapli_planlarda_kota_pozitif(plan):
    assert PLAN_LIMITS[plan]["max_uyap_documents"] > 0
    assert PLAN_LIMITS[plan]["max_monthly_queries"] > 0


def test_bilinmeyen_plan_en_kisitli_limite_duser():
    """Şema/enum değişirse sessizce yüksek limit VERİLMEZ."""
    assert plan_limitleri("bilinmeyen_plan") == PLAN_LIMITS["free"]


def test_limit_case_when_bloklari_kodda_kalmadi():
    """Regresyon kilidi: kopyalanmış CASE WHEN blokları geri gelmesin."""
    desen = re.compile(r"max_uyap_documents\s*=\s*CASE", re.IGNORECASE)
    suclu = []
    for f in (ROOT / "api").rglob("*.py"):
        if desen.search(f.read_text(encoding="utf-8")):
            suclu.append(str(f.relative_to(ROOT)))
    assert not suclu, (
        "Plan limitleri yine SQL içine gömülmüş: "
        f"{suclu}. Bunun yerine billing.plan_limitleri() kullanın."
    )
