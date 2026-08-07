"""API entegrasyon testleri için ortak yardımcılar.

FastAPI uygulamasını DB'siz ayağa kaldırmak için gereken asgari sahte katman:
`get_current_user` / `require_admin` gibi dependency'ler `app.dependency_overrides`
ile değiştirilir, DB'ye giden yollar test bazında monkeypatch'lenir.

Bu dosya `conftest.py` DEĞİL — pytest tarafından otomatik yüklenmez; test
dosyaları açıkça `from tests.conftest_api import ...` ile alır.
"""
from __future__ import annotations

import os
from typing import Iterator

import pytest

# TestClient uygulamayı import etmeden ÖNCE ayarlanmalı: api.main import
# anında env okuyor.
os.environ.setdefault("NEXTAUTH_SECRET", "test-secret-yalnizca-testlerde")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("TRUSTED_PROXY_HOPS", "1")


def kullanici(
    user_id: str = "11111111-1111-1111-1111-111111111111",
    email: str = "avukat@example.com",
    role: str = "user",
    tenant_id: str | None = "22222222-2222-2222-2222-222222222222",
    tenant_plan: str = "pro_solo",
    email_verified: bool = True,
    restricted: bool = False,
):
    """Test için CurrentUser üret."""
    from api.auth import CurrentUser

    return CurrentUser(
        user_id=user_id, email=email, name="Test Avukat", role=role,
        tenant_id=tenant_id, tenant_plan=tenant_plan, tenant_role="owner",
        email_verified=email_verified, restricted=restricted,
    )


@pytest.fixture
def app():
    from api.main import app as fastapi_app

    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def client(app) -> Iterator:
    """Lifespan ÇALIŞTIRILMADAN TestClient — DB havuzu açılmasın."""
    from starlette.testclient import TestClient

    # TestClient(app) normalde lifespan'i çalıştırır ve init_pool() DB arar.
    # raise_server_exceptions=False: 500'leri yanıt olarak görebilelim.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def client_no_lifespan(app) -> Iterator:
    """Context manager kullanmayan istemci — lifespan hiç tetiklenmez."""
    from starlette.testclient import TestClient

    yield TestClient(app, raise_server_exceptions=False)


def giris_yap(app, user=None, admin: bool = False):
    """`get_current_user` (ve admin gerekiyorsa `require_admin`) override eder."""
    from api.auth import get_current_user, require_admin

    u = user or kullanici(role="admin" if admin else "user")
    app.dependency_overrides[get_current_user] = lambda: u
    app.dependency_overrides[require_admin] = lambda: u
    return u


def cikis_yap(app):
    app.dependency_overrides.clear()
