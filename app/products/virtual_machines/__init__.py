"""Sanal Makineler urun modulu (resmi Azure Pricing Calculator'in
'Virtual Machines' karti ile ayni alan/bagimlilik kumesini uygular, gomulu
Yonetilen Disk / Depolama islemleri / Bant genisligi bilesenleri dahil)."""

from __future__ import annotations

from typing import Any

from app.bolgeler import bolge_bul
from app.i18n import Dil, t
from app.products.base import DisaAktarimSatiri, FiyatSonucu
from app.products.virtual_machines import fiyatlama, secenekler
from app.products.virtual_machines.secenekler import SecenekSonucu


class VirtualMachinesUrunu:
    anahtar = "virtual_machines"
    sablon_adi = "urunler/_vm_form.html"

    def ad(self, dil: Dil) -> str:
        return t("urun_vm_ad", dil)

    def aciklama(self, dil: Dil) -> str:
        return t("urun_vm_aciklama", dil)

    def bos_yapilandirma(self) -> dict[str, Any]:
        return secenekler.bos_yapilandirma()

    async def secenekleri_getir(self, yapilandirma: dict[str, Any], dil: Dil) -> SecenekSonucu:
        return await secenekler.secenekleri_coz(yapilandirma, dil)

    async def fiyatla(self, yapilandirma: dict[str, Any], para_birimi: str) -> FiyatSonucu:
        return await fiyatlama.fiyatla(yapilandirma, para_birimi)

    def ozet(self, yapilandirma: dict[str, Any], dil: Dil) -> str:
        bolge = bolge_bul(yapilandirma.get("bolge", ""))
        bolge_adi = bolge.ad if bolge else yapilandirma.get("bolge", "")
        sku = yapilandirma.get("sku") or "?"
        adet = yapilandirma.get("adet", 1)
        yazilim_kodu = yapilandirma.get("yazilim_tipi", "")
        yazilim_liste = secenekler.yazilim_tipleri(yapilandirma.get("isletim_sistemi", "linux"))
        yazilim_adi = next((etiket[dil] for kod, etiket, _ in yazilim_liste if kod == yazilim_kodu), yazilim_kodu)
        parcalar = [f"{adet} x {sku}", yazilim_adi, bolge_adi]
        if yapilandirma.get("hibrit_fayda"):
            parcalar.append("AHB")
        return " - ".join(str(p) for p in parcalar)

    def disa_aktarim_satirlari(
        self, yapilandirma: dict[str, Any], fiyat: FiyatSonucu, dil: Dil
    ) -> list[DisaAktarimSatiri]:
        bolge = bolge_bul(yapilandirma.get("bolge", ""))
        bolge_adi = bolge.ad if bolge else yapilandirma.get("bolge", "")
        urun_adi = self.ad(dil)
        ozet = self.ozet(yapilandirma, dil)
        return [
            DisaAktarimSatiri(
                urun=urun_adi,
                yapilandirma_ozeti=f"{ozet} / {t(kalem.anahtar, dil)}",
                bolge=bolge_adi,
                miktar=kalem.miktar,
                birim=kalem.birim,
                birim_fiyat=kalem.birim_fiyat,
                ara_toplam=kalem.aylik_tutar,
            )
            for kalem in fiyat.kalemler
        ]
