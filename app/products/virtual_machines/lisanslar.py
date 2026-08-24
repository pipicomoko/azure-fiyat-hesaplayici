"""Virtual Machines Licenses servisi uzerinden yazilim lisans fiyati.

Azure Pricing Calculator, SQL/BizTalk/RHEL/Ubuntu Pro gibi yazilimlari
SKU'ya bagli 'all-in' Virtual Machines urunu olarak degil,
'Virtual Machines Licenses' altinda vCPU bazli saatlik lisans olarak
faturalandirir. Bu modul o kayitlari cozer.
"""

from __future__ import annotations

import re

from app.fiyat_api import kayitlari_getir, odata_metin_kacir
from app.products.base import FiyatBulunamadiHatasi

# yazilim_tipi -> (lisans productName, Windows OS farki gerekli mi, SQL 4-cekirdek min?)
_LISANS_HARITASI: dict[str, tuple[str, bool, bool]] = {
    # Windows yazilim
    "sql": ("SQL Server Standard", True, True),  # geriye donuk
    "sql-web": ("SQL Server Web", True, True),
    "sql-standard": ("SQL Server Standard", True, True),
    "sql-enterprise": ("SQL Server Enterprise", True, True),
    "biztalk": ("BizTalk Server Standard", True, False),
    "biztalk-standard": ("BizTalk Server Standard", True, False),
    "biztalk-enterprise": ("BizTalk Server Enterprise", True, False),
    # Linux OS lisanslari
    "rhel": ("Red Hat Enterprise Linux", False, False),
    "rhel-ha": ("Red Hat Enterprise Linux with HA", False, False),
    "rhel-sap": ("RHEL for SAP Business Applications", False, False),
    "suse": ("SUSE Linux Enterprise Server", False, False),
    "suse-hpc": ("SUSE Linux Enterprise Server for HPC Standard", False, False),
    "ubuntu-pro": ("Ubuntu Pro", False, False),
    # Linux + SQL (tek urunde birlesik lisans)
    "sql-rhel": ("SQL Server Standard Red Hat Enterprise Linux", False, True),
    "sql-rhel-web": ("SQL Server Web Red Hat Enterprise Linux", False, True),
    "sql-rhel-standard": ("SQL Server Standard Red Hat Enterprise Linux", False, True),
    "sql-rhel-enterprise": (
        "SQL Server Enterprise Red Hat Enterprise Linux",
        False,
        True,
    ),
    "sql-suse": ("SQL Server Standard SLES", False, True),
    "sql-suse-web": ("SQL Server Web SLES", False, True),
    "sql-suse-standard": ("SQL Server Standard SLES", False, True),
    "sql-suse-enterprise": ("SQL Server Enterprise SLES", False, True),
    "sql-ubuntu": ("SQL Server Standard Ubuntu Pro", False, True),
    "sql-ubuntu-web": ("SQL Server Web Ubuntu Pro", False, True),
    "sql-ubuntu-standard": ("SQL Server Standard Ubuntu Pro", False, True),
    "sql-ubuntu-enterprise": ("SQL Server Enterprise Ubuntu Pro", False, True),
}

# Eski tek kod -> yeni varsayilan surum
_YAZILIM_TIPI_ESKI_ESLEME = {
    "sql": "sql-standard",
    "biztalk": "biztalk-standard",
    "sql-rhel": "sql-rhel-standard",
    "sql-suse": "sql-suse-standard",
    "sql-ubuntu": "sql-ubuntu-standard",
}

_ARALIK_DESEN = re.compile(
    r"^(\d+)\s*-\s*(\d+)\s+vCPU(?:\s+VM)?\s+License$",
    re.IGNORECASE,
)
_TEK_VCPU_DESEN = re.compile(
    r"^(\d+)[-\s]?vCPU(?:\s+VM)?\s+License$",
    re.IGNORECASE,
)
_VCORE_DESEN = re.compile(
    r"^(\d+)\s+vCore\s+License$",
    re.IGNORECASE,
)


def yazilim_tipini_normallestir(yazilim_tipi: str | None) -> str:
    kod = (yazilim_tipi or "").strip()
    return _YAZILIM_TIPI_ESKI_ESLEME.get(kod, kod)


def lisans_tanimi(yazilim_tipi: str) -> tuple[str, bool, bool] | None:
    kod = yazilim_tipini_normallestir(yazilim_tipi)
    return _LISANS_HARITASI.get(kod)


def lisansli_yazilim_mi(yazilim_tipi: str) -> bool:
    return lisans_tanimi(yazilim_tipi) is not None


def windows_os_gerekli_mi(isletim_sistemi: str, yazilim_tipi: str) -> bool:
    if isletim_sistemi == "windows":
        return True
    tanim = lisans_tanimi(yazilim_tipi)
    return bool(tanim and tanim[1])


def _saatlik_adaylar(kayitlar: list[dict]) -> list[dict]:
    adaylar = []
    for k in kayitlar:
        if k.get("type") != "Consumption":
            continue
        if (k.get("unitOfMeasure") or "") not in ("1 Hour", "Hour", "1 Hour/Hour"):
            # Bazi kayitlar '1 Hour' kullanir
            uom = (k.get("unitOfMeasure") or "").lower()
            if "hour" not in uom:
                continue
        fiyat = k.get("retailPrice")
        if fiyat is None:
            continue
        try:
            fiyat_f = float(fiyat)
        except (TypeError, ValueError):
            continue
        if fiyat_f < 0:
            continue
        adaylar.append(k)
    return adaylar


