"""Tahmin calisma alani uc-uca (route seviyesinde) testleri.

Azure Retail Prices API'sine giden CANLI cagrilar burada MOCKLANIR (pricing
matematiginin dogrulugu tests/test_managed_disks_fiyatlama.py ve
tests/test_virtual_machines_fiyatlama.py'de ayrica, gercek API'den alinmis
sabit verilerle test edilir) -- bu dosya sadece HTTP/form/DB entegrasyonunu
dogrular: kalem ekleme, alan degisince yeniden hesaplama, kaydetme, disa
aktarma, gecmis/karsilastirma.
"""

import re

import pytest

from app.fiyat_api import onbellek_temizle
from app.models import Hesaplama

_S4_KAYITLARI = [
    {
        "meterName": "S4 LRS Disk", "skuName": "S4 LRS", "retailPrice": 1.536,
        "unitOfMeasure": "1/Month", "type": "Consumption", "productName": "Standard HDD Managed Disks",
        "effectiveStartDate": "2020-01-01",
    },
    {
        "meterName": "S4 LRS Disk Operations", "skuName": "S4 LRS", "retailPrice": 0.0005,
        "unitOfMeasure": "10K", "type": "Consumption", "productName": "Standard HDD Managed Disks",
        "effectiveStartDate": "2020-01-01",
    },
]


async def _sahte_disk_kayitlari(filtre, para_birimi="USD", onbellek_kullan=True):
    if "Standard HDD Managed Disks" in filtre:
        return _S4_KAYITLARI
    return []


@pytest.fixture(autouse=True)
def _fiyat_api_sahte(monkeypatch):
    onbellek_temizle()
    monkeypatch.setattr("app.products.managed_disks.fiyatlama.kayitlari_getir", _sahte_disk_kayitlari)
    yield
    onbellek_temizle()


def _kalem_id_cikar(html: str) -> str:
    return re.search(r'kalem-([a-f0-9]+)"', html).group(1)


def test_tahmin_sayfasi_acilir(client):
    yanit = client.get("/tahmin")
    assert yanit.status_code == 200
    assert "Tahminim" in yanit.text


def test_kalem_ekle_disk_varsayilan_fiyatla_doner(client):
    yanit = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks", "para_birimi": "USD"})
    assert yanit.status_code == 200
    assert 'data-tutar="1.586"' in yanit.text or "1.59" in yanit.text


def test_kalem_hesapla_alan_degisince_yeniden_fiyatlar(client):
    ekleme = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks", "para_birimi": "USD"})
    kalem_id = _kalem_id_cikar(ekleme.text)

    veri = {
        f"{kalem_id}.urun_tipi": "managed_disks",
        f"{kalem_id}.bolge": "eastus",
        f"{kalem_id}.kademe": "standardhdd",
        f"{kalem_id}.sku": "S4",
        f"{kalem_id}.adet": "3",
        f"{kalem_id}.islem_adet": "0",
        "para_birimi": "USD",
    }
    yanit = client.post(f"/tahmin/kalem/hesapla?kalem_id={kalem_id}", data=veri)
    assert yanit.status_code == 200
    assert 'data-tutar="4.608"' in yanit.text  # 3 x $1.536


def test_gecersiz_urun_tipi_reddedilir(client):
    yanit = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "olmayan_urun"})
    assert yanit.status_code == 400


def test_bos_tahmin_disa_aktarilamaz(client):
    yanit = client.post("/tahmin/disa-aktar", data={"para_birimi": "USD"})
    assert yanit.status_code == 400


def test_bos_tahmin_kaydedilemez(client):
    yanit = client.post("/tahmin/kaydet", data={"para_birimi": "USD", "hesaplama_adi": "Test"})
    assert yanit.status_code == 400


def test_ad_verilmeden_kaydedilemez(client):
    ekleme = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks", "para_birimi": "USD"})
    kalem_id = _kalem_id_cikar(ekleme.text)
    veri = {
        f"{kalem_id}.urun_tipi": "managed_disks", f"{kalem_id}.bolge": "eastus",
        f"{kalem_id}.kademe": "standardhdd", f"{kalem_id}.sku": "S4", f"{kalem_id}.adet": "1",
        "para_birimi": "USD", "hesaplama_adi": "",
    }
    yanit = client.post("/tahmin/kaydet", data=veri)
    assert yanit.status_code == 400


