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


def _sayiya_cevir(deger: Any) -> float:
    """Form/JSON'dan gelen degeri sayiya cevirir; "0" gibi metinler 0 olur."""
    try:
        return float(deger)
    except (TypeError, ValueError):
        return 0.0


class VirtualMachinesUrunu:
    anahtar = "virtual_machines"
    sablon_adi = "urunler/_vm_form.html"
    # Azure urun adi dil bagimsiz (resmi calculator ile ayni)
    SABIT_AD = "Virtual Machines"

    def ad(self, dil: Dil) -> str:
        return self.SABIT_AD

    def aciklama(self, dil: Dil) -> str:
        return t("urun_vm_aciklama", dil)

    def bos_yapilandirma(self) -> dict[str, Any]:
        return secenekler.bos_yapilandirma()

    async def secenekleri_getir(
        self, yapilandirma: dict[str, Any], dil: Dil
    ) -> SecenekSonucu:
        return await secenekler.secenekleri_coz(yapilandirma, dil)

    async def fiyatla(
        self, yapilandirma: dict[str, Any], para_birimi: str
    ) -> FiyatSonucu:
        return await fiyatlama.fiyatla(yapilandirma, para_birimi)

    def ozet(self, yapilandirma: dict[str, Any], dil: Dil) -> str:
        bolge = bolge_bul(yapilandirma.get("bolge", ""))
        bolge_adi = bolge.ad if bolge else yapilandirma.get("bolge", "")
        sku = yapilandirma.get("sku") or "?"
        adet = yapilandirma.get("adet", 1)
        yazilim_kodu = yapilandirma.get("yazilim_tipi", "")
        yazilim_liste = secenekler.yazilim_tipleri(
            yapilandirma.get("isletim_sistemi", "linux")
        )
        yazilim_adi = next(
            (etiket[dil] for kod, etiket, _ in yazilim_liste if kod == yazilim_kodu),
            yazilim_kodu,
        )
        parcalar = [f"{adet} x {sku}", yazilim_adi, bolge_adi]
        if yapilandirma.get("hibrit_fayda"):
            parcalar.append("AHB")
        return " - ".join(str(p) for p in parcalar)

    def _azure_description(
        self, yapilandirma: dict[str, Any], fiyat: FiyatSonucu, dil: Dil
    ) -> str:
        """Azure orijinal sitesindeki Description formatını üretir.
        Örnek: '1 D4ads v5 (4 vCPUs, 16 GB RAM) x 730 Hours (Pay as you go), Linux, ...'
        """
        from app.products.virtual_machines.secenekler import (
            _sku_goruntu_adi,
            _govdeyi_ayristir,
            seri_kategorisi,
            tahmini_ram_gib,
            fiyatlandirma_modeli_adi,
            SAAT_CARPANLARI,
            _BILINEN_SKU_BOYUTLARI,
        )

        sku = yapilandirma.get("sku") or ""
        adet = max(1, int(_sayiya_cevir(yapilandirma.get("adet", 1)) or 1))
        sure_birimi = yapilandirma.get("sure_birimi", "ay")
        sure_miktar = _sayiya_cevir(yapilandirma.get("sure_miktar", 730)) or 730
        fm = fiyatlandirma_modeli_adi(
            yapilandirma.get("fiyatlandirma_modeli", "payg"), "en"
        )
        isletim = yapilandirma.get("isletim_sistemi", "linux").capitalize()

        goruntu = _sku_goruntu_adi(sku)
        if sku in _BILINEN_SKU_BOYUTLARI:
            vcpu, ram = _BILINEN_SKU_BOYUTLARI[sku]
        else:
            vcpu_raw, _ = _govdeyi_ayristir(sku)
            vcpu = vcpu_raw if (vcpu_raw is not None and vcpu_raw > 0) else None
            seri = sku.split("_")[1][:2] if "_" in sku else ""
            ram = tahmini_ram_gib(vcpu, seri_kategorisi(seri)) if vcpu else None

        vcpu_str = f"{vcpu} vCPUs" if vcpu else "?"
        ram_str = f"{ram:g} GB RAM" if ram else ""
        boyut_str = f"({vcpu_str}, {ram_str})" if ram_str else f"({vcpu_str})"

        sure_etiket_map = {"saat": "Hours", "gun": "Days", "ay": "Hours"}
        sure_birim_str = sure_etiket_map.get(sure_birimi, "Hours")
        carpan = SAAT_CARPANLARI.get(sure_birimi, 730)
        sure_toplam = sure_miktar * carpan if sure_birimi != "ay" else 730

        parcalar = [
            f"{adet} {goruntu} {boyut_str} x {int(sure_toplam)} {sure_birim_str} ({fm})"
        ]
        parcalar.append(isletim)

        # Disk bilgisi
        disk = yapilandirma.get("disk") or {}
        disk_adet = _sayiya_cevir(disk.get("adet"))
        if disk_adet:
            disk_adet = int(disk_adet)
            disk_sku = disk.get("sku") or ""
            disk_boyut = disk.get("disk_boyutu_gib") or ""
            disk_sure = int(_sayiya_cevir(disk.get("sure_miktar")) or 730)
            disk_bilgi = (
                f"{disk_adet} X {disk_boyut or disk_sku} GiB Disks, {disk_sure} Hours"
            )
            if disk.get("iops"):
                disk_bilgi += f", {disk['iops']} IOPS"
            if disk.get("throughput_mbps"):
                disk_bilgi += f", {disk['throughput_mbps']} MB/s Throughput"
            parcalar.append(disk_bilgi)

        # Bant genişliği
        bant = yapilandirma.get("bant_genisligi") or {}
        gb = _sayiya_cevir(bant.get("cikis_gb"))
        if gb:
            transfer_tip = bant.get("veri_transfer_tipi", "interregion")
            tip_str = (
                "Inter Region transfer type"
                if transfer_tip == "interregion"
                else "Internet Egress transfer type"
            )
            kaynak = bant.get("kaynak_bolge", "")
            hedef = bant.get("hedef_bolge", "")
            gb = f"{gb:g}"
            bolge_str = f"from {kaynak} to {hedef}" if hedef else f"from {kaynak}"
            parcalar.append(f"{tip_str}, {gb} GB outbound data transfer {bolge_str}")

        return "; ".join(parcalar)

    def disa_aktarim_satirlari(
        self, yapilandirma: dict[str, Any], fiyat: FiyatSonucu, dil: Dil
    ) -> list[DisaAktarimSatiri]:
        bolge = bolge_bul(yapilandirma.get("bolge", ""))
        bolge_adi = bolge.ad if bolge else yapilandirma.get("bolge", "")
        description = self._azure_description(yapilandirma, fiyat, dil)
        return [
            DisaAktarimSatiri(
                servis_kategori="Compute",
                urun=self.ad(dil),
                ozel_ad="",
                bolge=bolge_adi,
                yapilandirma_ozeti=description,
                miktar=fiyat.aylik_toplam,
                birim="month",
                birim_fiyat=fiyat.aylik_toplam,
                ara_toplam=round(fiyat.aylik_toplam, 2),
                on_odeme=0.0,
            )
        ]
