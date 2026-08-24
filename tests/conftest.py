import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import oturum_al
from app.guvenlik import giris_hiz_siniri_sifirla
from app.main import app
from app.yetkilendirme import aktif_kullanici

_TEST_KULLANICISI = {
    "kullanici_adi": "test.kullanici",
    "ad_soyad": "Test Kullanici",
    "unvan": "Test Unvani",
    "gruplar": ["AFH-Calisanlar"],
    "manager": "onur.simsek",
    "manager_zinciri": ["onur.simsek", "emre.turan", "baris.kocak"],
    "rol": "calisan",
}


def csrf_hazirla(client: TestClient) -> str:
    """Session + X-CSRF-Token baslat (BUG-17)."""
    yanit = client.get("/canli")
    assert yanit.status_code == 200
    token = client.cookies.get("csrf_token")
    if not token:
        giris = client.get("/giris")
        m = re.search(r'name="csrf-token" content="([^"]+)"', giris.text)
        token = m.group(1) if m else ""
    if token:
        client.headers["X-CSRF-Token"] = token
    return token or ""


@pytest.fixture
def client():
    c = TestClient(app)
    csrf_hazirla(c)
    return c


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    """Testlerdeki korumali uclar icin sahte (mock) bir oturum acmis kullanici.
    Gercek LDAP'a hic gidilmez."""
    app.dependency_overrides[aktif_kullanici] = lambda: _TEST_KULLANICISI
    yield
    app.dependency_overrides.pop(aktif_kullanici, None)


@pytest.fixture(autouse=True)
def _giris_hiz_siniri_temizle():
    giris_hiz_siniri_sifirla()
    yield
    giris_hiz_siniri_sifirla()


@pytest.fixture
def veritabani():
    """Bellekte tek seferlik bir SQLite motoru + oturum_al override'i.

    poolclass=StaticPool sart: FastAPI senkron dependency'leri ayri bir
    thread'de calistirir; StaticPool olmadan bellek-ici SQLite her thread'de
    sifirdan baslar, "tablo bulunamadi" hatasi verir.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def _oturum_al():
        with Session(engine) as oturum:
            yield oturum

    app.dependency_overrides[oturum_al] = _oturum_al
    yield engine
    app.dependency_overrides.pop(oturum_al, None)
