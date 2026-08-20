"""Kaydedilmis hesaplama kayitlarindan urun modulu ciktilarini yeniden uretir.

Gecmis kayitlari veritabaninda kisa bir ozet (`HesaplamaKalemi.ozet`) ve fiyat
bilesenleri olarak tutulur. Hem Excel disa aktarimi hem de gecmis detay sayfasi
ise urun modullerinin Azure formatindaki ayrintili aciklamasini gosterir. Bu
modul, kayitli `yapilandirma` JSON'undan o aciklamayi yeniden uretir; boylece
iki yuzey de ayni metni gosterir.
"""

from __future__ import annotations

from app.i18n import Dil
from app.products import urun_al
from app.products.base import DisaAktarimSatiri, FiyatKalemi, FiyatSonucu

# Fiyat bilesenlerinin birimleri veritabaninda Turkce sabit olarak yazilidir
# (bkz. products/*/fiyatlama.py). Goruntulerken dile gore cevrilir.
_BIRIM_ETIKETLERI: dict[str, dict[str, str]] = {
    "saat": {"tr": "saat", "en": "Hours"},
    "gun": {"tr": "gun", "en": "Days"},
    "ay": {"tr": "ay", "en": "Months"},
    "disk": {"tr": "disk", "en": "Disks"},
    "10K islem": {"tr": "10K islem", "en": "10K operations"},
    "GB": {"tr": "GB", "en": "GB"},
    "GB/ay": {"tr": "GB/ay", "en": "GB/month"},
    "month": {"tr": "ay", "en": "month"},
}


def birim_etiketi(birim: str | None, dil: Dil = "en") -> str:
    """Fiyat bileseni birimini istenen dilde dondurur."""
    if not birim:
        return ""
    etiket = _BIRIM_ETIKETLERI.get(birim.strip())
    if etiket is None:
        return birim
    return etiket.get(dil, etiket["en"])


def fiyat_sonucu(kalem, para_birimi: str = "USD") -> FiyatSonucu:
    """Kayitli kalemden urun modullerinin bekledigi FiyatSonucu'yu uretir."""
    kalemler = [
        FiyatKalemi(
            anahtar=bilesen.get("anahtar", ""),
            miktar=float(bilesen.get("miktar", 0)),
            birim=bilesen.get("birim", ""),
            birim_fiyat=float(bilesen.get("birim_fiyat", 0)),
            aylik_tutar=float(bilesen.get("aylik_tutar", 0)),
        )
        for bilesen in (kalem.fiyat_kalemleri or [])
        if isinstance(bilesen, dict)
    ]
    return FiyatSonucu(
        aylik_toplam=float(kalem.aylik_maliyet or 0),
        para_birimi=para_birimi or "USD",
        kalemler=kalemler,
    )


def kalem_satirlari(
    kalem, para_birimi: str = "USD", dil: Dil = "en"
) -> list[DisaAktarimSatiri]:
    """Kayitli kalem icin urun modulunun disa aktarim satirlarini uretir.

    Urun modulu bulunamazsa kayitli ozete dayanan tek satirla geri duser.
    """
    urun = urun_al(kalem.urun_tipi or "")
    satirlar: list[DisaAktarimSatiri] = []
    if urun is not None:
        try:
            satirlar = urun.disa_aktarim_satirlari(
                kalem.yapilandirma or {}, fiyat_sonucu(kalem, para_birimi), dil
            )
        except Exception:
            satirlar = []
    if not satirlar:
        aylik = float(kalem.aylik_maliyet or 0)
        satirlar = [
            DisaAktarimSatiri(
                servis_kategori="Other",
                urun=kalem.urun_tipi or "",
                ozel_ad="",
                bolge=(kalem.yapilandirma or {}).get("bolge", ""),
                yapilandirma_ozeti=kalem.ozet or "",
                miktar=aylik,
                birim="month",
                birim_fiyat=aylik,
                ara_toplam=aylik,
                on_odeme=0.0,
            )
        ]
    indirim = getattr(kalem, "indirim_yuzdesi", None)
    indirimli = getattr(kalem, "indirimli_aylik_maliyet", None)
    if indirim is not None:
        for s in satirlar:
            s.indirim_yuzdesi = float(indirim)
            s.indirimli_aylik = float(indirimli) if indirimli is not None else None
    return satirlar


def kalem_aciklamasi(kalem, para_birimi: str = "USD", dil: Dil = "en") -> str:
    """Kayitli kalemin ayrintili (Azure formatindaki) aciklamasini dondurur."""
    satirlar = kalem_satirlari(kalem, para_birimi, dil)
    aciklama = satirlar[0].yapilandirma_ozeti if satirlar else ""
    return aciklama or (kalem.ozet or "")


def kalem_bolgesi(kalem, para_birimi: str = "USD", dil: Dil = "en") -> str:
    """Kayitli kalemin okunabilir bolge adini dondurur."""
    satirlar = kalem_satirlari(kalem, para_birimi, dil)
    return satirlar[0].bolge if satirlar else ""


def hesaplamadan_satirlar(
    hesaplama, dil: Dil = "en"
) -> tuple[list[DisaAktarimSatiri], float]:
    """Kaydedilmis Hesaplama'nin tum kalemleri icin disa aktarim satirlari."""
    para_birimi = hesaplama.para_birimi or "USD"
    satirlar: list[DisaAktarimSatiri] = []
    for kalem in hesaplama.kalemler:
        satirlar.extend(kalem_satirlari(kalem, para_birimi, dil))
    return satirlar, hesaplama.toplam_aylik_maliyet
