"""Yonetilen Disk fiyatlama.

Tum fiyatlar Azure Retail Prices API'sinden CANLI cekilir; bu dosyada hicbir
sayisal fiyat sabiti yoktur. Meter/skuName eslesme kaliplari, canli API
karsisinda `curl` ile dogrulanmistir (bkz. proje plani):

- Sabit SKU'lu kademeler (Standard HDD/SSD, Premium SSD): disk fiyati
  `meterName == '{SKU} {Redundancy} Disk'`, unitOfMeasure '1/Month'.
- Islemler (sadece HDD/SSD): `meterName == '{SKU} {Redundancy} Disk Operations'`.
- Anlik goruntu: `skuName == 'Snapshots {Redundancy}'`, '1 GB/Month'.
- Gizli sifreleme: `meterName == 'Confidential Compute Encryption {Redundancy}
  Provisioned Capacity'`, '1 GiB/Hour'.
- Premium SSD v2 / Ultra Disk: uc ayri "provisioned" olcu birimi (Capacity
  GiB/saat, IOPS/saat, Throughput MBps/saat). Premium SSD v2'de ilk 3.000
  IOPS ve 125 MB/s ucretsizdir (resmi hesaplayicida dogrulanmistir); Ultra
  Disk'te ucretsiz kota YOKTUR, talep edilen tum IOPS/throughput faturalanir
  (resmi hesaplayicinin ornek hesaplamasiyla dogrulanmistir).
"""

from __future__ import annotations

from app.fiyat_api import kayitlari_getir, odata_metin_kacir
from app.products.base import FiyatBulunamadiHatasi, FiyatKalemi, FiyatSonucu
from app.products.managed_disks.secenekler import (
    GIZLI_SIFRELEME_DESTEKLEYEN_KADEMELER,
    ISLEM_DESTEKLEYEN_KADEMELER,
    REZERVASYON_DESTEKLEYEN_KADEMELER,
    SABIT_SKU_TABLOLARI,
    SAAT_CARPANLARI,
    SNAPSHOT_DESTEKLEYEN_KADEMELER,
)

_URUN_ADLARI = {
    "standardhdd": "Standard HDD Managed Disks",
    "standardssd": "Standard SSD Managed Disks",
    "premiumssd": "Premium SSD Managed Disks",
    "premiumssdv2": "Azure Premium SSD v2",
    "ultrassd": "Ultra Disks",
}

_PREMIUM_V2_UCRETSIZ_IOPS = 3000
_PREMIUM_V2_UCRETSIZ_THROUGHPUT = 125


def _en_iyi_kaydi_sec(kayitlar: list[dict]) -> dict | None:
    adaylar = [
        k
        for k in kayitlar
        if k.get("retailPrice", 0) > 0
        and "shared" not in k.get("productName", "").lower()
        and "shared" not in k.get("meterName", "").lower()
    ]
    if not adaylar:
        return None
    return max(adaylar, key=lambda k: k.get("effectiveStartDate", ""))


async def _urun_kayitlarini_al(bolge: str, kademe: str, para_birimi: str) -> list[dict]:
    urun_adi = _URUN_ADLARI[kademe]
    filtre = (
        f"serviceName eq 'Storage' and armRegionName eq '{odata_metin_kacir(bolge)}' "
        f"and productName eq '{odata_metin_kacir(urun_adi)}'"
    )
    return await kayitlari_getir(filtre, para_birimi)


def _meter_bul(
    kayitlar: list[dict], meter_adi: str, unit: str | None = None, tip: str = "Consumption"
) -> dict | None:
    adaylar = [
        k
        for k in kayitlar
        if k.get("meterName") == meter_adi
        and k.get("type") == tip
        and (unit is None or k.get("unitOfMeasure") == unit)
    ]
    return _en_iyi_kaydi_sec(adaylar)


