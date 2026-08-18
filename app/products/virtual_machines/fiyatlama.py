"""Sanal Makine fiyatlama.

Tum fiyatlar Azure Retail Prices API'sinden CANLI cekilir; bu dosyada hicbir
sayisal fiyat sabiti yoktur. Temel model, resmi hesaplayicinin kendi
gosterdigi "Compute" + "OS" ayrimiyla canli API karsisinda dogrulanmistir:

  Compute = temel (Linux/Ubuntu, ek yazilimsiz) productName'in tuketim fiyati
  OS/Yazilim bileseni = (secilen isletim sistemi/yazilimin tum-dahil fiyati)
                         - (ayni SKU'nun Compute fiyati)

Windows D2s v3 orneginde: 0.188 $/s - 0.096 $/s = 0.092 $/s = resmi
hesaplayicinin gosterdigi "OS (Windows)" bileseniyle (67.16 $/ay) birebir
eslesir. Tasarruf plani (savingsPlan dizisi) VE rezervasyon kayitlari SADECE
temel (Linux) urun altinda bulunur -- yani bu indirimler yalnizca Compute
bilesenine uygulanir, OS/yazilim farki her zaman kullandikca-ode oranindan
hesaplanir (gercek Azure faturalama davranisiyla ayni: Compute tasarruf
planlari/rezervasyonlari Windows/SQL lisans ucretini kapsamaz).
"""

from __future__ import annotations

import re

from app.fiyat_api import kayitlari_getir, odata_metin_kacir
from app.products.base import FiyatBulunamadiHatasi, FiyatKalemi, FiyatSonucu
from app.products.managed_disks import fiyatlama as disk_fiyatlama
from app.products.virtual_machines.secenekler import (
    SAAT_CARPANLARI,
    ahb_uygun_mu,
    yazilim_tipi_arama_anahtar_kelimeleri,
)

_TEMEL_URUN_DESENI = re.compile(r"^Virtual Machines \S+ Series$")
_WINDOWS_OS_ONLY_DESENI = re.compile(r"^Virtual Machines \S+ Series Windows$")

_REZERVASYON_TERIM = {"reservation_1y": "1 Year", "reservation_3y": "3 Years"}
_REZERVASYON_AY = {"reservation_1y": 12, "reservation_3y": 36}
_TASARRUF_TERIM = {"savings_1y": "1 Year", "savings_3y": "3 Years"}


def _en_ucuz(kayitlar: list[dict]) -> dict | None:
    if not kayitlar:
        return None
    return min(kayitlar, key=lambda k: k.get("retailPrice", float("inf")))


def _kademeli_tutar(kayitlar: list[dict], miktar: float) -> float:
    """tierMinimumUnits'e gore kademeli (graduated/hacim bazli) fiyatlandirma
    uygular -- Azure'in Bant genisligi gibi bazi metrikleri gercekten bu
    sekilde faturalandirdigi dogrulanmistir (canli API)."""
    kademeler = sorted({k.get("tierMinimumUnits", 0.0): k["retailPrice"] for k in kayitlar}.items())
    if not kademeler or miktar <= 0:
        return 0.0
    toplam = 0.0
    for i, (esik, fiyat) in enumerate(kademeler):
        if miktar <= esik:
            break
        ust_sinir = kademeler[i + 1][0] if i + 1 < len(kademeler) else float("inf")
        dilim = min(miktar, ust_sinir) - esik
        toplam += dilim * fiyat
    return toplam


async def _sku_kayitlarini_al(bolge: str, sku: str, para_birimi: str) -> list[dict]:
    filtre = (
        f"serviceName eq 'Virtual Machines' and armRegionName eq '{odata_metin_kacir(bolge)}' "
        f"and armSkuName eq '{odata_metin_kacir(sku)}'"
    )
    return await kayitlari_getir(filtre, para_birimi)


def _temiz_mi(kayit: dict) -> bool:
    meter_adi = kayit.get("meterName", "")
    return "Spot" not in meter_adi and "Low Priority" not in meter_adi


