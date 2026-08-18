"""Sanal Makine secenek/bagimlilik cozumleme.

Bolge/Kategori/Seri/Instance zincirinin veri kaynagi CANLIDIR: bir bolge
icin Azure Retail Prices API'sinden TEK SEFERDE (onbellekli) cekilen temel
(Linux, ek yazilimsiz) tuketim kayitlari islenerek elde edilir -- boylece o
bolgede gercekten var olmayan bir SKU asla listelenmez.

Seri -> Kategori eslemesi ve vCPU/RAM referans degerleri FIYAT DEGILDIR;
Azure'in yayinladigi seri adlandirma kuralindan (armSkuName) ve ailelere
gore ortalama RAM/vCPU oranindan turetilen referans metadatadir. Nadir/ozel
aileler icin RAM degeri yaklasik olabilir -- bu, sadece bilgi amacli
gosterimi etkiler, fiyat hesabini ETKILEMEZ (fiyat her zaman API'den gelir).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.bolgeler import BOLGELER, VARSAYILAN_BOLGE
from app.fiyat_api import kayitlari_getir, odata_metin_kacir
from app.products.base import SecenekSonucu
from app.products.managed_disks import secenekler as disk_secenekler

KATEGORILER = [
    "all",
    "generalpurpose",
    "computeoptimized",
    "memoryoptimized",
    "storageoptimized",
    "gpu",
    "highperformancecompute",
]
_KATEGORI_ETIKETLERI = {
    "all": {"tr": "Tumu", "en": "All"},
    "generalpurpose": {"tr": "Genel amacli", "en": "General purpose"},
    "computeoptimized": {"tr": "Islem optimizasyonlu", "en": "Compute optimized"},
    "memoryoptimized": {"tr": "Bellek optimizasyonlu", "en": "Memory optimized"},
    "storageoptimized": {"tr": "Depolama optimizasyonlu", "en": "Storage optimized"},
    "gpu": {"tr": "GPU", "en": "GPU"},
    "highperformancecompute": {"tr": "Yuksek performansli islem", "en": "High performance compute"},
}

_AILE_KATEGORI = {
    "NC": "gpu", "ND": "gpu", "NV": "gpu", "NG": "gpu",
    "HB": "highperformancecompute", "HC": "highperformancecompute", "HX": "highperformancecompute",
    "DC": "generalpurpose", "FX": "computeoptimized",
    "A": "generalpurpose", "B": "generalpurpose", "D": "generalpurpose",
    "E": "memoryoptimized", "M": "memoryoptimized",
    "F": "computeoptimized", "L": "storageoptimized",
    "N": "gpu", "H": "highperformancecompute", "G": "generalpurpose",
}
_KATEGORI_RAM_ORANI_GIB = {
    "generalpurpose": 4.0,
    "memoryoptimized": 8.0,
    "computeoptimized": 2.0,
    "storageoptimized": 8.0,
    "gpu": 8.0,
    "highperformancecompute": 4.0,
}

_TEMEL_URUN_DESENI = re.compile(r"^Virtual Machines (\S+) Series$")
_GOVDE_DESEN = re.compile(r"^(?:Standard|Basic)_[A-Za-z]+(\d+)([A-Za-z]*)")

ISLETIM_SISTEMLERI = ["linux", "windows"]

WINDOWS_YAZILIM_TIPLERI = [
    ("os-only", {"tr": "(Yalnizca isletim sistemi)", "en": "(OS Only)"}, ["Windows"]),
    ("biztalk", {"tr": "BizTalk", "en": "BizTalk"}, ["Windows", "BizTalk"]),
    ("sql", {"tr": "SQL Server", "en": "SQL Server"}, ["Windows", "SQL"]),
]
LINUX_YAZILIM_TIPLERI = [
    ("ubuntu", {"tr": "Ubuntu", "en": "Ubuntu"}, []),
    ("ubuntu-advantage", {"tr": "Ubuntu Advantage", "en": "Ubuntu Advantage"}, ["Ubuntu Advantage"]),
    ("ubuntu-pro", {"tr": "Ubuntu Pro", "en": "Ubuntu Pro"}, ["Ubuntu Pro"]),
    ("rhel", {"tr": "Red Hat Enterprise Linux", "en": "Red Hat Enterprise Linux"}, ["RHEL"]),
    ("rhel-ha", {"tr": "Red Hat Enterprise Linux (HA)", "en": "Red Hat Enterprise Linux with HA"}, ["RHEL", "HA"]),
    ("rhel-sap", {"tr": "RHEL for SAP Business Applications", "en": "RHEL for SAP Business Applications"}, ["RHEL", "SAP"]),
    ("suse", {"tr": "SUSE Linux Enterprise", "en": "SUSE Linux Enterprise"}, ["SUSE"]),
    ("suse-hpc", {"tr": "SUSE Linux Enterprise for HPC", "en": "SUSE Linux Enterprise for HPC"}, ["SUSE", "HPC"]),
    ("sql-rhel", {"tr": "SQL Server (Red Hat Enterprise Linux)", "en": "SQL Server Red Hat Enterprise Linux"}, ["SQL", "RHEL"]),
    ("sql-suse", {"tr": "SQL Server (SUSE)", "en": "SQL Server SUSE"}, ["SQL", "SUSE"]),
    ("sql-ubuntu", {"tr": "SQL Server (Ubuntu)", "en": "SQL Server Ubuntu Linux"}, ["SQL", "Ubuntu"]),
]
_YAZILIM_TIPI_ARAMA = {
    kod: arama for kod, _, arama in WINDOWS_YAZILIM_TIPLERI + LINUX_YAZILIM_TIPLERI
}
_AHB_UYGUN_TIPLER = {"os-only", "sql", "rhel", "rhel-ha", "rhel-sap", "suse", "suse-hpc", "sql-rhel", "sql-suse"}

TIERLER = ["standard", "basic"]
_TIER_ETIKETLERI = {"standard": {"tr": "Standart", "en": "Standard"}, "basic": {"tr": "Temel", "en": "Basic"}}

SURE_BIRIMLERI = ["saat", "gun", "ay"]
_SURE_ETIKETLERI = {
    "saat": {"tr": "Saat", "en": "Hours"},
    "gun": {"tr": "Gun", "en": "Days"},
    "ay": {"tr": "Ay", "en": "Month"},
}
SAAT_CARPANLARI = {"saat": 1, "gun": 24, "ay": 730}

FIYATLANDIRMA_MODELLERI = ["payg", "savings_1y", "savings_3y", "reservation_1y", "reservation_3y"]
_FIYATLANDIRMA_ETIKETLERI = {
    "payg": {"tr": "Kullandikca ode", "en": "Pay as you go"},
    "savings_1y": {"tr": "1 yillik tasarruf plani", "en": "1 year savings plan"},
    "savings_3y": {"tr": "3 yillik tasarruf plani", "en": "3 year savings plan"},
    "reservation_1y": {"tr": "1 yillik rezervasyon", "en": "1 year reserved"},
    "reservation_3y": {"tr": "3 yillik rezervasyon", "en": "3 year reserved"},
}


@dataclass
class BoyutBilgisi:
    arm_sku_adi: str
    seri: str
    vcpu: int | None
    premium_depolama: bool


@dataclass
class BolgeKatalogu:
    seriler: dict[str, list[BoyutBilgisi]] = field(default_factory=dict)


def _govdeyi_ayristir(arm_sku_adi: str) -> tuple[int | None, str]:
    eslesme = _GOVDE_DESEN.match(arm_sku_adi)
    if not eslesme:
        return None, ""
    return int(eslesme.group(1)), eslesme.group(2)


def premium_depolama_destekli_mi(arm_sku_adi: str) -> bool:
    _, modifiyerler = _govdeyi_ayristir(arm_sku_adi)
    return "s" in modifiyerler.lower()


def seri_kategorisi(seri: str) -> str:
    buyuk = seri.upper()
    for uzunluk in (2, 1):
        onek = buyuk[:uzunluk]
        if onek in _AILE_KATEGORI:
            return _AILE_KATEGORI[onek]
    return "generalpurpose"


def tahmini_ram_gib(vcpu: int | None, kategori: str) -> float | None:
    if vcpu is None:
        return None
    oran = _KATEGORI_RAM_ORANI_GIB.get(kategori, 4.0)
    return round(vcpu * oran, 1)


def kategori_adi(kategori: str, dil: str) -> str:
    return _KATEGORI_ETIKETLERI.get(kategori, {}).get(dil, kategori)


def tier_adi(tier: str, dil: str) -> str:
    return _TIER_ETIKETLERI.get(tier, {}).get(dil, tier)


def sure_birimi_adi(birim: str, dil: str) -> str:
    return _SURE_ETIKETLERI.get(birim, {}).get(dil, birim)


def fiyatlandirma_modeli_adi(model: str, dil: str) -> str:
    return _FIYATLANDIRMA_ETIKETLERI.get(model, {}).get(dil, model)


def yazilim_tipleri(isletim_sistemi: str) -> list[tuple[str, dict, list[str]]]:
    return WINDOWS_YAZILIM_TIPLERI if isletim_sistemi == "windows" else LINUX_YAZILIM_TIPLERI


def yazilim_tipi_arama_anahtar_kelimeleri(yazilim_tipi: str) -> list[str]:
    return _YAZILIM_TIPI_ARAMA.get(yazilim_tipi, [])


def ahb_uygun_mu(yazilim_tipi: str) -> bool:
    return yazilim_tipi in _AHB_UYGUN_TIPLER


async def bolge_katalogunu_getir(bolge: str, tier: str, para_birimi: str = "USD") -> BolgeKatalogu:
    onek = "Basic_" if tier == "basic" else "Standard_"
    filtre = (
        f"serviceName eq 'Virtual Machines' and armRegionName eq '{odata_metin_kacir(bolge)}' "
        f"and priceType eq 'Consumption'"
    )
    kayitlar = await kayitlari_getir(filtre, para_birimi)

    katalog = BolgeKatalogu()
    gorulen: set[str] = set()
    for kayit in kayitlar:
        urun_adi = kayit.get("productName", "")
        eslesme = _TEMEL_URUN_DESENI.match(urun_adi)
        if not eslesme:
            continue  # yazilim ekli (Windows/SQL/RHEL...) urunler - boyut listesi icin gerek yok
        meter_adi = kayit.get("meterName", "")
        if "Spot" in meter_adi or "Low Priority" in meter_adi:
            continue
        arm_sku_adi = kayit.get("armSkuName", "")
        if not arm_sku_adi.startswith(onek):
            continue
        if arm_sku_adi in gorulen:
            continue
        gorulen.add(arm_sku_adi)

        seri = eslesme.group(1)
        vcpu, _ = _govdeyi_ayristir(arm_sku_adi)
        boyut = BoyutBilgisi(
            arm_sku_adi=arm_sku_adi,
            seri=seri,
            vcpu=vcpu,
            premium_depolama=premium_depolama_destekli_mi(arm_sku_adi),
        )
        katalog.seriler.setdefault(seri, []).append(boyut)

    for liste in katalog.seriler.values():
        liste.sort(key=lambda b: (b.vcpu or 0, b.arm_sku_adi))

    return katalog


def _boyut_etiketi(boyut: BoyutBilgisi, dil: str) -> str:
    kategori = seri_kategorisi(boyut.seri)
    ram = tahmini_ram_gib(boyut.vcpu, kategori)
    vcpu_metni = f"{boyut.vcpu} vCPU" if boyut.vcpu is not None else "?"
    ram_metni = f", {ram:g} GiB RAM" if ram is not None else ""
    return f"{boyut.arm_sku_adi}: {vcpu_metni}{ram_metni}"


def bos_yapilandirma() -> dict:
    disk = disk_secenekler.bos_yapilandirma()
    disk["adet"] = 0
    return {
        "bolge": VARSAYILAN_BOLGE,
        "isletim_sistemi": "linux",
        "yazilim_tipi": "ubuntu",
        "kademe": "standard",
        "kategori": "all",
        "seri": "all",
        "sku": None,
        "adet": 1,
        "sure_birimi": "saat",
        "sure_miktar": 730,
        "fiyatlandirma_modeli": "payg",
        "hibrit_fayda": False,
        "disk": disk,
        "bant_genisligi": {
            "veri_transfer_tipi": "interregion",
            "kaynak_bolge": VARSAYILAN_BOLGE,
            "hedef_bolge": next((b.kod for b in BOLGELER if b.kod != VARSAYILAN_BOLGE), VARSAYILAN_BOLGE),
            "cikis_gb": 5,
        },
    }


async def secenekleri_coz(yapilandirma: dict, dil: str) -> SecenekSonucu:
    yeni = dict(yapilandirma)
    yeni["disk"] = dict(yapilandirma.get("disk") or {})
    yeni["bant_genisligi"] = dict(yapilandirma.get("bant_genisligi") or {})

    if not yeni.get("bolge"):
        yeni["bolge"] = VARSAYILAN_BOLGE
    if yeni.get("isletim_sistemi") not in ISLETIM_SISTEMLERI:
        yeni["isletim_sistemi"] = "linux"
    if yeni.get("kademe") not in TIERLER:
        yeni["kademe"] = "standard"
    if yeni.get("kategori") not in KATEGORILER:
        yeni["kategori"] = "all"
    if yeni.get("sure_birimi") not in SAAT_CARPANLARI:
        yeni["sure_birimi"] = "saat"
        yeni["sure_miktar"] = 730
    if yeni.get("fiyatlandirma_modeli") not in FIYATLANDIRMA_MODELLERI:
        yeni["fiyatlandirma_modeli"] = "payg"

    gecerli_yazilim_kodlari = [kod for kod, _, _ in yazilim_tipleri(yeni["isletim_sistemi"])]
    if yeni.get("yazilim_tipi") not in gecerli_yazilim_kodlari:
        yeni["yazilim_tipi"] = gecerli_yazilim_kodlari[0]
    if not ahb_uygun_mu(yeni["yazilim_tipi"]):
        yeni["hibrit_fayda"] = False

    secenekler: dict[str, list[tuple[str, str]]] = {
        "bolge": [(b.kod, b.ad) for b in BOLGELER],
        "isletim_sistemi": [("linux", "Linux"), ("windows", "Windows")],
        "yazilim_tipi": [(kod, etiket[dil]) for kod, etiket, _ in yazilim_tipleri(yeni["isletim_sistemi"])],
        "kademe": [(k, tier_adi(k, dil)) for k in TIERLER],
        "kategori": [(k, kategori_adi(k, dil)) for k in KATEGORILER],
        "sure_birimi": [(b, sure_birimi_adi(b, dil)) for b in SURE_BIRIMLERI],
        "fiyatlandirma_modeli": [(m, fiyatlandirma_modeli_adi(m, dil)) for m in FIYATLANDIRMA_MODELLERI],
    }

    katalog = await bolge_katalogunu_getir(yeni["bolge"], yeni["kademe"])

    tum_seriler = sorted(katalog.seriler.keys())
    if yeni["kategori"] == "all":
        seri_havuzu = tum_seriler
    else:
        seri_havuzu = [s for s in tum_seriler if seri_kategorisi(s) == yeni["kategori"]]

    secenekler["seri"] = [("all", kategori_adi("all", dil))] + [(s, s) for s in seri_havuzu]
    if yeni.get("seri") not in ["all", *seri_havuzu]:
        yeni["seri"] = "all"

    if yeni["seri"] == "all":
        boyut_havuzu = [b for s in seri_havuzu for b in katalog.seriler.get(s, [])]
    else:
        boyut_havuzu = list(katalog.seriler.get(yeni["seri"], []))

    secenekler["sku"] = [(b.arm_sku_adi, _boyut_etiketi(b, dil)) for b in boyut_havuzu]
    gecerli_skular = {b.arm_sku_adi for b in boyut_havuzu}
    secili_boyut: BoyutBilgisi | None = None
    if yeni.get("sku") in gecerli_skular:
        secili_boyut = next(b for b in boyut_havuzu if b.arm_sku_adi == yeni["sku"])
    elif boyut_havuzu:
        secili_boyut = boyut_havuzu[0]
        yeni["sku"] = secili_boyut.arm_sku_adi
    else:
        yeni["sku"] = None

    # Gomulu Yonetilen Disk alt-blogu: sadece secili SKU premium depolamayi
    # destekliyorsa Premium SSD/v2/Ultra kademeleri sunulur.
    disk_yapilandirma = yeni["disk"]
    disk_yapilandirma.setdefault("bolge", yeni["bolge"])
    disk_yapilandirma["bolge"] = yeni["bolge"]
    disk_secenek_sonucu = disk_secenekler.secenekleri_coz(disk_yapilandirma, dil)
    if secili_boyut is not None and not secili_boyut.premium_depolama:
        if disk_secenek_sonucu.yapilandirma.get("kademe") in ("premiumssd", "premiumssdv2", "ultrassd"):
            disk_secenek_sonucu.yapilandirma["kademe"] = "standardhdd"
            disk_secenek_sonucu = disk_secenekler.secenekleri_coz(disk_secenek_sonucu.yapilandirma, dil)
        disk_secenek_sonucu.secenekler["kademe"] = [
            (k, disk_secenekler.kademe_adi(k, dil)) for k in ("standardhdd", "standardssd")
        ]
    yeni["disk"] = disk_secenek_sonucu.yapilandirma
    secenekler["disk"] = disk_secenek_sonucu.secenekler
    secenekler["disk_gorunur_alanlar"] = disk_secenek_sonucu.gorunur_alanlar

    bant = yeni["bant_genisligi"]
    if bant.get("veri_transfer_tipi") not in ("interregion", "internetegress"):
        bant["veri_transfer_tipi"] = "interregion"
    if not bant.get("kaynak_bolge"):
        bant["kaynak_bolge"] = yeni["bolge"]
    secenekler["bant_genisligi_bolge"] = [(b.kod, b.ad) for b in BOLGELER]
    secenekler["bant_genisligi_tipi"] = [
        ("interregion", {"tr": "Bolgeler arasi", "en": "Inter Region"}[dil]),
        ("internetegress", {"tr": "Internet cikisi", "en": "Internet Egress"}[dil]),
    ]
    if bant["veri_transfer_tipi"] != "interregion":
        bant["hedef_bolge"] = None

    gorunur = {"bolge", "isletim_sistemi", "yazilim_tipi", "kademe", "kategori", "seri", "sku", "adet", "sure_birimi", "sure_miktar", "fiyatlandirma_modeli"}
    if ahb_uygun_mu(yeni["yazilim_tipi"]):
        gorunur.add("hibrit_fayda")

    return SecenekSonucu(yapilandirma=yeni, secenekler=secenekler, gorunur_alanlar=gorunur)