def _sku_meter_bul(kayitlar, sku, yedeklilik, ek, unit, tip="Consumption") -> dict | None:
    return _meter_bul(kayitlar, f"{sku} {yedeklilik} {ek}".strip(), unit, tip)


async def _fiyatla_sabit_sku(
    yapilandirma: dict, kayitlar: list[dict], para_birimi: str
) -> FiyatSonucu:
    kademe = yapilandirma["kademe"]
    sku = yapilandirma["sku"]
    yedeklilik = yapilandirma.get("yedeklilik", "LRS")
    adet = max(1, int(yapilandirma.get("adet", 1)))
    gib = SABIT_SKU_TABLOLARI[kademe][sku]
    fiyatlandirma_modeli = yapilandirma.get("fiyatlandirma_modeli", "payg")

    kalemler: list[FiyatKalemi] = []

    if fiyatlandirma_modeli == "reservation_1y" and kademe in REZERVASYON_DESTEKLEYEN_KADEMELER:
        adaylar = [
            k
            for k in kayitlar
            if k.get("meterName") == f"{sku} {yedeklilik} Disk"
            and k.get("type") == "Reservation"
            and k.get("reservationTerm") == "1 Year"
        ]
        disk_kaydi = _en_iyi_kaydi_sec(adaylar)
        if disk_kaydi is None:
            raise FiyatBulunamadiHatasi()
        birim_fiyat = disk_kaydi["retailPrice"] / 12  # API: rezervasyon toplam donem fiyatini verir
    else:
        disk_kaydi = _sku_meter_bul(kayitlar, sku, yedeklilik, "Disk", "1/Month")
        if disk_kaydi is None:
            raise FiyatBulunamadiHatasi()
        birim_fiyat = disk_kaydi["retailPrice"]

    disk_tutar = birim_fiyat * adet
    kalemler.append(
        FiyatKalemi("disk_bilesen_depolama", adet, "disk", birim_fiyat, disk_tutar)
    )

    if kademe in ISLEM_DESTEKLEYEN_KADEMELER:
        islem_kaydi = _sku_meter_bul(kayitlar, sku, yedeklilik, "Disk Operations", "10K")
        islem_adet = max(0.0, float(yapilandirma.get("islem_adet", 0) or 0))
        if islem_kaydi and islem_adet > 0:
            islem_tutar = islem_kaydi["retailPrice"] * islem_adet
            kalemler.append(
                FiyatKalemi(
                    "disk_bilesen_islemler", islem_adet, "10K islem", islem_kaydi["retailPrice"], islem_tutar
                )
            )

    if yapilandirma.get("anlik_goruntu") and kademe in SNAPSHOT_DESTEKLEYEN_KADEMELER:
        adaylar = [
            k
            for k in kayitlar
            if k.get("skuName") == f"Snapshots {yedeklilik}"
            and k.get("unitOfMeasure") == "1 GB/Month"
            and k.get("type") == "Consumption"
        ]
        snapshot_kaydi = _en_iyi_kaydi_sec(adaylar)
        if snapshot_kaydi:
            miktar = gib * adet
            tutar = snapshot_kaydi["retailPrice"] * miktar
            kalemler.append(
                FiyatKalemi("disk_bilesen_anlik_goruntu", miktar, "GB", snapshot_kaydi["retailPrice"], tutar)
            )

    if yapilandirma.get("gizli_sifreleme") and kademe in GIZLI_SIFRELEME_DESTEKLEYEN_KADEMELER:
        gizli_kaydi = _meter_bul(
            kayitlar, f"Confidential Compute Encryption {yedeklilik} Provisioned Capacity", "1 GiB/Hour"
        )
        if gizli_kaydi:
            miktar = gib * adet
            tutar = gizli_kaydi["retailPrice"] * miktar * 730
            kalemler.append(
                FiyatKalemi(
                    "disk_bilesen_gizli_sifreleme", miktar, "GiB", gizli_kaydi["retailPrice"], tutar
                )
            )

    toplam = sum(k.aylik_tutar for k in kalemler)
    return FiyatSonucu(aylik_toplam=toplam, para_birimi=para_birimi, kalemler=kalemler)


