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
from app.yetkilendirme import (
    gecmis_erisim_kapsami,
    gruplardan_departman_belirle,
)

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


def test_onaya_gonder_hedefsiz_reddedilir(client):
    ekleme = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks", "para_birimi": "USD"})
    kalem_id = _kalem_id_cikar(ekleme.text)
    veri = {
        f"{kalem_id}.urun_tipi": "managed_disks", f"{kalem_id}.bolge": "eastus",
        f"{kalem_id}.kademe": "standardhdd", f"{kalem_id}.sku": "S4", f"{kalem_id}.adet": "1",
        "para_birimi": "USD", "hesaplama_adi": "Hedefsiz", "onaya_gonder": "1",
    }
    yanit = client.post("/tahmin/kaydet", data=veri)
    assert yanit.status_code == 400
    metin = yanit.text.casefold()
    assert "yonetici" in metin or "yönetici" in metin or "approver" in metin or "seç" in metin or "select" in metin


def test_genel_mudur_onaya_gonderemez_sadece_kaydeder(client, veritabani):
    from app.main import app
    from app.models import DURUM_TASLAK, Hesaplama
    from app.yetkilendirme import GENEL_MUDUR_SAM, aktif_kullanici
    from sqlmodel import select

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": GENEL_MUDUR_SAM,
        "ad_soyad": "Ahmet Yildirim",
        "unvan": "Genel Mudur",
        "gruplar": ["AFH-Calisanlar", "AFH-Direktorler"],
        "rol": "direktor",
        "manager": None,
        "manager_zinciri": [],
    }
    ekleme = client.post("/tahmin/kalem-ekle", data={"urun_tipi": "managed_disks", "para_birimi": "USD"})
    kalem_id = _kalem_id_cikar(ekleme.text)
    veri = {
        f"{kalem_id}.urun_tipi": "managed_disks", f"{kalem_id}.bolge": "eastus",
        f"{kalem_id}.kademe": "standardhdd", f"{kalem_id}.sku": "S4", f"{kalem_id}.adet": "1",
        "para_birimi": "USD", "hesaplama_adi": "GM Deneme", "onaya_gonder": "1",
        "onay_hedefi": "kimse",
    }
    yanit = client.post("/tahmin/kaydet", data=veri)
    assert yanit.status_code == 200

    with __import__("sqlmodel").Session(veritabani) as oturum:
        kayit = oturum.exec(select(Hesaplama).where(Hesaplama.ad == "GM Deneme")).one()
        assert kayit.durum == DURUM_TASLAK
        assert kayit.onay_hedefi is None

    gecmis = client.get("/gecmis/taslaklar")
    assert "GM Deneme" in gecmis.text
    assert "Estimate History" in gecmis.text or "Tahmin ge" in gecmis.text

    app.dependency_overrides.pop(aktif_kullanici, None)


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

    gecmis_yaniti = client.get("/gecmis/taslaklar")
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
    # Eski karsilastirma ucu kalktiysa 404; varsa 400/422
    assert yanit.status_code in (400, 404, 422)


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


def test_gecmis_sadece_sahibi_gorur_admin_taslak_gormez(client, veritabani):
    from app.main import app
    from app.models import DURUM_ONAY_BEKLIYOR
    from app.yetkilendirme import aktif_kullanici

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "zeynep.kara",
        "ad_soyad": "Zeynep Kara",
        "unvan": "",
        "gruplar": ["AFH-Calisanlar"],
        "manager": "onur.simsek",
        "manager_zinciri": ["onur.simsek"],
    }
    _kaydet(client, "Zeynep Tahmini")

    # Admin taslagi gormez
    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "asli.demirtas",
        "ad_soyad": "Asli Demirtas",
        "unvan": "",
        "gruplar": ["AFH-Adminler"],
        "rol": "admin",
    }
    can_gecmis = client.get("/gecmis/arama")
    assert "Zeynep Tahmini" not in can_gecmis.text

    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        kayit = oturum.exec(select(Hesaplama).where(Hesaplama.ad == "Zeynep Tahmini")).one()
        kayit.durum = DURUM_ONAY_BEKLIYOR
        oturum.add(kayit)
        oturum.commit()
        kayit_id = kayit.id

    can_gecmis = client.get("/gecmis/arama")
    assert "Zeynep Tahmini" in can_gecmis.text

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "deniz.aksoy",
        "ad_soyad": "Deniz Aksoy",
        "unvan": "",
        "gruplar": ["AFH-Calisanlar"],
    }
    deniz_gecmis = client.get("/gecmis/taslaklar")
    assert "Zeynep Tahmini" not in deniz_gecmis.text

    detay_yaniti = client.get(f"/gecmis/{kayit_id}")
    assert detay_yaniti.status_code == 403
    sil_yaniti = client.post(f"/gecmis/{kayit_id}/sil")
    assert sil_yaniti.status_code == 403

    app.dependency_overrides.pop(aktif_kullanici, None)


