from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_saglik_kontrolu_200_doner():
    yanit = client.get("/saglik")
    assert yanit.status_code == 200
    assert yanit.json()["durum"] == "calisiyor"


def test_anasayfa_giris_yapmamis_kullaniciyi_girise_yonlendirir():
    yanit = client.get("/", follow_redirects=False)
    assert yanit.status_code == 303
    assert yanit.headers["location"] == "/giris"
