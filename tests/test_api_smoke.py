"""API uçlarının HTTP seviyesinde ilk entegrasyon testleri.

BOŞLUK: 30 router'ın (auth, billing, arama, uyap, admin, publisher dahil)
hiçbiri `TestClient` ile test edilmiyordu. Regresyonlar ancak production'da
veya elle smoke test ile fark ediliyordu.

Bu dosya DB gerektirmez: dependency override + monkeypatch ile çalışır.
Kapsam bilinçli olarak "sözleşme" seviyesinde: kimlik doğrulama kapıları,
yanıt biçimi, güvenlik header'ları, hata gövdesi.
"""
from __future__ import annotations

import pytest

from tests.conftest_api import (  # noqa: F401  (fixture'lar)
    app,
    cikis_yap,
    client,
    giris_yap,
    kullanici,
)


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------

def test_health_liveness_dbsiz_calisir(client):
    """Liveness bağımlılıklara BAKMAZ — DB yokken bile 200 dönmeli."""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_ready_db_yoksa_503(client):
    """Readiness DB'yi kontrol eder. Eskiden tek bir /api/health vardı ve DB'ye
    hiç dokunmuyordu: Postgres düştüğünde LB hâlâ 200 görüyordu."""
    r = client.get("/api/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["ok"] is False
    assert body["db"]["ok"] is False


def test_health_ve_ready_farkli_davranir(client):
    """İkisi aynı şeyi yapıyorsa readiness ayrımı anlamsızdır."""
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/ready").status_code == 503


# ---------------------------------------------------------------------------
# Korelasyon kimliği
# ---------------------------------------------------------------------------

def test_her_yanitta_request_id_var(client):
    r = client.get("/api/health")
    assert r.headers.get("X-Request-Id")
    assert r.headers.get("X-Response-Time-ms")


def test_istemci_request_id_korunur(client):
    """Next.js proxy'si uçtan uca izleme için kendi kimliğini gönderebilir."""
    r = client.get("/api/health", headers={"X-Request-Id": "abc123XYZ"})
    assert r.headers["X-Request-Id"] == "abc123XYZ"


def test_zararli_request_id_temizlenir():
    """Log enjeksiyonu / sınırsız uzunluk engellenmeli."""
    from starlette.requests import Request

    from api.logging_setup import new_request_id

    def _req(v):
        return Request({"type": "http", "method": "GET", "path": "/",
                        "headers": [(b"x-request-id", v.encode())], "client": ("1.1.1.1", 1)})

    assert "\n" not in new_request_id(_req("kotu\ndeger"))
    assert len(new_request_id(_req("x" * 500))) <= 64
    assert new_request_id(_req("!!!"))  # tamamen geçersizse yeni üretilir


# ---------------------------------------------------------------------------
# Güvenlik: kimlik doğrulama kapıları
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("yol", [
    "/api/me/",
    "/api/me/kullanim",
    "/api/me/api-keys",
    "/api/me/kararlar",
    "/api/billing/current",
    "/api/billing/invoices",
    "/api/admin/dashboard",
    "/api/admin/users",
])
def test_korumali_uclar_tokensiz_401(client, yol):
    r = client.get(yol)
    assert r.status_code in (401, 403), f"{yol} korumasız! → {r.status_code}"


#: Kimlik doğrulaması İSTEMEYEN uçlar — bilinçli olarak public.
#: Buraya bir yol eklemek "bu uç herkese açık olsun" kararıdır; hafife almayın.
PUBLIC_GET_UCLARI = {
    "/api/health",                      # liveness (LB)
    "/api/ready",                       # readiness (LB)
    "/api/arama/stats",                 # anasayfa "N karar" sayacı
    "/api/billing/plans",               # fiyatlandırma sayfası
    "/api/billing/plan-limits",          # fiyatlandırma sayfası
    "/api/billing/addons",              # ek paket vitrini
    "/api/denetim/turler",              # form seçenekleri
    "/api/faiz/options",                # form seçenekleri
    "/api/kvkk/sektorler",              # form seçenekleri
    "/api/zamanasimi/kategoriler",      # form seçenekleri
    "/api/icerik/liste",                # public blog listesi
    "/api/karar/liste",                 # public karar listesi (SEO)
    # Trend paneli — anonim kullanıcıya da açık (pazarlama yüzeyi)
    "/api/trend/aylik",
    "/api/trend/yillik",
    "/api/trend/filtre-secenekleri",
    "/api/trend/kaynak-dagilimi",
    "/api/trend/konu-dagilimi",
    "/api/trend/mahkeme-konu",
    "/api/trend/top-mahkemeler",
    # Publisher: tek kullanımlık URL token'ı ile korunur (API key değil)
    "/api/publisher/approve",
    "/api/publisher/reject",
    "/api/publisher/health",            # Bearer ister → zaten 401/503
}


def test_hicbir_yeni_uc_yanlislikla_public_kalmasin(client):
    """OpenAPI şemasındaki TÜM GET uçlarını tokensiz dener.

    Yeni bir router eklenip auth dependency'si unutulursa bu test kırılır.
    Bilinçli public bir uç ekliyorsanız PUBLIC_GET_UCLARI'na yazın.
    """
    sema = client.get("/api/openapi.json").json()
    korumasiz: list[str] = []

    for yol, ops in sema["paths"].items():
        if "get" not in ops or "{" in yol:       # parametreli yolları atla
            continue
        if yol in PUBLIC_GET_UCLARI:
            continue
        r = client.get(yol)
        if r.status_code not in (401, 403):
            korumasiz.append(f"{yol} → {r.status_code}")

    assert not korumasiz, (
        "Kimlik doğrulaması olmadan erişilebilen uç(lar):\n  "
        + "\n  ".join(korumasiz)
        + "\n\nBilinçli olarak public ise PUBLIC_GET_UCLARI listesine ekleyin."
    )


def test_admin_ucu_normal_kullaniciya_kapali(app, client):
    """require_admin gerçekten rol kontrol ediyor mu?"""
    from api.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: kullanici(role="user")
    r = client.get("/api/admin/dashboard")
    assert r.status_code == 403
    cikis_yap(app)


def test_v1_api_key_header_olmadan_401(client):
    r = client.post("/api/v1/arama", json={"q": "icra"})
    assert r.status_code == 401


def test_v1_gecersiz_onekli_anahtar_401(client):
    r = client.post("/api/v1/arama", json={"q": "icra"},
                    headers={"X-API-Key": "yanlis_onek_123"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Public uçlar
# ---------------------------------------------------------------------------

def test_plans_public_ve_liste_doner(client):
    r = client.get("/api/billing/plans")
    assert r.status_code == 200
    data = r.json()["data"]
    assert isinstance(data["plans"], list) and data["plans"]
    for p in data["plans"]:
        assert {"key", "name", "amount_try", "currency"} <= set(p)


def test_openapi_semasi_uretiliyor(client):
    """Şema bozulursa /api/docs de çöker."""
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    assert r.json()["paths"]


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def test_cors_preflight_delete_icin_izin_verir(client):
    """API PATCH/PUT/DELETE uçları içeriyor; eski allow_methods listesi
    yalnızca GET/POST/OPTIONS'tı ve bu uçlar tarayıcıdan çağrılamıyordu."""
    r = client.options("/api/me/profil", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "DELETE",
    })
    assert r.status_code in (200, 204)
    izinli = r.headers.get("access-control-allow-methods", "")
    assert "DELETE" in izinli and "PATCH" in izinli


def test_bilinmeyen_origin_reddedilir(client):
    r = client.options("/api/me/profil", headers={
        "Origin": "https://kotu-site.example",
        "Access-Control-Request-Method": "GET",
    })
    assert "kotu-site" not in r.headers.get("access-control-allow-origin", "")


# ---------------------------------------------------------------------------
# Hata gövdesi
# ---------------------------------------------------------------------------

def test_bilinmeyen_yol_404(client):
    assert client.get("/api/boyle-bir-uc-yok").status_code == 404


def test_gecersiz_govde_422(app, client):
    giris_yap(app)
    r = client.post("/api/billing/checkout", json={})   # plan_tier eksik
    assert r.status_code in (400, 422)
    cikis_yap(app)