def test_disa_aktarim_xlsx_dosyasi_doner(client):
    ekleme = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks", "para_birimi": "USD"})
    kalem_id = _kalem_id_cikar(ekleme.text)
    veri = {
        f"{kalem_id}.urun_tipi": "managed_disks", f"{kalem_id}.bolge": "eastus",
        f"{kalem_id}.kademe": "standardhdd", f"{kalem_id}.sku": "S4", f"{kalem_id}.adet": "1",
        "para_birimi": "USD",
    }
    yanit = client.post("/tahmin/disa-aktar", data=veri)
    assert yanit.status_code == 200
    assert yanit.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in yanit.headers["content-disposition"]


def test_kaydet_ve_gecmis_akisi(client, veritabani):
    ekleme = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks", "para_birimi": "USD"})
    kalem_id = _kalem_id_cikar(ekleme.text)
    veri = {
        f"{kalem_id}.urun_tipi": "managed_disks", f"{kalem_id}.bolge": "eastus",
        f"{kalem_id}.kademe": "standardhdd", f"{kalem_id}.sku": "S4", f"{kalem_id}.adet": "1",
        "para_birimi": "USD", "hesaplama_adi": "Test Senaryosu",
    }
    kaydet_yaniti = client.post("/tahmin/kaydet", data=veri)
    assert kaydet_yaniti.status_code == 200
    assert "kaydedildi" in kaydet_yaniti.text

    gecmis_yaniti = client.get("/gecmis")
    assert "Test Senaryosu" in gecmis_yaniti.text

    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        kayit = oturum.exec(select(Hesaplama)).one()
        assert kayit.ad == "Test Senaryosu"
        assert round(kayit.toplam_aylik_maliyet, 3) == 1.536
        assert len(kayit.kalemler) == 1
        assert kayit.kalemler[0].yapilandirma["sku"] == "S4"


def test_gecmis_karsilastirma_2den_farkli_secim_reddedilir(client, veritabani):
    yanit = client.get("/gecmis/karsilastir?id=1")
    assert yanit.status_code == 400


def _kaydet(client, hesaplama_adi="Test Senaryosu"):
    ekleme = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks", "para_birimi": "USD"})
    kalem_id = _kalem_id_cikar(ekleme.text)
    veri = {
        f"{kalem_id}.urun_tipi": "managed_disks", f"{kalem_id}.bolge": "eastus",
        f"{kalem_id}.kademe": "standardhdd", f"{kalem_id}.sku": "S4", f"{kalem_id}.adet": "1",
        "para_birimi": "USD", "hesaplama_adi": hesaplama_adi,
    }
    return client.post("/tahmin/kaydet", data=veri)


def test_gecmis_detay_yillik_maliyet_gosterir(client, veritabani):
    _kaydet(client)
    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        kayit = oturum.exec(select(Hesaplama)).one()

    yanit = client.get(f"/gecmis/{kayit.id}")
    assert yanit.status_code == 200
    assert "Test Senaryosu" in yanit.text
    assert "S4" in yanit.text  # kalemin ozeti detayda gorunuyor


def test_gecmis_sadece_sahibi_gorur_admin_hepsini_gorur(client, veritabani):
    from app.main import app
    from app.yetkilendirme import aktif_kullanici

    # Zeynep (Calisanlar) bir tahmin kaydeder
    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "zeynep.kara", "ad_soyad": "Zeynep Kara", "unvan": "", "gruplar": ["Calisanlar"],
    }
    _kaydet(client, "Zeynep Tahmini")

    # Can (Adminler) gecmise bakinca Zeynep'inkini de gormeli
    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "can.aydin", "ad_soyad": "Can Aydin", "unvan": "", "gruplar": ["Adminler"],
    }
    can_gecmis = client.get("/gecmis")
    assert "Zeynep Tahmini" in can_gecmis.text

    # Baska bir calisan (Deniz) gecmise bakinca Zeynep'inkini GORMEMELI
    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "deniz.aksoy", "ad_soyad": "Deniz Aksoy", "unvan": "", "gruplar": ["Calisanlar"],
    }
    deniz_gecmis = client.get("/gecmis")
    assert "Zeynep Tahmini" not in deniz_gecmis.text

    # Deniz, Zeynep'in kaydinin detayina/silmesine de erisemez
    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        kayit = oturum.exec(select(Hesaplama).where(Hesaplama.ad == "Zeynep Tahmini")).one()
    detay_yaniti = client.get(f"/gecmis/{kayit.id}")
    assert detay_yaniti.status_code == 403
    sil_yaniti = client.post(f"/gecmis/{kayit.id}/sil")
    assert sil_yaniti.status_code == 403

    app.dependency_overrides.pop(aktif_kullanici, None)