def _vcpu_icin_lisans_fiyati(
    kayitlar: list[dict], vcpu: int, dort_cekirdek_min: bool
) -> float | None:
    """vCPU sayisina en uygun saatlik lisans birim fiyatini dondurur."""
    hedef = max(1, int(vcpu))
    if dort_cekirdek_min:
        faturalanan = max(hedef, 4)
    else:
        faturalanan = hedef

    adaylar = _saatlik_adaylar(kayitlar)
    if not adaylar:
        return None

    # meterName -> en ucuz pozitif (AHB 0.0 kayitlarini atla, yoksa en ucuz)
    meter_fiyat: dict[str, float] = {}
    for k in adaylar:
        meter = (k.get("meterName") or "").strip()
        if not meter:
            continue
        fiyat = float(k["retailPrice"])
        onceki = meter_fiyat.get(meter)
        if onceki is None:
            meter_fiyat[meter] = fiyat
        elif fiyat > 0 and (onceki == 0 or fiyat < onceki):
            meter_fiyat[meter] = fiyat
        elif onceki == 0 and fiyat > 0:
            meter_fiyat[meter] = fiyat

    # 1) Tam vCPU eslesmesi
    for etiket in (
        f"{faturalanan} vCPU VM License",
        f"{faturalanan}-vCPU VM License",
        f"{faturalanan} vCPU License",
        f"{faturalanan}-vCPU License",
    ):
        if etiket in meter_fiyat and meter_fiyat[etiket] > 0:
            return meter_fiyat[etiket]

    # 2) Aralik meter (1-4, 1-8 ...)
    aralik_adaylari: list[tuple[int, int, float]] = []
    for meter, fiyat in meter_fiyat.items():
        if fiyat <= 0:
            continue
        m = _ARALIK_DESEN.match(meter)
        if m:
            alt, ust = int(m.group(1)), int(m.group(2))
            if alt <= faturalanan <= ust:
                aralik_adaylari.append((ust - alt, alt, fiyat))
    if aralik_adaylari:
        aralik_adaylari.sort(key=lambda x: (x[0], x[2]))
        return aralik_adaylari[0][2]

    # 3) En yakin ust tek-vCPU meter
    tekler: list[tuple[int, float]] = []
    for meter, fiyat in meter_fiyat.items():
        if fiyat <= 0:
            continue
        m = _TEK_VCPU_DESEN.match(meter)
        if m and not _ARALIK_DESEN.match(meter):
            n = int(m.group(1))
            if n >= faturalanan:
                tekler.append((n, fiyat))
    if tekler:
        tekler.sort(key=lambda x: (x[0], x[1]))
        return tekler[0][1]

    # 4) vCore * faturalanan
    for meter, fiyat in meter_fiyat.items():
        if fiyat <= 0:
            continue
        m = _VCORE_DESEN.match(meter)
        if m and int(m.group(1)) == 1:
            return fiyat * faturalanan

    # 5) Ubuntu Advantage benzeri destek meterleri: en ucuz pozitif
    destek = [f for m, f in meter_fiyat.items() if f > 0 and "Support" in m]
    if destek:
        return min(destek)

    pozitif = [f for f in meter_fiyat.values() if f > 0]
    return min(pozitif) if pozitif else None


async def lisans_saatlik_fiyat(
    yazilim_tipi: str,
    vcpu: int,
    para_birimi: str,
) -> float:
    """Secilen yazilim icin saatlik lisans birim fiyati (VM basina)."""
    tanim = lisans_tanimi(yazilim_tipi)
    if tanim is None:
        raise FiyatBulunamadiHatasi()
    urun_adi, _, dort_min = tanim
    filtre = (
        f"serviceName eq 'Virtual Machines Licenses' "
        f"and productName eq '{odata_metin_kacir(urun_adi)}' "
        f"and priceType eq 'Consumption'"
    )
    kayitlar = await kayitlari_getir(filtre, para_birimi)
    fiyat = _vcpu_icin_lisans_fiyati(kayitlar, vcpu, dort_min)
    if fiyat is None:
        raise FiyatBulunamadiHatasi()
    return fiyat


_windows_sku_cache: dict[str, set[str]] = {}


async def bolgede_windows_skulari(bolge: str, para_birimi: str = "USD") -> set[str]:
    """Bolgede Windows Series tuketim fiyati olan armSkuName kumesi."""
    anahtar = f"{bolge}:{para_birimi}"
    if anahtar in _windows_sku_cache:
        return _windows_sku_cache[anahtar]
    filtre = (
        f"serviceName eq 'Virtual Machines' and armRegionName eq '{odata_metin_kacir(bolge)}' "
        f"and priceType eq 'Consumption' and endswith(productName, 'Series Windows')"
    )
    kayitlar = await kayitlari_getir(filtre, para_birimi)
    skular = {
        k.get("armSkuName", "")
        for k in kayitlar
        if k.get("armSkuName")
        and "Spot" not in (k.get("meterName") or "")
        and "Low Priority" not in (k.get("meterName") or "")
    }
    _windows_sku_cache[anahtar] = skular
    return skular


def windows_sku_onbellegi_temizle() -> None:
    _windows_sku_cache.clear()