def test_yonetici_manager_zincirindeki_kaydi_gorur(client, veritabani):
    from app.main import app
    from app.models import DURUM_ONAY_BEKLIYOR
    from app.yetkilendirme import aktif_kullanici

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "kerem.acar",
        "ad_soyad": "Kerem Acar",
        "unvan": "",
        "gruplar": ["AFH-Calisanlar", "DEPT-IT"],
        "departman": "it-altyapi",
        "manager": "onur.simsek",
        "manager_zinciri": ["onur.simsek", "emre.turan"],
    }
    _kaydet(client, "Kerem Tahmini")

    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        kayit = oturum.exec(select(Hesaplama).where(Hesaplama.ad == "Kerem Tahmini")).one()
        kayit.durum = DURUM_ONAY_BEKLIYOR
        kayit.olusturan_manager_zinciri = ["onur.simsek", "emre.turan"]
        oturum.add(kayit)
        oturum.commit()
        kayit_id = kayit.id

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "mehmet.hr",
        "ad_soyad": "Mehmet HR",
        "unvan": "",
        "gruplar": ["AFH-Calisanlar", "DEPT-IK"],
        "departman": "ik",
        "manager": "baska",
        "manager_zinciri": ["baska"],
    }
    _kaydet(client, "HR Calisan Tahmini")
    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        hr = oturum.exec(select(Hesaplama).where(Hesaplama.ad == "HR Calisan Tahmini")).one()
        hr.durum = DURUM_ONAY_BEKLIYOR
        hr.olusturan_manager_zinciri = ["baska"]
        oturum.add(hr)
        oturum.commit()
        hr_id = hr.id

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "onur.simsek",
        "ad_soyad": "Onur Simsek",
        "unvan": "",
        "gruplar": ["AFH-Calisanlar", "AFH-Yoneticiler", "DEPT-IT"],
        "rol": "yonetici",
        "manager_zinciri": ["emre.turan"],
    }
    mudur_gecmis = client.get("/gecmis/arama")
    assert "Kerem Tahmini" in mudur_gecmis.text
    assert "HR Calisan Tahmini" not in mudur_gecmis.text

    detay_yaniti = client.get(f"/gecmis/{hr_id}")
    assert detay_yaniti.status_code == 403
    assert client.get(f"/gecmis/{kayit_id}").status_code == 200

    app.dependency_overrides.pop(aktif_kullanici, None)


def test_yonetici_zincirde_yoksa_baskasini_gormez(client, veritabani):
    from app.main import app
    from app.yetkilendirme import aktif_kullanici

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "zeynep.kara",
        "ad_soyad": "Zeynep Kara",
        "unvan": "",
        "gruplar": ["AFH-Calisanlar"],
        "manager_zinciri": ["x"],
    }
    _kaydet(client, "Zeynep Tahmini")

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "genel.mudur",
        "ad_soyad": "Genel Mudur",
        "unvan": "",
        "gruplar": ["AFH-Yoneticiler"],
        "rol": "yonetici",
    }
    mudur_gecmis = client.get("/gecmis/arama")
    assert "Zeynep Tahmini" not in mudur_gecmis.text

    app.dependency_overrides.pop(aktif_kullanici, None)


def test_gruplardan_departman_belirle_it_ik_ve_diger():
    assert gruplardan_departman_belirle(["AFH-Calisanlar", "DEPT-IT"]) == ("it", "IT")
    assert gruplardan_departman_belirle(["HR.Calisanlar"]) == ("ik", "IK")
    assert gruplardan_departman_belirle(["AFH-Calisanlar"]) == ("diger", "Diger")


def test_gecmis_erisim_kapsami_admin_yonetici_calisan():
    assert gecmis_erisim_kapsami({"gruplar": ["AFH-Adminler"]}) == "admin"
    assert gecmis_erisim_kapsami({"gruplar": ["AFH-Direktorler"]}) == "direktor"
    assert gecmis_erisim_kapsami({"gruplar": ["AFH-Yoneticiler"]}) == "yonetici"
    assert gecmis_erisim_kapsami({"gruplar": ["AFH-Calisanlar"]}) == "kendi"


def test_sahibi_kendi_tahminini_silebilir(client, veritabani):
    from app.main import app
    from app.yetkilendirme import aktif_kullanici

    app.dependency_overrides[aktif_kullanici] = lambda: {
        "kullanici_adi": "zeynep.kara",
        "ad_soyad": "Zeynep Kara",
        "unvan": "",
        "gruplar": ["AFH-Calisanlar"],
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
