from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_canli_kontrolu_200_doner():
    yanit = client.get("/canli")
    assert yanit.status_code == 200
    assert yanit.json()["durum"] == "calisiyor"


def test_saglik_kontrolu_200_doner(monkeypatch):
    monkeypatch.setattr("app.main.veritabani_erisilebilir_mi", lambda: True)
    monkeypatch.setattr("app.main.ldap_tcp_erisilebilir_mi", lambda: True)
    yanit = client.get("/saglik")
    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["durum"] == "calisiyor"
    assert govde["veritabani"] is True
    assert govde["ldap"] is True


def test_saglik_db_yoksa_503(monkeypatch):
    monkeypatch.setattr("app.main.veritabani_erisilebilir_mi", lambda: False)
    monkeypatch.setattr("app.main.ldap_tcp_erisilebilir_mi", lambda: True)
    yanit = client.get("/saglik")
    assert yanit.status_code == 503
    govde = yanit.json()
    assert govde["durum"] == "bozuk"
    assert govde["veritabani"] is False
    assert govde["ldap"] is True
    assert "host" not in govde
    assert "error" not in govde


def test_saglik_ldap_yoksa_503(monkeypatch):
    monkeypatch.setattr("app.main.veritabani_erisilebilir_mi", lambda: True)
    monkeypatch.setattr("app.main.ldap_tcp_erisilebilir_mi", lambda: False)
    yanit = client.get("/saglik")
    assert yanit.status_code == 503
    assert yanit.json()["ldap"] is False


def test_anasayfa_giris_yapmamis_kullaniciyi_girise_yonlendirir():
    from app.yetkilendirme import aktif_kullanici

    app.dependency_overrides.pop(aktif_kullanici, None)
    try:
        yanit = client.get("/", follow_redirects=False)
    finally:
        app.dependency_overrides[aktif_kullanici] = lambda: {
            "kullanici_adi": "test.kullanici",
            "ad_soyad": "Test Kullanici",
            "unvan": "Test Unvani",
            "gruplar": ["AFH-Calisanlar"],
            "manager": "onur.simsek",
            "manager_zinciri": ["onur.simsek", "emre.turan", "baris.kocak"],
            "rol": "calisan",
        }
    assert yanit.status_code == 303
    assert yanit.headers["location"] == "/giris"


def test_gelistirmede_docs_acik():
    """Gelistirmede OpenAPI dokumanlari kullanilabilir (production'da kapali)."""
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_guvenlik_basliklari_mevcut():
    yanit = client.get("/canli")
    assert yanit.headers.get("x-content-type-options") == "nosniff"
    assert yanit.headers.get("x-frame-options") == "DENY"
    assert "strict-origin" in (yanit.headers.get("referrer-policy") or "")
