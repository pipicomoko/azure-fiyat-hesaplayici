"""Claude audit BUG-12..18 + 2. tur (BUG-06/16, YENI-01) regresyon testleri."""

from __future__ import annotations

import pytest
from starlette.requests import Request as StarletteRequest

from app.guvenlik import (
    giris_basarisiz_kaydet,
    giris_hiz_siniri_asildi_mi,
    giris_hiz_siniri_sifirla,
    istemci_ip,
    yerel_yonlendirme_yolu,
)
from app.products.base import GecersizYapilandirmaHatasi
from app.products.managed_disks import secenekler as disk_secenekler
from app.yapilandirma import uretim_ortami_mi


def test_yerel_yonlendirme_yolu_open_redirect_engeller():
    assert yerel_yonlendirme_yolu("https://evil.example/phish") == "/"
    assert yerel_yonlendirme_yolu("//evil.example") == "/"
    assert yerel_yonlendirme_yolu("/gecmis/taslaklar") == "/gecmis/taslaklar"
    assert yerel_yonlendirme_yolu("/gecmis?x=1") == "/gecmis?x=1"
    assert yerel_yonlendirme_yolu(None) == "/"


def test_yerel_yonlendirme_mutlak_referer_ayni_host():
    """YENI-01: tarayici mutlak Referer gonderince path korunur."""
    assert (
        yerel_yonlendirme_yolu(
            "https://afh.sirket.local/gecmis/taslaklar",
            izinli_host="afh.sirket.local",
        )
        == "/gecmis/taslaklar"
    )
    assert (
        yerel_yonlendirme_yolu(
            "https://ayni-sunucu:8099/tahmin",
            izinli_host="ayni-sunucu:8099",
        )
        == "/tahmin"
    )
    assert (
        yerel_yonlendirme_yolu(
            "https://kotu-site.example/x",
            izinli_host="afh.sirket.local",
        )
        == "/"
    )


def test_dil_referer_open_redirect_yerelde_kalir(client):
    yanit = client.post(
        "/dil",
        data={"dil": "en"},
        headers={"Referer": "https://evil.example/steal"},
        follow_redirects=False,
    )
    assert yanit.status_code == 303
    assert yanit.headers["location"] == "/"


def test_dil_referer_yerel_yol_korunur(client):
    yanit = client.post(
        "/dil",
        data={"dil": "en"},
        headers={"Referer": "/tahmin"},
        follow_redirects=False,
    )
    assert yanit.status_code == 303
    assert yanit.headers["location"] == "/tahmin"


def test_dil_mutlak_referer_ayni_host_path_korunur(client):
    """YENI-01: TestClient Host=testserver ile mutlak Referer."""
    yanit = client.post(
        "/dil",
        data={"dil": "en"},
        headers={"Referer": "http://testserver/gecmis/taslaklar"},
        follow_redirects=False,
    )
    assert yanit.status_code == 303
    assert yanit.headers["location"] == "/gecmis/taslaklar"


def test_kaydet_xss_hesaplama_adi_kacirilir(client, veritabani, monkeypatch):
    from tests.test_tahmin import _kalem_id_cikar, _sahte_disk_kayitlari

    monkeypatch.setattr(
        "app.products.managed_disks.fiyatlama.kayitlari_getir", _sahte_disk_kayitlari
    )
    payload = '"><img src=x onerror=alert(1)>'
    ekleme = client.post(
        "/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks", "para_birimi": "USD"}
    )
    assert ekleme.status_code == 200
    kalem_id = _kalem_id_cikar(ekleme.text)
    yanit = client.post(
        "/tahmin/kaydet",
        data={
            f"{kalem_id}.urun_tipi": "managed_disks",
            f"{kalem_id}.bolge": "eastus",
            f"{kalem_id}.kademe": "standardhdd",
            f"{kalem_id}.sku": "S4",
            f"{kalem_id}.yedeklilik": "LRS",
            f"{kalem_id}.adet": "1",
            "para_birimi": "USD",
            "hesaplama_adi": payload,
        },
    )
    assert yanit.status_code == 200
    # Etiket kirildi: < → &lt; (metinde "onerror" kalabilir, calismaz)
    assert "<img" not in yanit.text
    assert "&lt;img" in yanit.text
    assert "&quot;&gt;&lt;img" in yanit.text or "&lt;img src=x" in yanit.text


def test_guvenlik_basliklari_csp_mevcut(client):
    yanit = client.get("/canli")
    csp = yanit.headers.get("content-security-policy") or ""
    assert "default-src" in csp
    assert yanit.headers.get("x-frame-options") == "DENY"


def test_giris_cache_control(client):
    yanit = client.get("/giris")
    assert "no-store" in (yanit.headers.get("cache-control") or "")


def test_csrf_eksik_post_reddedilir():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    c.get("/canli")
    # Header/form yok → 403 (cookie tek basina yetmez)
    c.headers.pop("X-CSRF-Token", None)
    yanit = c.post("/dil", data={"dil": "en"}, follow_redirects=False)
    assert yanit.status_code == 403


def test_gecersiz_disk_sku_hata_firlatir():
    with pytest.raises(GecersizYapilandirmaHatasi):
        disk_secenekler.secenekleri_coz(
            {"bolge": "eastus", "kademe": "standardhdd", "sku": "HACKED", "adet": 1},
            "tr",
        )


