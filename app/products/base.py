"""Urun modulu sozlesmesi.

Yeni bir Azure urunu eklemek = bu sozlesmeyi uygulayan bir paket yazip
`app/products/__init__.py`'deki KAYITLI_URUNLER sozlugune eklemek demektir.
Tahmin motoru (routers/tahmin.py), disa aktarim (disa_aktar.py) ve ortak
sablonlar bu arayuz uzerinden calisir; urune ozel dallanma icermezler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class FiyatBulunamadiHatasi(Exception):
    """Verilen yapilandirma icin Azure Retail Prices API'sinde eslesen kayit
    bulunamadi. Cagiran taraf ASLA tahmini/uydurma bir fiyat GOSTERMEMELI,
    bunun yerine kullaniciya net, yerellestirilmis bir hata sunmalidir."""


class GecersizYapilandirmaHatasi(Exception):
    """Whitelist disi / parse edilemeyen alan (BUG-15).

    Sessizce varsayilan SKU/fiyata dusulmez; cagiran hata gosterir.
    """

    def __init__(self, alan: str = ""):
        self.alan = alan
        super().__init__(alan or "gecersiz_yapilandirma")


@dataclass
class FiyatKalemi:
    """Tek bir maliyet bileseni (orn. 'Compute', 'Isletim sistemi', 'Depolama',
    'Islemler', 'Bant genisligi'). Deger 0 olabilir (orn. AHB acikken OS
    lisansi 0 gorunur, tipki resmi hesaplayicida oldugu gibi)."""

    anahtar: str  # ceviri anahtari (orn. "vm_bilesen_compute")
    miktar: float
    birim: str
    birim_fiyat: float
    aylik_tutar: float


@dataclass
class FiyatSonucu:
    aylik_toplam: float
    para_birimi: str
    kalemler: list[FiyatKalemi] = field(default_factory=list)


@dataclass
class DisaAktarimSatiri:
    """Excel'e aktarilacak tek bir satir.

    Azure orijinal formatina uygun alanlar:
      servis_kategori  → Service category (orn. Compute, Storage)
      urun             → Service type     (orn. Virtual Machines)
      ozel_ad          → Custom name      (kullanici tanimli isim, genelde bos)
      bolge            → Region
      yapilandirma_ozeti → Description
      ara_toplam       → Estimated monthly cost
      on_odeme         → Estimated upfront cost (genelde 0)
    """

    urun: str
    yapilandirma_ozeti: str
    bolge: str
    miktar: float
    birim: str
    birim_fiyat: float
    ara_toplam: float
    servis_kategori: str = ""
    ozel_ad: str = ""
    on_odeme: float = 0.0
    indirim_yuzdesi: float | None = None
    indirimli_aylik: float | None = None


@dataclass
class SecenekSonucu:
    """secenekleri_getir()'in donus degeri.

    `yapilandirma`: olasi duzeltmelerle (orn. artik gecersiz olan bir SKU
    secimi, yeni listenin ilk elemaniyla degistirilir) guncellenmis tam
    yapilandirma.
    `secenekler`: alan adi -> [(deger, etiket), ...] biciminde, o an
    gosterilmesi gereken her bagimli (dropdown) alanin secim listesi.
    `gorunur_alanlar`: sayisal/checkbox gibi dropdown OLMAYAN alanlardan
    hangilerinin, secili kademe/SKU icin anlamli oldugunu belirtir (orn.
    'islem_adet' sadece Standard HDD/SSD'de gorunur). Sablonlar, gecersiz
    bir kombinasyonda alani gostermemek icin bu kumeyi kullanir.
    """

    yapilandirma: dict[str, Any]
    secenekler: dict[str, list[tuple[str, str]]]
    gorunur_alanlar: set[str] = field(default_factory=set)


class UrunModulu(Protocol):
    anahtar: str  # orn. "virtual_machines" - formlardaki urun_tipi degeriyle esler
    sablon_adi: str  # urunler/_vm_form.html gibi, satir formunun Jinja parcaciği

    def ad(self, dil: str) -> str: ...

    def aciklama(self, dil: str) -> str: ...

    def bos_yapilandirma(self) -> dict[str, Any]:
        """Yeni bir kalem eklenirken kullanilacak varsayilan yapilandirma."""
        ...

    async def secenekleri_getir(
        self, yapilandirma: dict[str, Any], dil: str
    ) -> SecenekSonucu:
        """Kismi/tam yapilandirmaya gore bagimli alanlarin secim listelerini
        cozer (orn. Kategori -> Seri, Isletim Sistemi -> Yazilim Tipi, Disk
        Kademesi -> Redundancy/Disk Boyutu). Sonuc, gecersiz kombinasyonlarin
        arayuzde asla gosterilmeyecegini garanti eder."""
        ...

    async def fiyatla(
        self, yapilandirma: dict[str, Any], para_birimi: str
    ) -> FiyatSonucu:
        """FiyatBulunamadiHatasi firlatabilir; cagiran bunu yakalayip
        kullaniciya `t('fiyat_bulunamadi', dil)` gosterir."""
        ...

    def ozet(self, yapilandirma: dict[str, Any], dil: str) -> str:
        """Kalemin tek satirlik ozeti (gecmis/karsilastirma ekranlarinda kullanilir)."""
        ...

    def disa_aktarim_satirlari(
        self, yapilandirma: dict[str, Any], fiyat: FiyatSonucu, dil: str
    ) -> list[DisaAktarimSatiri]:
        """fiyatla()'nin sonucunu birebir kullanir (yeniden hesaplama YAPMAZ)
        ki Excel'deki rakamlar ekranda gorunenle her zaman birebir essin."""
        ...
