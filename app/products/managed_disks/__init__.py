"""Yonetilen Diskler urun modulu (resmi Azure Pricing Calculator'in
'Managed Disks' karti ile ayni alan/bagimlilik kumesini uygular)."""

from __future__ import annotations

from typing import Any

from app.bolgeler import bolge_bul
from app.i18n import Dil, t
from app.products.base import DisaAktarimSatiri, FiyatSonucu
from app.products.managed_disks import fiyatlama, secenekler
from app.products.managed_disks.secenekler import SecenekSonucu


class ManagedDisksUrunu:
    anahtar = "managed_disks"
    sablon_adi = "urunler/_disk_form.html"

    def ad(self, dil: Dil) -> str:
        return t("urun_disk_ad", dil)

    def aciklama(self, dil: Dil) -> str:
        return t("urun_disk_aciklama", dil)

    def bos_yapilandirma(self) -> dict[str, Any]:
        return secenekler.bos_yapilandirma()

    async def secenekleri_getir(self, yapilandirma: dict[str, Any], dil: Dil) -> SecenekSonucu:
        return secenekler.secenekleri_coz(yapilandirma, dil)

    async def fiyatla(self, yapilandirma: dict[str, Any], para_birimi: str) -> FiyatSonucu:
        return await fiyatlama.fiyatla(yapilandirma, para_birimi)

    def ozet(self, yapilandirma: dict[str, Any], dil: Dil) -> str:
        kademe_adi = secenekler.kademe_adi(yapilandirma.get("kademe", ""), dil)
        bolge = bolge_bul(yapilandirma.get("bolge", ""))
        bolge_adi = bolge.ad if bolge else yapilandirma.get("bolge", "")
        sku = yapilandirma.get("sku")
        adet = yapilandirma.get("adet", 1)
        parcalar = [kademe_adi]
        if sku:
            parcalar.append(sku)
        else:
            parcalar.append(f"{yapilandirma.get('disk_boyutu_gib')} GiB")
        parcalar.append(f"x{adet}")
        parcalar.append(bolge_adi)
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
