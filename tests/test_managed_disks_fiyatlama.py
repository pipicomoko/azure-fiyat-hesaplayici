"""Yonetilen Disk fiyatlama testleri.

Sabit veriler (fixture), Azure Retail Prices API'sine yapilan CANLI
sorgularla dogrulanmis gercek kayitlardir (bkz. proje plani/PR aciklamasi):
Standard HDD S4 = $1.536/ay, islemler $0.0005/10K, Ultra Disk ve Premium SSD
v2 birim fiyatlari. Beklenen toplamlar da bu canli dogrulamadan gelir.
"""

import asyncio

import pytest

from app.fiyat_api import onbellek_temizle
from app.products import managed_disks
from app.products.base import FiyatBulunamadiHatasi

_STANDARD_HDD_KAYITLARI = [
    {
        "meterName": "S4 LRS Disk",
        "skuName": "S4 LRS",
        "retailPrice": 1.536,
        "unitOfMeasure": "1/Month",
        "type": "Consumption",
        "productName": "Standard HDD Managed Disks",
        "effectiveStartDate": "2020-01-01",
    },
    {
        "meterName": "S4 LRS Disk Operations",
        "skuName": "S4 LRS",
        "retailPrice": 0.0005,
        "unitOfMeasure": "10K",
        "type": "Consumption",
        "productName": "Standard HDD Managed Disks",
        "effectiveStartDate": "2020-01-01",
    },
    {
        "meterName": "LRS Snapshots",
        "skuName": "Snapshots LRS",
        "retailPrice": 0.05,
        "unitOfMeasure": "1 GB/Month",
        "type": "Consumption",
        "productName": "Standard HDD Managed Disks",
        "effectiveStartDate": "2020-01-01",
    },
]

_ULTRA_KAYITLARI = [
    {
        "meterName": "Ultra LRS Provisioned Capacity",
        "skuName": "Ultra LRS",
        "retailPrice": 0.000164,
        "unitOfMeasure": "1 GiB/Hour",
        "type": "Consumption",
        "productName": "Ultra Disks",
        "effectiveStartDate": "2020-01-01",
    },
    {
        "meterName": "Ultra LRS Provisioned IOPS",
        "skuName": "Ultra LRS",
        "retailPrice": 0.000068,
        "unitOfMeasure": "1/Hour",
        "type": "Consumption",
        "productName": "Ultra Disks",
        "effectiveStartDate": "2020-01-01",
    },
    {
        "meterName": "Ultra LRS Provisioned Throughput (MBps)",
        "skuName": "Ultra LRS",
        "retailPrice": 0.000479,
        "unitOfMeasure": "1/Hour",
        "type": "Consumption",
        "productName": "Ultra Disks",
        "effectiveStartDate": "2020-01-01",
    },
]

_PREMIUM_V2_KAYITLARI = [
    {
        "meterName": "Premium LRS Provisioned Capacity",
        "skuName": "Premium LRS",
        "retailPrice": 0.00011,
        "unitOfMeasure": "1 GiB/Hour",
        "type": "Consumption",
        "productName": "Azure Premium SSD v2",
        "effectiveStartDate": "2020-01-01",
    },
    {
        "meterName": "Premium LRS Provisioned IOPS",
        "skuName": "Premium LRS",
        "retailPrice": 0.0,
        "unitOfMeasure": "1/Hour",
        "type": "Consumption",
        "productName": "Azure Premium SSD v2",
        "effectiveStartDate": "2019-01-01",
    },
    {
        "meterName": "Premium LRS Provisioned IOPS",
        "skuName": "Premium LRS",
        "retailPrice": 7e-06,
        "unitOfMeasure": "1/Hour",
        "type": "Consumption",
        "productName": "Azure Premium SSD v2",
        "effectiveStartDate": "2021-01-01",
    },
    {
        "meterName": "Premium LRS Provisioned Throughput (MBps)",
        "skuName": "Premium LRS",
        "retailPrice": 0.0,
        "unitOfMeasure": "1/Hour",
        "type": "Consumption",
        "productName": "Azure Premium SSD v2",
        "effectiveStartDate": "2019-01-01",
    },
    {
        "meterName": "Premium LRS Provisioned Throughput (MBps)",
        "skuName": "Premium LRS",
        "retailPrice": 5.5e-05,
        "unitOfMeasure": "1/Hour",
        "type": "Consumption",
        "productName": "Azure Premium SSD v2",
        "effectiveStartDate": "2021-01-01",
    },
]

_TUM_KAYITLAR = {
    "Standard HDD Managed Disks": _STANDARD_HDD_KAYITLARI,
    "Ultra Disks": _ULTRA_KAYITLARI,
    "Azure Premium SSD v2": _PREMIUM_V2_KAYITLARI,
}