def test_it_muduru_kendi_departmanini_gorur_diger_departmani_gormez(client, veritabani):
    from app.main import app
    from app.yetkilendirme import aktif_kullanici

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "ayse.it", "ad_soyad": "Ayse IT", "unvan": "", "gruplar": ["Calisanlar", "IT"],
    }
    _kaydet(client, "IT Calisan Tahmini")

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "mehmet.hr", "ad_soyad": "Mehmet HR", "unvan": "", "gruplar": ["Calisanlar", "HR"],
    }
    _kaydet(client, "HR Calisan Tahmini")

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "ali.mudur",
        "ad_soyad": "Ali Mudur",
        "unvan": "",
        "gruplar": ["Mudurler", "IT"],
    }
    mudur_gecmis = client.get("/gecmis")
    assert "IT Calisan Tahmini" in mudur_gecmis.text
    assert "HR Calisan Tahmini" not in mudur_gecmis.text

    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        hr_kayit = oturum.exec(select(Hesaplama).where(Hesaplama.ad == "HR Calisan Tahmini")).one()
    detay_yaniti = client.get(f"/gecmis/{hr_kayit.id}")
    assert detay_yaniti.status_code == 403

    app.dependency_overrides.pop(aktif_kullanici, None)


def test_yonetici_departman_grubu_yoksa_sadece_kendininkini_gorur(client, veritabani):
    from app.main import app
    from app.yetkilendirme import aktif_kullanici

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "zeynep.kara", "ad_soyad": "Zeynep Kara", "unvan": "", "gruplar": ["Calisanlar"],
    }
    _kaydet(client, "Zeynep Tahmini")

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "deniz.aksoy", "ad_soyad": "Deniz Aksoy", "unvan": "", "gruplar": ["Calisanlar"],
    }
    _kaydet(client, "Deniz Tahmini")

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "genel.mudur", "ad_soyad": "Genel Mudur", "unvan": "", "gruplar": ["Mudurler"],
    }
    mudur_gecmis = client.get("/gecmis")
    assert "Zeynep Tahmini" not in mudur_gecmis.text
    assert "Deniz Tahmini" not in mudur_gecmis.text

    app.dependency_overrides.pop(aktif_kullanici, None)


def test_gruplardan_departman_belirle_it_ik_ve_diger():
    assert gruplardan_departman_belirle(["Calisanlar", "IT"]) == ("it", "IT")
    assert gruplardan_departman_belirle(["HR.Calisanlar"]) == ("ik", "IK")
    assert gruplardan_departman_belirle(["Calisanlar"]) == ("diger", "Diger")


def test_gecmis_erisim_kapsami_admin_mudur_calisan():
    assert gecmis_erisim_kapsami({"gruplar": ["Adminler"]}) == "admin"
    assert gecmis_erisim_kapsami({"gruplar": ["Mudurler", "IT"]}) == "departman"
    assert gecmis_erisim_kapsami({"gruplar": ["Mudurler"]}) == "kendi"
    assert gecmis_erisim_kapsami({"gruplar": ["Calisanlar"]}) == "kendi"


def test_sahibi_kendi_tahminini_silebilir(client, veritabani):
    from app.main import app
    from app.yetkilendirme import aktif_kullanici

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "zeynep.kara", "ad_soyad": "Zeynep Kara", "unvan": "", "gruplar": ["Calisanlar"],
    }
    _kaydet(client, "Silinecek Tahmin")

    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        kayit = oturum.exec(select(Hesaplama).where(Hesaplama.ad == "Silinecek Tahmin")).one()

    yanit = client.post(f"/gecmis/{kayit.id}/sil", follow_redirects=False)
    assert yanit.status_code == 303

    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        kalan = oturum.exec(select(Hesaplama).where(Hesaplama.ad == "Silinecek Tahmin")).all()
    assert kalan == []

    app.dependency_overrides.pop(aktif_kullanici, None)


def test_dil_degistir_tahmini_kaybetmez(client):
    ekleme = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks", "para_birimi": "USD"})
    kalem_id = _kalem_id_cikar(ekleme.text)
    veri = {
        f"{kalem_id}.urun_tipi": "managed_disks", f"{kalem_id}.bolge": "eastus",
        f"{kalem_id}.kademe": "standardhdd", f"{kalem_id}.sku": "S4", f"{kalem_id}.adet": "1",
        "para_birimi": "USD", "dil": "en",
    }
    yanit = client.post("/tahmin/dil-degistir", data=veri)
    assert yanit.status_code == 200
    assert "Managed Disks" in yanit.text  # kalem, ingilizce olarak, KAYBOLMADAN geri geldi
    assert f'kalem-{kalem_id}' in yanit.text
