from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_saglik_kontrolu_200_doner():
    yanit = client.get("/saglik")
    assert yanit.status_code == 200
    assert yanit.json()["durum"] == "calisiyor"


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
