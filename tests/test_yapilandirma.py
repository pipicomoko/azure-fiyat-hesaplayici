"""BUG-05 / BUG-08: production yapilandirma guard'lari."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.yapilandirma import (
    GELISTIRME_SECRET_KEY,
    fastapi_docs_kwargs,
    oturum_secret_key,
)


def test_gelistirmede_varsayilan_secret_kullanilir(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    assert oturum_secret_key() == GELISTIRME_SECRET_KEY


def test_gelistirmede_ozel_secret_kullanilir(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "lokal-ozel-anahtar")
    assert oturum_secret_key() == "lokal-ozel-anahtar"


def test_production_eksik_secret_reddedilir(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        oturum_secret_key()


def test_production_gelistirme_varsayilani_reddedilir(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", GELISTIRME_SECRET_KEY)
    with pytest.raises(RuntimeError, match="SECRET_KEY|zayif|gelistirme"):
        oturum_secret_key()


def test_production_kisa_secret_reddedilir(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "kisa-ama-varsayilan-degil")
    with pytest.raises(RuntimeError, match="32"):
        oturum_secret_key()


def test_production_guclu_secret_kabul(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    guclu = "a" * 32
    monkeypatch.setenv("SECRET_KEY", guclu)
    assert oturum_secret_key() == guclu


def test_gelistirmede_docs_kwargs_bos(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    assert fastapi_docs_kwargs() == {}


def test_production_docs_openapi_kapali(monkeypatch):
    """BUG-08: uretimde /docs /redoc /openapi.json 404."""
    monkeypatch.setenv("APP_ENV", "production")
    kwargs = fastapi_docs_kwargs()
    assert kwargs == {"docs_url": None, "redoc_url": None, "openapi_url": None}
    mini = FastAPI(**kwargs)
    istemci = TestClient(mini)
    assert istemci.get("/docs").status_code == 404
    assert istemci.get("/redoc").status_code == 404
    assert istemci.get("/openapi.json").status_code == 404
