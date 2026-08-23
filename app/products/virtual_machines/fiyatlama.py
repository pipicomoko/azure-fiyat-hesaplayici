"""Sanal Makine fiyatlama.

Tum fiyatlar Azure Retail Prices API'sinden CANLI cekilir; bu dosyada hicbir
sayisal fiyat sabiti yoktur.

Bilesen modeli (resmi Azure Pricing Calculator ile ayni mantik):

  1) Compute = temel Linux Series tuketim fiyati (SKU + bolge)
  2) Windows OS = (Series Windows) - Compute  — Windows secildiginde
  3) Yazilim lisansi = Virtual Machines Licenses (SQL/BizTalk/RHEL/...)
     vCPU bazli saatlik lisans — all-in SKU kaydi olmayan yazilimlar icin

Tasarruf plani / rezervasyon yalnizca Compute'a uygulanir; OS ve lisans
her zaman kullandikca-ode oranindan hesaplanir.
"""

from __future__ import annotations

import re

from app.fiyat_api import kayitlari_getir, odata_metin_kacir
from app.products.base import FiyatBulunamadiHatasi, FiyatKalemi, FiyatSonucu
from app.products.managed_disks import fiyatlama as disk_fiyatlama
from app.products.virtual_machines.lisanslar import (
    lisans_saatlik_fiyat,
    lisansli_yazilim_mi,
    windows_os_gerekli_mi,
    yazilim_tipini_normallestir,
)
from app.products.virtual_machines.secenekler import (
    SAAT_CARPANLARI,
    _govdeyi_ayristir,
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


def _windows_os_kaydini_bul(kayitlar: list[dict]) -> dict | None:
    adaylar = [
        k
        for k in kayitlar
        if k.get("type") == "Consumption"
        and _temiz_mi(k)
        and _WINDOWS_OS_ONLY_DESENI.match(k.get("productName", ""))
    ]
    return adaylar[0] if adaylar else None


def _yazilim_all_in_kaydini_bul(kayitlar: list[dict], yazilim_tipi: str) -> dict | None:
    """Nadiren SKU'ya gomulu all-in urun (eski yol); lisans yoksa yedek."""
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


def _pozitif_sayi(deger, varsayilan: float = 0.0) -> float:
    try:
        return float(deger)
    except (TypeError, ValueError):
        return varsayilan


def _vcpu_coz(sku: str, yapilandirma: dict) -> int:
    ham = yapilandirma.get("vcpu")
    if ham is not None:
        try:
            n = int(float(ham))
            if n > 0:
                return n
        except (TypeError, ValueError):
            pass
    vcpu, _ = _govdeyi_ayristir(sku or "")
    return max(1, vcpu or 1)


async def _compute_ve_os_fiyatla(yapilandirma: dict, para_birimi: str) -> list[FiyatKalemi]:
    bolge = yapilandirma["bolge"]
    sku = yapilandirma.get("sku")
    if not sku:
        raise FiyatBulunamadiHatasi()

    adet = max(1, int(_pozitif_sayi(yapilandirma.get("adet", 1), 1)))
    carpan = SAAT_CARPANLARI.get(yapilandirma.get("sure_birimi", "saat"), 1)
    toplam_saat = max(0.0, _pozitif_sayi(yapilandirma.get("sure_miktar", 730), 730)) * carpan
    fiyatlandirma_modeli = yapilandirma.get("fiyatlandirma_modeli", "payg")
    isletim_sistemi = yapilandirma.get("isletim_sistemi", "linux")
    yazilim_tipi = yazilim_tipini_normallestir(yapilandirma.get("yazilim_tipi", "ubuntu"))
    hibrit = bool(yapilandirma.get("hibrit_fayda"))
    vcpu = _vcpu_coz(sku, yapilandirma)

    kayitlar = await _sku_kayitlarini_al(bolge, sku, para_birimi)
    if not kayitlar:
        raise FiyatBulunamadiHatasi()

    compute_kaydi = _temel_compute_kaydini_bul(kayitlar)
    if compute_kaydi is None:
        raise FiyatBulunamadiHatasi()
    compute_payg_fiyat = float(compute_kaydi["retailPrice"])

    kalemler: list[FiyatKalemi] = []

    # --- 1) Compute ---
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

    # --- 2) Windows OS farki ---
    if windows_os_gerekli_mi(isletim_sistemi, yazilim_tipi):
        windows_kaydi = _windows_os_kaydini_bul(kayitlar)
        if windows_kaydi is None:
            raise FiyatBulunamadiHatasi()
        os_birim = max(0.0, float(windows_kaydi["retailPrice"]) - compute_payg_fiyat)
        # AHB yalnizca "os-only" icin Windows lisansini sifirlar
        if hibrit and yazilim_tipi == "os-only" and ahb_uygun_mu(yazilim_tipi):
            os_birim = 0.0
        os_tutar = os_birim * toplam_saat * adet
        kalemler.append(
            FiyatKalemi("vm_bilesen_os", toplam_saat * adet, "saat", os_birim, os_tutar)
        )

    # --- 3) Yazilim lisansi (SQL/BizTalk/RHEL/...) veya all-in yedek ---
    if yazilim_tipi in ("ubuntu", "os-only"):
        return kalemler

    if lisansli_yazilim_mi(yazilim_tipi):
        lisans_birim = await lisans_saatlik_fiyat(yazilim_tipi, vcpu, para_birimi)
        if hibrit and ahb_uygun_mu(yazilim_tipi):
            lisans_birim = 0.0
        lisans_tutar = lisans_birim * toplam_saat * adet
        kalemler.append(
            FiyatKalemi("vm_bilesen_yazilim", toplam_saat * adet, "saat", lisans_birim, lisans_tutar)
        )
        return kalemler

    # Yedek: SKU'ya gomulu all-in urun (varsa)
    yazilim_kaydi = _yazilim_all_in_kaydini_bul(kayitlar, yazilim_tipi)
    if yazilim_kaydi is None:
        raise FiyatBulunamadiHatasi()
    fark = max(0.0, float(yazilim_kaydi["retailPrice"]) - compute_payg_fiyat)
    if hibrit and ahb_uygun_mu(yazilim_tipi):
        fark = 0.0
    # Windows OS zaten eklendiyse all-in farkini yazilim olarak ekleme (cift sayim);
    # all-in genelde OS+yazilim. Windows gerekli degilse fark OS/yazilim toplamidir.
    if windows_os_gerekli_mi(isletim_sistemi, yazilim_tipi):
        windows_kaydi = _windows_os_kaydini_bul(kayitlar)
        if windows_kaydi is not None:
            windows_fark = max(0.0, float(windows_kaydi["retailPrice"]) - compute_payg_fiyat)
            fark = max(0.0, fark - windows_fark)
    kalemler.append(
        FiyatKalemi("vm_bilesen_yazilim", toplam_saat * adet, "saat", fark, fark * toplam_saat * adet)
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
    if int(_pozitif_sayi(disk_yapilandirma.get("adet", 0), 0)) > 0:
        disk_sonucu = await disk_fiyatlama.fiyatla(disk_yapilandirma, para_birimi)
        kalemler.extend(disk_sonucu.kalemler)

    bant = yapilandirma.get("bant_genisligi") or {}
    kalemler.extend(await _bant_genisligi_fiyatla(bant, para_birimi))

    toplam = sum(k.aylik_tutar for k in kalemler)
    return FiyatSonucu(aylik_toplam=toplam, para_birimi=para_birimi, kalemler=kalemler)
