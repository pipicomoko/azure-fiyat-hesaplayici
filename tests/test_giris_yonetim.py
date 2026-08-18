from fastapi.testclient import TestClient

import app.routers.giris as giris_modulu
from app.main import app
from app.yetkilendirme import aktif_kullanici

client = TestClient(app)

_ORNEK_CALISAN = {
    "kullanici_adi": "zeynep.kara",
    "ad_soyad": "Zeynep Kara",
    "unvan": "IK Uzmani",
    "gruplar": ["Calisanlar"],
}

_ORNEK_ADMIN = {
    "kullanici_adi": "can.aydin",
    "ad_soyad": "Can Aydin",
    "unvan": "Sistem Yoneticisi",
    "gruplar": ["Adminler", "Calisanlar"],
}


def test_giris_formu_acilir():
    yanit = client.get("/giris")
    assert yanit.status_code == 200
    assert "Giris Yap" in yanit.text


def test_giris_yapmadan_tahmine_giris_sayfasina_yonlendirir():
    # conftest.py'deki autouse fixture varsayilan olarak sahte bir oturum
    # acar; bu test ozellikle oturumSUZ durumu kontrol ettigi icin gecici
    # olarak kaldirir.
    app.dependency_overrides.pop(aktif_kullanici, None)
    try:
        yanit = client.get("/tahmin", follow_redirects=False)
    finally:
        app.dependency_overrides[aktif_kullanici] = lambda: _ORNEK_CALISAN

    assert yanit.status_code == 303
    assert yanit.headers["location"] == "/giris"


def test_dogru_bilgilerle_giris_tahmine_yonlendirir(monkeypatch):
    monkeypatch.setattr(giris_modulu, "giris_dogrula", lambda k, s: _ORNEK_CALISAN)

    yanit = client.post(
        "/giris",
        data={"kullanici_adi": "zeynep.kara", "sifre": "herhangi"},
        follow_redirects=False,
    )

    assert yanit.status_code == 303
    assert yanit.headers["location"] == "/tahmin"


def test_yanlis_bilgilerle_giris_reddedilir(monkeypatch):
    monkeypatch.setattr(giris_modulu, "giris_dogrula", lambda k, s: None)

    yanit = client.post(
        "/giris",
        data={"kullanici_adi": "zeynep.kara", "sifre": "yanlis"},
    )

    assert yanit.status_code == 401
    assert "hatali" in yanit.text


def test_calisan_yonetim_sayfasina_403_alir():
    app.dependency_overrides[aktif_kullanici] = lambda: _ORNEK_CALISAN
    try:
        yanit = client.get("/yonetim")
    finally:
        app.dependency_overrides.pop(aktif_kullanici, None)

    assert yanit.status_code == 403


def test_admin_yonetim_sayfasina_girebilir():
    app.dependency_overrides[aktif_kullanici] = lambda: _ORNEK_ADMIN
    try:
        yanit = client.get("/yonetim")
    finally:
        app.dependency_overrides.pop(aktif_kullanici, None)

    assert yanit.status_code == 200
    assert "Adminler" in yanit.text


def test_yetkisiz_kullanici_tahmin_ucuna_dogrudan_istekle_de_erisemez():
    """Frontend'de gizlenen bir islem, API'ye dogrudan istek atarak
    atlatilamamalidir: gruplarindan hicbiri eslenmemis bir kullanici
    /tahmin/kalem-ekle'ye dogrudan POST atsa bile 403 almalidir."""
    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "yetkisiz.kullanici", "ad_soyad": "Yetkisiz", "unvan": "", "gruplar": ["TanimsizGrup"],
    }
    try:
        yanit = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks"})
    finally:
        app.dependency_overrides.pop(aktif_kullanici, None)

    assert yanit.status_code == 403


def test_cikis_giris_sayfasina_yonlendirir():
    yanit = client.get("/cikis", follow_redirects=False)
    assert yanit.status_code == 303
    assert yanit.headers["location"] == "/giris"
