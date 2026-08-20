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
            urun="Managed Disks",
            yapilandirma_ozeti="Standard HDD - S4 - x1 - East US",
            bolge="East US",
            miktar=1,
            birim="disk",
            birim_fiyat=1.536,
            ara_toplam=1.536,
            servis_kategori="Storage",
        ),
        DisaAktarimSatiri(
            urun="Virtual Machines",
            yapilandirma_ozeti="1 x D2s v5 - Ubuntu - East US",
            bolge="East US",
            miktar=730,
            birim="saat",
            birim_fiyat=0.096,
            ara_toplam=70.08,
            servis_kategori="Compute",
        ),
    ]
    icerik = calisma_kitabi_olustur(satirlar, 71.616, "USD", "tr")

    kitap = load_workbook(io.BytesIO(icerik))
    sayfa = kitap.active
    satirlar_okunan = list(sayfa.iter_rows(values_only=True))

    assert satirlar_okunan[0][0] == "Microsoft Azure Estimate"
    assert satirlar_okunan[1][0] == "Your Estimate"
    baslik = satirlar_okunan[2]
    assert baslik[0] == "Service category"
    assert baslik[5] == "Estimated monthly cost"
    assert baslik[6] == "Indirim Yuzdesi"
    assert baslik[9] == "Yillik Tahmini Maliyet"
    assert satirlar_okunan[3][1] == "Managed Disks"
    assert satirlar_okunan[4][1] == "Virtual Machines"
    toplam_satiri = next(s for s in satirlar_okunan if s[3] == "Total")
    assert toplam_satiri[5] == 71.62
    assert toplam_satiri[9] == round(71.616 * 12, 2)
