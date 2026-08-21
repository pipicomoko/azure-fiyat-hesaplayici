from fastapi.testclient import TestClient

import app.routers.giris as giris_modulu
from app.main import app
from app.yetkilendirme import LdapTlsHatasi, aktif_kullanici

client = TestClient(app)

_ORNEK_CALISAN = {
    "kullanici_adi": "zeynep.kara",
    "ad_soyad": "Zeynep Kara",
    "unvan": "IK Uzmani",
    "gruplar": ["AFH-Calisanlar"],
}

_ORNEK_ADMIN = {
    "kullanici_adi": "asli.demirtas",
    "ad_soyad": "Asli Demirtas",
    "unvan": "Sistem Yoneticisi",
    "gruplar": ["AFH-Adminler"],
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
    assert yanit.headers["location"] == "/"


def test_admin_giris_aktiviteye_yonlendirir(monkeypatch):
    """Admin hesaplama.kullan yetkisine sahip degildir; / yerine audit sayfasina gider."""
    monkeypatch.setattr(giris_modulu, "giris_dogrula", lambda k, s: _ORNEK_ADMIN)

    yanit = client.post(
        "/giris",
        data={"kullanici_adi": "asli.demirtas", "sifre": "herhangi"},
        follow_redirects=False,
    )

    assert yanit.status_code == 303
    assert yanit.headers["location"] == "/admin/aktivite"


def test_yanlis_bilgilerle_giris_reddedilir(monkeypatch):
    monkeypatch.setattr(giris_modulu, "giris_dogrula", lambda k, s: None)

    yanit = client.post(
        "/giris",
        data={"kullanici_adi": "zeynep.kara", "sifre": "yanlis"},
    )

    assert yanit.status_code == 401
    assert "hatali" in yanit.text


def test_ldap_tls_hatasi_yanlis_sifre_gibi_gosterilmez(monkeypatch):
    def tls_hata(kullanici_adi, sifre):
        raise LdapTlsHatasi()

    monkeypatch.setattr(giris_modulu, "giris_dogrula", tls_hata)

    yanit = client.post(
        "/giris",
        data={"kullanici_adi": "zeynep.kara", "sifre": "herhangi"},
    )

    assert yanit.status_code == 503
    assert "hatali" not in yanit.text
    assert "TLS" in yanit.text


def test_calisan_yonetim_sayfasina_erisemez():
    app.dependency_overrides[aktif_kullanici] = lambda: _ORNEK_CALISAN
    try:
        yanit = client.get("/yonetim")
    finally:
        app.dependency_overrides.pop(aktif_kullanici, None)

    assert yanit.status_code in (403, 404)


def test_yonetim_sayfasi_gecici_olarak_kapalidir():
    app.dependency_overrides[aktif_kullanici] = lambda: _ORNEK_ADMIN
    try:
        yanit = client.get("/yonetim")
    finally:
        app.dependency_overrides.pop(aktif_kullanici, None)

    assert yanit.status_code == 404


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


def test_uc_kullanici_ayni_anda_bagimsiz_oturum_acar(monkeypatch):
    def sahte_dogrula(kullanici_adi, sifre):
        return {
            "kullanici_adi": kullanici_adi,
            "ad_soyad": kullanici_adi,
            "unvan": "",
            "gruplar": ["AFH-Calisanlar"],
        }

    monkeypatch.setattr(giris_modulu, "giris_dogrula", sahte_dogrula)
    app.dependency_overrides.pop(aktif_kullanici, None)

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def giris_yap(kullanici_adi: str) -> tuple[int, int, str]:
        yerel = TestClient(app)
        yanit = yerel.post(
            "/giris",
            data={"kullanici_adi": kullanici_adi, "sifre": "herhangi"},
            follow_redirects=False,
        )
        tahmin = yerel.get("/tahmin", follow_redirects=False)
        return yanit.status_code, tahmin.status_code, kullanici_adi

    try:
        with ThreadPoolExecutor(max_workers=3) as havuz:
            isler = [havuz.submit(giris_yap, adi) for adi in ("ali", "ayse", "mehmet")]
            sonuclar = [is_.result() for is_ in as_completed(isler)]
    finally:
        app.dependency_overrides[aktif_kullanici] = lambda: _ORNEK_CALISAN

    assert len(sonuclar) == 3
    assert all(giris_kodu == 303 and tahmin_kodu == 200 for giris_kodu, tahmin_kodu, _ in sonuclar)