def test_gecersiz_disk_adet_hata_firlatir():
    with pytest.raises(GecersizYapilandirmaHatasi):
        disk_secenekler.secenekleri_coz(
            {"bolge": "eastus", "kademe": "standardhdd", "sku": "S4", "adet": "abc"},
            "tr",
        )
    with pytest.raises(GecersizYapilandirmaHatasi):
        disk_secenekler.secenekleri_coz(
            {"bolge": "eastus", "kademe": "standardhdd", "sku": "S4", "adet": 0},
            "tr",
        )


def test_vm_gomulu_disk_adet_sifir_izinli():
    """VM varsayilaninda disk adet=0 (disk yok); tum roller icin kalem-ekle kirilmamali."""
    from app.products.virtual_machines.secenekler import bos_yapilandirma as vm_bos

    disk = vm_bos()["disk"]
    assert disk.get("adet") == 0
    sonuc = disk_secenekler.secenekleri_coz(disk, "tr", min_adet=0)
    assert sonuc.yapilandirma["adet"] == 0


def test_gecersiz_kademe_hata_firlatir():
    with pytest.raises(GecersizYapilandirmaHatasi):
        disk_secenekler.secenekleri_coz(
            {"bolge": "eastus", "kademe": "uydurma", "sku": "S4", "adet": 1},
            "tr",
        )


def test_kademe_degisiminde_eski_sku_cascade_olur():
    """S4 HDD SKU'su SSD'ye gecince sessizce E1'e (tablo ilki) duzeltilir."""
    sonuc = disk_secenekler.secenekleri_coz(
        {"bolge": "eastus", "kademe": "standardssd", "sku": "S4", "adet": 1},
        "tr",
    )
    assert sonuc.yapilandirma["sku"] == "E1"


def _sahte_request(istemci_host: str, headers: dict[str, str] | None = None):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "client": (istemci_host, 12345),
        "server": ("testserver", 80),
    }
    return StarletteRequest(scope)


def test_istemci_ip_xff_varsayilan_yok_sayilir(monkeypatch):
    """BUG-16: X-Forwarded-For varsayilan olarak guvenilmez."""
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    req = _sahte_request("203.0.113.9", {"x-forwarded-for": "10.0.0.1"})
    assert istemci_ip(req) == "203.0.113.9"


def test_istemci_ip_xff_guvenilen_vekil_en_sag(monkeypatch):
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.0.0.2")
    req = _sahte_request("10.0.0.2", {"x-forwarded-for": "10.0.0.1, 198.51.100.7"})
    assert istemci_ip(req) == "198.51.100.7"


def test_giris_hiz_siniri(client, monkeypatch, veritabani):
    import app.routers.giris as giris_modulu

    monkeypatch.setattr(giris_modulu, "giris_dogrula", lambda k, s: None)
    giris_hiz_siniri_sifirla()
    for _ in range(5):
        yanit = client.post("/giris", data={"kullanici_adi": "x", "sifre": "y"})
        assert yanit.status_code == 401
    yanit = client.post("/giris", data={"kullanici_adi": "x", "sifre": "y"})
    assert yanit.status_code == 429


def test_giris_hiz_siniri_xff_ile_atlatilamaz(client, monkeypatch, veritabani):
    """BUG-16: her istekte farkli XFF yeni kota acmamali."""
    import app.routers.giris as giris_modulu

    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    monkeypatch.setattr(giris_modulu, "giris_dogrula", lambda k, s: None)
    giris_hiz_siniri_sifirla()
    for i in range(5):
        yanit = client.post(
            "/giris",
            data={"kullanici_adi": "hedef.kullanici", "sifre": "y"},
            headers={"X-Forwarded-For": f"10.0.0.{i + 1}"},
        )
        assert yanit.status_code == 401
    yanit = client.post(
        "/giris",
        data={"kullanici_adi": "hedef.kullanici", "sifre": "y"},
        headers={"X-Forwarded-For": "10.0.0.99"},
    )
    assert yanit.status_code == 429


def test_giris_hiz_siniri_kullanici_adi_bazli():
    """BUG-16: IP degisse bile ayni hesap dakikada 5 denemeyi asamaz."""
    giris_hiz_siniri_sifirla()
    for i in range(5):
        assert not giris_hiz_siniri_asildi_mi(f"203.0.113.{i}", "ayse.yilmaz")
        giris_basarisiz_kaydet(f"203.0.113.{i}", "ayse.yilmaz")
    assert giris_hiz_siniri_asildi_mi("198.51.100.1", "ayse.yilmaz")
    assert giris_hiz_siniri_asildi_mi("198.51.100.1", "Ayse.Yilmaz")


def test_https_only_uretimde_true(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    assert uretim_ortami_mi() is True
    monkeypatch.setenv("APP_ENV", "development")
    assert uretim_ortami_mi() is False


def test_gecmis_sayfalama_baglami():
    from app.routers.tahmin import GECMIS_SAYFA_BOYUTU, _sayfala

    kayitlar = list(range(GECMIS_SAYFA_BOYUTU + 3))
    dilim, meta = _sayfala(kayitlar, sayfa=1)
    assert len(dilim) == GECMIS_SAYFA_BOYUTU
    assert meta["toplam_sayfa"] == 2
    assert meta["sonraki_sayfa"] == 2


def test_gecmis_excel_maks_kayit_sabiti():
    from app.routers.tahmin import GECMIS_EXCEL_MAKS_KAYIT

    assert GECMIS_EXCEL_MAKS_KAYIT == 500