def _temel_compute_kaydini_bul(kayitlar: list[dict]) -> dict | None:
    adaylar = [
        k
        for k in kayitlar
        if k.get("type") == "Consumption"
        and _temiz_mi(k)
        and _TEMEL_URUN_DESENI.match(k.get("productName", ""))
    ]
    return adaylar[0] if adaylar else None


def _yazilim_all_in_kaydini_bul(kayitlar: list[dict], isletim_sistemi: str, yazilim_tipi: str) -> dict | None:
    if isletim_sistemi == "windows" and yazilim_tipi == "os-only":
        adaylar = [
            k
            for k in kayitlar
            if k.get("type") == "Consumption" and _temiz_mi(k)
            and _WINDOWS_OS_ONLY_DESENI.match(k.get("productName", ""))
        ]
        return adaylar[0] if adaylar else None

    anahtar_kelimeler = yazilim_tipi_arama_anahtar_kelimeleri(yazilim_tipi)
    if not anahtar_kelimeler:
        return None
    adaylar = []
    for k in kayitlar:
        if k.get("type") != "Consumption" or not _temiz_mi(k):
            continue
        urun_adi_kucuk = k.get("productName", "").lower()
        if all(kelime.lower() in urun_adi_kucuk for kelime in anahtar_kelimeler):
            adaylar.append(k)
    return _en_ucuz(adaylar)


def _tasarruf_orani_bul(compute_kaydi: dict, terim: str) -> float | None:
    for girdi in compute_kaydi.get("savingsPlan", []) or []:
        if girdi.get("term") == terim:
            return girdi.get("retailPrice")
    return None


async def _rezervasyon_kaydini_bul(bolge: str, sku: str, terim: str, para_birimi: str) -> dict | None:
    kayitlar = await _sku_kayitlarini_al(bolge, sku, para_birimi)
    adaylar = [
        k
        for k in kayitlar
        if k.get("type") == "Reservation"
        and k.get("reservationTerm") == terim
        and _TEMEL_URUN_DESENI.match(k.get("productName", ""))
    ]
    return adaylar[0] if adaylar else None


async def _compute_ve_os_fiyatla(yapilandirma: dict, para_birimi: str) -> list[FiyatKalemi]:
    bolge = yapilandirma["bolge"]
    sku = yapilandirma.get("sku")
    if not sku:
        raise FiyatBulunamadiHatasi()

    adet = max(1, int(yapilandirma.get("adet", 1)))
    carpan = SAAT_CARPANLARI.get(yapilandirma.get("sure_birimi", "saat"), 1)
    toplam_saat = max(0.0, float(yapilandirma.get("sure_miktar", 730) or 0)) * carpan
    fiyatlandirma_modeli = yapilandirma.get("fiyatlandirma_modeli", "payg")
    isletim_sistemi = yapilandirma.get("isletim_sistemi", "linux")
    yazilim_tipi = yapilandirma.get("yazilim_tipi", "ubuntu")

    kayitlar = await _sku_kayitlarini_al(bolge, sku, para_birimi)
    if not kayitlar:
        raise FiyatBulunamadiHatasi()

    compute_kaydi = _temel_compute_kaydini_bul(kayitlar)
    if compute_kaydi is None:
        raise FiyatBulunamadiHatasi()
    compute_payg_fiyat = compute_kaydi["retailPrice"]

    kalemler: list[FiyatKalemi] = []

    if fiyatlandirma_modeli in _TASARRUF_TERIM:
        oran = _tasarruf_orani_bul(compute_kaydi, _TASARRUF_TERIM[fiyatlandirma_modeli])
        if oran is None:
            raise FiyatBulunamadiHatasi()
        compute_tutar = oran * toplam_saat * adet
        kalemler.append(FiyatKalemi("vm_bilesen_compute", toplam_saat * adet, "saat", oran, compute_tutar))
    elif fiyatlandirma_modeli in _REZERVASYON_TERIM:
        rez_kaydi = await _rezervasyon_kaydini_bul(bolge, sku, _REZERVASYON_TERIM[fiyatlandirma_modeli], para_birimi)
        if rez_kaydi is None:
            raise FiyatBulunamadiHatasi()
        ay_sayisi = _REZERVASYON_AY[fiyatlandirma_modeli]
        aylik_birim = rez_kaydi["retailPrice"] / ay_sayisi
        compute_tutar = aylik_birim * adet
        kalemler.append(FiyatKalemi("vm_bilesen_compute", adet, "vm", aylik_birim, compute_tutar))
    else:
        compute_tutar = compute_payg_fiyat * toplam_saat * adet
        kalemler.append(
            FiyatKalemi("vm_bilesen_compute", toplam_saat * adet, "saat", compute_payg_fiyat, compute_tutar)
        )

    if yazilim_tipi != "ubuntu":
        yazilim_kaydi = _yazilim_all_in_kaydini_bul(kayitlar, isletim_sistemi, yazilim_tipi)
        if yazilim_kaydi is None:
            raise FiyatBulunamadiHatasi()
        os_birim_farki = max(0.0, yazilim_kaydi["retailPrice"] - compute_payg_fiyat)

        if yapilandirma.get("hibrit_fayda") and ahb_uygun_mu(yazilim_tipi):
            os_tutar = 0.0
            os_birim_farki = 0.0
        else:
            os_tutar = os_birim_farki * toplam_saat * adet

        kalemler.append(
            FiyatKalemi("vm_bilesen_os", toplam_saat * adet, "saat", os_birim_farki, os_tutar)
        )

    return kalemler


