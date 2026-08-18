"""Azure bolge referans listesi.

Bu liste fiyat DEGERI icermez; sadece Azure'in yayinladigi ARM bolge adlarini
(armRegionName) ve goruntuleme adlarini eslestirir. Fiyatlar her zaman Azure
Retail Prices API'sinden aninda cekilir (bkz. app/fiyat_api.py).

Kapsam, resmi Azure Pricing Calculator'in Sanal Makineler/Yonetilen Diskler
kartlarinda gosterdigi bolge listesiyle uyumludur (canli inceleme ile
dogrulanmistir). Cok yeni/az bilinen birkac bolge (orn. Avusturya, Belcika)
Microsoft tarafindan duyurulmus olup ARM kodu degisebilir; bu bolgeler icin
fiyat sorgusu sonuc bulamazsa uygulama net bir hata gosterir, uydurma fiyat
uretmez.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Bolge:
    kod: str  # armRegionName - Retail Prices API sorgularinda kullanilir
    ad: str  # goruntuleme adi (TR/EN ayrimi yapmiyoruz; bolge adlari teknik kimlik)


BOLGELER: list[Bolge] = [
    Bolge("eastus", "East US"),
    Bolge("eastus2", "East US 2"),
    Bolge("centralus", "Central US"),
    Bolge("northcentralus", "North Central US"),
    Bolge("southcentralus", "South Central US"),
    Bolge("westcentralus", "West Central US"),
    Bolge("westus", "West US"),
    Bolge("westus2", "West US 2"),
    Bolge("westus3", "West US 3"),
    Bolge("canadacentral", "Canada Central"),
    Bolge("canadaeast", "Canada East"),
    Bolge("brazilsouth", "Brazil South"),
    Bolge("brazilsoutheast", "Brazil Southeast"),
    Bolge("mexicocentral", "Mexico Central"),
    Bolge("chilecentral", "Chile Central"),
    Bolge("uksouth", "UK South"),
    Bolge("ukwest", "UK West"),
    Bolge("northeurope", "North Europe"),
    Bolge("westeurope", "West Europe"),
    Bolge("francecentral", "France Central"),
    Bolge("francesouth", "France South"),
    Bolge("germanywestcentral", "Germany West Central"),
    Bolge("germanynorth", "Germany North"),
    Bolge("switzerlandnorth", "Switzerland North"),
    Bolge("switzerlandwest", "Switzerland West"),
    Bolge("norwayeast", "Norway East"),
    Bolge("norwaywest", "Norway West"),
    Bolge("swedencentral", "Sweden Central"),
    Bolge("swedensouth", "Sweden South"),
    Bolge("polandcentral", "Poland Central"),
    Bolge("italynorth", "Italy North"),
    Bolge("spaincentral", "Spain Central"),
    Bolge("uaenorth", "UAE North"),
    Bolge("uaecentral", "UAE Central"),
    Bolge("qatarcentral", "Qatar Central"),
    Bolge("israelcentral", "Israel Central"),
    Bolge("southafricanorth", "South Africa North"),
    Bolge("southafricawest", "South Africa West"),
    Bolge("eastasia", "East Asia"),
    Bolge("southeastasia", "Southeast Asia"),
    Bolge("japaneast", "Japan East"),
    Bolge("japanwest", "Japan West"),
    Bolge("koreacentral", "Korea Central"),
    Bolge("koreasouth", "Korea South"),
    Bolge("centralindia", "Central India"),
    Bolge("southindia", "South India"),
    Bolge("westindia", "West India"),
    Bolge("indonesiacentral", "Indonesia Central"),
    Bolge("malaysiawest", "Malaysia West"),
    Bolge("newzealandnorth", "New Zealand North"),
    Bolge("australiaeast", "Australia East"),
    Bolge("australiasoutheast", "Australia Southeast"),
    Bolge("australiacentral", "Australia Central"),
    Bolge("australiacentral2", "Australia Central 2"),
    Bolge("usgovvirginia", "US Gov Virginia"),
    Bolge("usgovtexas", "US Gov Texas"),
    Bolge("usgovarizona", "US Gov Arizona"),
]

_BOLGE_SOZLUGU = {b.kod: b for b in BOLGELER}
VARSAYILAN_BOLGE = "westeurope"


def bolge_bul(kod: str) -> Bolge | None:
    return _BOLGE_SOZLUGU.get(kod)


def bolge_gecerli_mi(kod: str) -> bool:
    return kod in _BOLGE_SOZLUGU
