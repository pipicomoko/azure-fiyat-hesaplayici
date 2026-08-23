"""Sanal Makine fiyatlama testleri.

Sabit veriler (fixture), Azure Retail Prices API'sine yapilan CANLI
sorgularla dogrulanmis gercek D2s v5 (East US) kayitlaridir: Linux/Compute
$0.096/saat, Windows tum-dahil $0.188/saat (-> OS farki $0.092/saat), 1
yillik rezervasyon $519 (toplam donem), tasarruf plani $0.0658368/saat.
"""

import asyncio

import pytest

from app.fiyat_api import onbellek_temizle
from app.products.base import FiyatBulunamadiHatasi
from app.products.virtual_machines import fiyatlama, secenekler

_D2SV5_KAYITLARI = [
    {
        "armSkuName": "Standard_D2s_v5", "productName": "Virtual Machines Dsv5 Series",
        "meterName": "D2s v5", "retailPrice": 0.096, "type": "Consumption",
        "savingsPlan": [{"term": "1 Year", "retailPrice": 0.0658368}, {"term": "3 Years", "retailPrice": 0.0441792}],
    },
    {
        "armSkuName": "Standard_D2s_v5", "productName": "Virtual Machines Dsv5 Series Windows",
        "meterName": "D2s v5", "retailPrice": 0.188, "type": "Consumption",
    },
    {
        "armSkuName": "Standard_D2s_v5", "productName": "Virtual Machines Dsv5 Series",
        "meterName": "D2s v5 Spot", "retailPrice": 0.02, "type": "Consumption",
    },
    {
        "armSkuName": "Standard_D2s_v5", "productName": "Virtual Machines Dsv5 Series",
        "meterName": "D2s v5", "retailPrice": 519.0, "type": "Reservation", "reservationTerm": "1 Year",
    },
    {
        "armSkuName": "Standard_D2s_v5", "productName": "Virtual Machines Dsv5 Series",
        "meterName": "D2s v5", "retailPrice": 997.0, "type": "Reservation", "reservationTerm": "3 Years",
    },
]


async def _sahte_kayitlari_getir(filtre, para_birimi="USD", onbellek_kullan=True):
    if "armSkuName eq 'Standard_D2s_v5'" in filtre:
        return _D2SV5_KAYITLARI
    return []


@pytest.fixture(autouse=True)
def _fiyat_api_sahte(monkeypatch):
    onbellek_temizle()
    monkeypatch.setattr("app.products.virtual_machines.fiyatlama.kayitlari_getir", _sahte_kayitlari_getir)
    yield
    onbellek_temizle()


def _taban_yapilandirma(**gecersiz_kilma):
    cfg = secenekler.bos_yapilandirma()
    cfg["bolge"] = "eastus"
    cfg["sku"] = "Standard_D2s_v5"
    cfg["disk"]["adet"] = 0
    cfg["bant_genisligi"]["cikis_gb"] = 0
    cfg.update(gecersiz_kilma)
    return cfg


def test_linux_ubuntu_payg_sadece_compute():
    cfg = _taban_yapilandirma(isletim_sistemi="linux", yazilim_tipi="ubuntu")
    sonuc = asyncio.run(fiyatlama.fiyatla(cfg, "USD"))
    assert round(sonuc.aylik_toplam, 2) == 70.08
    assert len(sonuc.kalemler) == 1


def test_windows_os_only_compute_artı_os_farki():
    cfg = _taban_yapilandirma(isletim_sistemi="windows", yazilim_tipi="os-only")
    sonuc = asyncio.run(fiyatlama.fiyatla(cfg, "USD"))
    # Resmi hesaplayicida dogrulanan deger: Compute $70.08 + OS $67.16 = $137.24
    assert round(sonuc.aylik_toplam, 2) == 137.24
    compute = next(k for k in sonuc.kalemler if k.anahtar == "vm_bilesen_compute")
    os_kalemi = next(k for k in sonuc.kalemler if k.anahtar == "vm_bilesen_os")
    assert round(compute.aylik_tutar, 2) == 70.08
    assert round(os_kalemi.aylik_tutar, 2) == 67.16


def test_windows_hibrit_fayda_os_bileseni_sifirlar():
    cfg = _taban_yapilandirma(isletim_sistemi="windows", yazilim_tipi="os-only", hibrit_fayda=True)
    sonuc = asyncio.run(fiyatlama.fiyatla(cfg, "USD"))
    os_kalemi = next(k for k in sonuc.kalemler if k.anahtar == "vm_bilesen_os")
    assert os_kalemi.aylik_tutar == 0.0
    assert round(sonuc.aylik_toplam, 2) == 70.08


def test_rezervasyon_1_yil_toplam_donem_fiyatindan_aylik_hesaplanir():
    cfg = _taban_yapilandirma(fiyatlandirma_modeli="reservation_1y")
    sonuc = asyncio.run(fiyatlama.fiyatla(cfg, "USD"))
    assert round(sonuc.aylik_toplam, 2) == round(519.0 / 12, 2)