async def _bant_genisligi_fiyatla(bant: dict, para_birimi: str) -> list[FiyatKalemi]:
    cikis_gb = max(0.0, float(bant.get("cikis_gb", 0) or 0))
    if cikis_gb <= 0:
        return []

    kaynak = bant.get("kaynak_bolge")
    if not kaynak:
        return []

    filtre = f"serviceName eq 'Bandwidth' and armRegionName eq '{odata_metin_kacir(kaynak)}'"
    kayitlar = await kayitlari_getir(filtre, para_birimi)

    if bant.get("veri_transfer_tipi") == "internetegress":
        eslesen = [
            k
            for k in kayitlar
            if k.get("productName") == "Bandwidth - Routing Preference: Internet"
            and k.get("meterName") == "Standard Data Transfer Out"
            and k.get("type") == "Consumption"
        ]
    else:
        eslesen = [
            k
            for k in kayitlar
            if k.get("meterName") == "Standard Inter-Region Data Transfer"
            and k.get("type") == "Consumption"
        ]

    if not eslesen:
        raise FiyatBulunamadiHatasi()

    tutar = _kademeli_tutar(eslesen, cikis_gb)
    birim_fiyat = tutar / cikis_gb if cikis_gb else 0.0
    return [FiyatKalemi("vm_bilesen_bant_genisligi", cikis_gb, "GB", birim_fiyat, tutar)]


async def fiyatla(yapilandirma: dict, para_birimi: str) -> FiyatSonucu:
    kalemler = list(await _compute_ve_os_fiyatla(yapilandirma, para_birimi))

    disk_yapilandirma = yapilandirma.get("disk") or {}
    if int(disk_yapilandirma.get("adet", 0) or 0) > 0:
        disk_sonucu = await disk_fiyatlama.fiyatla(disk_yapilandirma, para_birimi)
        kalemler.extend(disk_sonucu.kalemler)

    bant = yapilandirma.get("bant_genisligi") or {}
    kalemler.extend(await _bant_genisligi_fiyatla(bant, para_birimi))

    toplam = sum(k.aylik_tutar for k in kalemler)
    return FiyatSonucu(aylik_toplam=toplam, para_birimi=para_birimi, kalemler=kalemler)
