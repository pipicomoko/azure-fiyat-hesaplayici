import io

import pytest
from openpyxl import load_workbook

from app.disa_aktar import TahminBosHatasi, calisma_kitabi_olustur
from app.products.base import DisaAktarimSatiri


def test_bos_tahmin_disa_aktarilamaz():
    with pytest.raises(TahminBosHatasi):
        calisma_kitabi_olustur([], 0.0, "USD", "tr")


def test_calisma_kitabi_basliklar_ve_toplam():
    satirlar = [
        DisaAktarimSatiri(
            urun="Yonetilen Diskler", yapilandirma_ozeti="Standard HDD - S4 - x1 - East US",
            bolge="East US", miktar=1, birim="disk", birim_fiyat=1.536, ara_toplam=1.536,
        ),
        DisaAktarimSatiri(
            urun="Sanal Makineler", yapilandirma_ozeti="1 x D2s v5 - Ubuntu - East US",
            bolge="East US", miktar=730, birim="saat", birim_fiyat=0.096, ara_toplam=70.08,
        ),
    ]
    icerik = calisma_kitabi_olustur(satirlar, 71.616, "USD", "tr")

    kitap = load_workbook(io.BytesIO(icerik))
    sayfa = kitap.active
    satirlar_okunan = list(sayfa.iter_rows(values_only=True))

    assert satirlar_okunan[0] == (
        "Urun", "Yapilandirma", "Bolge", "Miktar", "Birim", "Birim Fiyat", "Ara Toplam (Aylik)"
    )
    assert satirlar_okunan[1][0] == "Yonetilen Diskler"
    assert satirlar_okunan[2][0] == "Sanal Makineler"
    genel_toplam_satiri = next(s for s in satirlar_okunan if s[0] == "Genel Toplam (Aylik)")
    assert genel_toplam_satiri[6] == 71.62