def test_tasarruf_plani_1_yil_saatlik_oran_kullanir():
    cfg = _taban_yapilandirma(fiyatlandirma_modeli="savings_1y")
    sonuc = asyncio.run(fiyatlama.fiyatla(cfg, "USD"))
    assert round(sonuc.aylik_toplam, 2) == round(0.0658368 * 730, 2)


def test_windows_sql_standard_compute_os_ve_lisans(monkeypatch):
    """SQL lisansi Virtual Machines Licenses API'den gelir (SKU all-in degil)."""
    async def _sahte(filtre, para_birimi="USD", onbellek_kullan=True):
        if "Virtual Machines Licenses" in filtre and "SQL Server Standard" in filtre:
            return [
                {
                    "productName": "SQL Server Standard",
                    "meterName": "1-4 vCPU VM License",
                    "retailPrice": 0.4,
                    "type": "Consumption",
                    "unitOfMeasure": "1 Hour",
                },
                {
                    "productName": "SQL Server Standard",
                    "meterName": "1-4 vCPU VM License",
                    "retailPrice": 0.0,
                    "type": "Consumption",
                    "unitOfMeasure": "1 Hour",
                },
            ]
        if "armSkuName eq 'Standard_D2s_v5'" in filtre:
            return _D2SV5_KAYITLARI
        return []

    monkeypatch.setattr("app.products.virtual_machines.fiyatlama.kayitlari_getir", _sahte)
    monkeypatch.setattr("app.products.virtual_machines.lisanslar.kayitlari_getir", _sahte)

    cfg = _taban_yapilandirma(
        isletim_sistemi="windows",
        yazilim_tipi="sql-standard",
        vcpu=2,
    )
    sonuc = asyncio.run(fiyatlama.fiyatla(cfg, "USD"))
    # Compute 0.096*730 + OS 0.092*730 + SQL 0.4*730
    assert round(sonuc.aylik_toplam, 2) == round((0.096 + 0.092 + 0.4) * 730, 2)
    anahtarlar = {k.anahtar for k in sonuc.kalemler}
    assert anahtarlar == {"vm_bilesen_compute", "vm_bilesen_os", "vm_bilesen_yazilim"}


def test_eski_sql_kodu_sql_standard_olarak_calisir(monkeypatch):
    async def _sahte(filtre, para_birimi="USD", onbellek_kullan=True):
        if "Virtual Machines Licenses" in filtre:
            return [
                {
                    "productName": "SQL Server Standard",
                    "meterName": "1-4 vCPU VM License",
                    "retailPrice": 0.4,
                    "type": "Consumption",
                    "unitOfMeasure": "1 Hour",
                }
            ]
        if "armSkuName eq 'Standard_D2s_v5'" in filtre:
            return _D2SV5_KAYITLARI
        return []

    monkeypatch.setattr("app.products.virtual_machines.fiyatlama.kayitlari_getir", _sahte)
    monkeypatch.setattr("app.products.virtual_machines.lisanslar.kayitlari_getir", _sahte)
    cfg = _taban_yapilandirma(isletim_sistemi="windows", yazilim_tipi="sql", vcpu=2)
    sonuc = asyncio.run(fiyatlama.fiyatla(cfg, "USD"))
    assert any(k.anahtar == "vm_bilesen_yazilim" for k in sonuc.kalemler)
    assert sonuc.aylik_toplam > 137.24


def test_sql_hibrit_fayda_lisansi_sifirlar(monkeypatch):
    async def _sahte(filtre, para_birimi="USD", onbellek_kullan=True):
        if "Virtual Machines Licenses" in filtre:
            return [
                {
                    "productName": "SQL Server Standard",
                    "meterName": "1-4 vCPU VM License",
                    "retailPrice": 0.4,
                    "type": "Consumption",
                    "unitOfMeasure": "1 Hour",
                }
            ]
        if "armSkuName eq 'Standard_D2s_v5'" in filtre:
            return _D2SV5_KAYITLARI
        return []

    monkeypatch.setattr("app.products.virtual_machines.fiyatlama.kayitlari_getir", _sahte)
    monkeypatch.setattr("app.products.virtual_machines.lisanslar.kayitlari_getir", _sahte)
    cfg = _taban_yapilandirma(
        isletim_sistemi="windows",
        yazilim_tipi="sql-standard",
        hibrit_fayda=True,
        vcpu=2,
    )
    sonuc = asyncio.run(fiyatlama.fiyatla(cfg, "USD"))
    yazilim = next(k for k in sonuc.kalemler if k.anahtar == "vm_bilesen_yazilim")
    assert yazilim.aylik_tutar == 0.0
    # Compute + Windows OS kalir
    assert round(sonuc.aylik_toplam, 2) == 137.24

def test_eslesen_sku_yoksa_hata_firlatir():
    cfg = _taban_yapilandirma(sku="Standard_Yok_v99")
    with pytest.raises(FiyatBulunamadiHatasi):
        asyncio.run(fiyatlama.fiyatla(cfg, "USD"))