async def _fiyatla_provisioned(
    yapilandirma: dict, kayitlar: list[dict], para_birimi: str, meter_onek: str, ucretsiz_iops: float, ucretsiz_throughput: float
) -> FiyatSonucu:
    gib = max(1.0, float(yapilandirma.get("disk_boyutu_gib", 1) or 1))
    adet = max(1, int(yapilandirma.get("adet", 1)))
    carpan = SAAT_CARPANLARI.get(yapilandirma.get("sure_birimi", "saat"), 1)
    saat = max(0.0, float(yapilandirma.get("sure_miktar", 730) or 0)) * carpan

    kapasite_kaydi = _meter_bul(kayitlar, f"{meter_onek} Provisioned Capacity", "1 GiB/Hour")
    iops_kaydi = _meter_bul(kayitlar, f"{meter_onek} Provisioned IOPS", "1/Hour")
    throughput_kaydi = _meter_bul(kayitlar, f"{meter_onek} Provisioned Throughput (MBps)", "1/Hour")
    if not (kapasite_kaydi and iops_kaydi and throughput_kaydi):
        raise FiyatBulunamadiHatasi()

    kalemler: list[FiyatKalemi] = []

    kapasite_tutar = kapasite_kaydi["retailPrice"] * gib * saat * adet
    kalemler.append(
        FiyatKalemi("disk_bilesen_depolama", gib * adet, "GiB", kapasite_kaydi["retailPrice"], kapasite_tutar)
    )

    istenen_iops = max(0.0, float(yapilandirma.get("iops", 0) or 0))
    faturalanan_iops = max(0.0, istenen_iops - ucretsiz_iops)
    if faturalanan_iops > 0:
        iops_tutar = iops_kaydi["retailPrice"] * faturalanan_iops * saat * adet
        kalemler.append(
            FiyatKalemi("disk_bilesen_iops", faturalanan_iops, "IOPS", iops_kaydi["retailPrice"], iops_tutar)
        )

    istenen_throughput = max(0.0, float(yapilandirma.get("throughput_mbps", 0) or 0))
    faturalanan_throughput = max(0.0, istenen_throughput - ucretsiz_throughput)
    if faturalanan_throughput > 0:
        throughput_tutar = throughput_kaydi["retailPrice"] * faturalanan_throughput * saat * adet
        kalemler.append(
            FiyatKalemi(
                "disk_bilesen_throughput", faturalanan_throughput, "MB/s", throughput_kaydi["retailPrice"], throughput_tutar
            )
        )

    toplam = sum(k.aylik_tutar for k in kalemler)
    return FiyatSonucu(aylik_toplam=toplam, para_birimi=para_birimi, kalemler=kalemler)


async def fiyatla(yapilandirma: dict, para_birimi: str) -> FiyatSonucu:
    bolge = yapilandirma.get("bolge")
    kademe = yapilandirma.get("kademe", "standardhdd")
    if not bolge:
        raise FiyatBulunamadiHatasi()

    kayitlar = await _urun_kayitlarini_al(bolge, kademe, para_birimi)
    if not kayitlar:
        raise FiyatBulunamadiHatasi()

    if kademe in SABIT_SKU_TABLOLARI:
        return await _fiyatla_sabit_sku(yapilandirma, kayitlar, para_birimi)
    if kademe == "premiumssdv2":
        return await _fiyatla_provisioned(
            yapilandirma, kayitlar, para_birimi, "Premium LRS", _PREMIUM_V2_UCRETSIZ_IOPS, _PREMIUM_V2_UCRETSIZ_THROUGHPUT
        )
    if kademe == "ultrassd":
        return await _fiyatla_provisioned(yapilandirma, kayitlar, para_birimi, "Ultra LRS", 0, 0)

    raise FiyatBulunamadiHatasi()