async def _sahte_kayitlari_getir(filtre, para_birimi="USD", onbellek_kullan=True):
    for urun_adi, kayitlar in _TUM_KAYITLAR.items():
        if f"productName eq '{urun_adi}'" in filtre:
            return kayitlar
    return []


@pytest.fixture(autouse=True)
def _fiyat_api_sahte(monkeypatch):
    onbellek_temizle()
    monkeypatch.setattr(
        "app.products.managed_disks.fiyatlama.kayitlari_getir", _sahte_kayitlari_getir
    )
    yield
    onbellek_temizle()


def test_standard_hdd_s4_tek_disk_ve_islemler():
    cfg = {
        "bolge": "eastus",
        "kademe": "standardhdd",
        "sku": "S4",
        "yedeklilik": "LRS",
        "adet": 1,
        "islem_adet": 100,
        "anlik_goruntu": False,
        "gizli_sifreleme": False,
        "fiyatlandirma_modeli": "payg",
    }
    sonuc = asyncio.run(managed_disks.fiyatlama.fiyatla(cfg, "USD"))
    assert round(sonuc.aylik_toplam, 3) == 1.586


def test_standard_hdd_anlik_goruntu_gib_ile_carpar():
    cfg = {
        "bolge": "eastus",
        "kademe": "standardhdd",
        "sku": "S4",
        "yedeklilik": "LRS",
        "adet": 1,
        "islem_adet": 0,
        "anlik_goruntu": True,
        "gizli_sifreleme": False,
        "fiyatlandirma_modeli": "payg",
    }
    sonuc = asyncio.run(managed_disks.fiyatlama.fiyatla(cfg, "USD"))
    # S4 = 32 GiB * $0.05/GB = $1.60 anlik goruntu + $1.536 disk
    assert round(sonuc.aylik_toplam, 3) == round(1.536 + 32 * 0.05, 3)


def test_ultra_disk_ucretsiz_kota_yok_tum_talep_faturalanir():
    cfg = {
        "bolge": "eastus",
        "kademe": "ultrassd",
        "disk_boyutu_gib": 4,
        "iops": 100,
        "throughput_mbps": 1,
        "sure_birimi": "saat",
        "sure_miktar": 730,
        "adet": 1,
    }
    sonuc = asyncio.run(managed_disks.fiyatlama.fiyatla(cfg, "USD"))
    # Resmi hesaplayicida dogrulanan deger: $5.79/ay (0.48 + 4.96 + 0.35)
    assert round(sonuc.aylik_toplam, 2) == 5.79


def test_premium_ssd_v2_serbest_kota_ucretsiz():
    cfg = {
        "bolge": "eastus",
        "kademe": "premiumssdv2",
        "disk_boyutu_gib": 1,
        "iops": 3000,
        "throughput_mbps": 125,
        "sure_birimi": "saat",
        "sure_miktar": 730,
        "adet": 1,
    }
    sonuc = asyncio.run(managed_disks.fiyatlama.fiyatla(cfg, "USD"))
    # Resmi hesaplayicida dogrulanan deger: $0.08/ay (sadece kapasite, IOPS/throughput ucretsiz kota icinde)
    assert round(sonuc.aylik_toplam, 2) == 0.08
    assert len(sonuc.kalemler) == 1


def test_premium_ssd_v2_ucretsiz_kota_asimi_faturalanir():
    cfg = {
        "bolge": "eastus",
        "kademe": "premiumssdv2",
        "disk_boyutu_gib": 1,
        "iops": 4000,
        "throughput_mbps": 125,
        "sure_birimi": "saat",
        "sure_miktar": 730,
        "adet": 1,
    }
    sonuc = asyncio.run(managed_disks.fiyatlama.fiyatla(cfg, "USD"))
    iops_kalemi = next(k for k in sonuc.kalemler if k.anahtar == "disk_bilesen_iops")
    assert iops_kalemi.miktar == 1000  # 4000 - 3000 ucretsiz
    assert round(iops_kalemi.aylik_tutar, 4) == round(1000 * 7e-06 * 730, 4)


def test_eslesen_kayit_yoksa_hata_firlatir():
    # premiumssd icin sahte veri tanimlanmadi -> API'de kayit yok senaryosu
    cfg = {"bolge": "eastus", "kademe": "premiumssd", "sku": "P1", "adet": 1}
    with pytest.raises(FiyatBulunamadiHatasi):
        asyncio.run(managed_disks.fiyatlama.fiyatla(cfg, "USD"))
