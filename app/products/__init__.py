"""Urun kayit defteri.

Yeni bir Azure urunu eklemek = app/products/base.py'deki UrunModulu
sozlesmesini uygulayan bir paket yazip burada KAYITLI_URUNLER'e eklemek
demektir. Tahmin motoru, disa aktarim ve sablonlar bu sozlukten baska
hicbir yerden urun bilgisi almaz; bu yuzden yeni bir urun eklemek, tahmin
motorunu, on yuzu ya da disa aktarimi degistirmeyi gerektirmez.

Bu surumde SADECE Sanal Makineler ve Yonetilen Diskler etkindir (kapsam
kurali geregi) -- KAYITLI_URUNLER'e baska bir modul eklenmedigi surece
arayuzde baska urun gorunmez.
"""

from __future__ import annotations

from app.products.base import UrunModulu
from app.products.managed_disks import ManagedDisksUrunu
from app.products.virtual_machines import VirtualMachinesUrunu

KAYITLI_URUNLER: dict[str, UrunModulu] = {
    "virtual_machines": VirtualMachinesUrunu(),
    "managed_disks": ManagedDisksUrunu(),
}


def urun_al(urun_tipi: str) -> UrunModulu | None:
    return KAYITLI_URUNLER.get(urun_tipi)
