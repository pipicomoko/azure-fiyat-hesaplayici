"""Yonetilen Disk secenek/bagimlilik cozumleme.

SKU boyut tablolarindaki GiB degerleri Azure'in yayinladigi SABIT disk
boyutlaridir -- FIYAT DEGILDIR, sadece hangi SKU kodunun kac GiB oldugunu
bilmek icin referans metadatadir (anlik goruntu/gizli sifreleme maliyeti
GiB basina hesaplanirken kullanilir; fiyatin kendisi her zaman Retail Prices
API'sinden gelir).

Kademeye gore hangi alanlarin gorunecegi (Redundancy, Storage transactions,
Add Snapshot, Confidential OS Encryption, Disk Bursting, Reservation) resmi
hesaplayicinin canli DOM'u incelenerek dogrulanmistir.
"""

from __future__ import annotations

from app.bolgeler import BOLGELER, VARSAYILAN_BOLGE
from app.products.base import SecenekSonucu

KADEMELER = ["standardhdd", "standardssd", "premiumssd", "premiumssdv2", "ultrassd"]

_KADEME_ETIKETLERI = {
    "standardhdd": {"tr": "Standard HDD", "en": "Standard HDD"},
    "standardssd": {"tr": "Standard SSD", "en": "Standard SSD"},
    "premiumssd": {"tr": "Premium SSD", "en": "Premium SSD"},
    "premiumssdv2": {"tr": "Premium SSD v2", "en": "Premium SSD v2"},
    "ultrassd": {"tr": "Ultra Disk", "en": "Ultra Disk"},
}

STANDARDHDD_SKU_GIB = {
    "S4": 32, "S6": 64, "S10": 128, "S15": 256, "S20": 512,
    "S30": 1024, "S40": 2048, "S50": 4096, "S60": 8192, "S70": 16384, "S80": 32767,
}
STANDARDSSD_SKU_GIB = {
    "E1": 4, "E2": 8, "E3": 16, "E4": 32, "E6": 64, "E10": 128, "E15": 256,
    "E20": 512, "E30": 1024, "E40": 2048, "E50": 4096, "E60": 8192, "E70": 16384, "E80": 32767,
}
PREMIUMSSD_SKU_GIB = {
    "P1": 4, "P2": 8, "P3": 16, "P4": 32, "P6": 64, "P10": 128, "P15": 256,
    "P20": 512, "P30": 1024, "P40": 2048, "P50": 4096, "P60": 8192, "P70": 16384, "P80": 32767,
}

SABIT_SKU_TABLOLARI: dict[str, dict[str, int]] = {
    "standardhdd": STANDARDHDD_SKU_GIB,
    "standardssd": STANDARDSSD_SKU_GIB,
    "premiumssd": PREMIUMSSD_SKU_GIB,
}

# Premium SSD'de on-demand patlama (bursting) sadece kucuk (P1-P20) boyutlarda sunulur.
PREMIUMSSD_PATLAMA_UYGUN_SKU = {"P1", "P2", "P3", "P4", "P6", "P10", "P15", "P20"}

REDUNDANS_DESTEKLEYEN_KADEMELER = {"standardssd", "premiumssd"}
SNAPSHOT_DESTEKLEYEN_KADEMELER = {"standardhdd", "standardssd", "premiumssd"}
GIZLI_SIFRELEME_DESTEKLEYEN_KADEMELER = {"standardhdd", "standardssd", "premiumssd"}
ISLEM_DESTEKLEYEN_KADEMELER = {"standardhdd", "standardssd"}
REZERVASYON_DESTEKLEYEN_KADEMELER = {"premiumssd"}
SURE_SECICI_KADEMELER = {"premiumssdv2", "ultrassd"}

_SURE_BIRIM_KODLARI = ["saat", "gun", "ay"]
_SURE_ETIKETLERI = {
    "saat": {"tr": "Saat", "en": "Hours"},
    "gun": {"tr": "Gun", "en": "Days"},
    "ay": {"tr": "Ay", "en": "Month"},
}
SAAT_CARPANLARI = {"saat": 1, "gun": 24, "ay": 730}


def _ultra_disk_boyutlari() -> list[int]:
    boyutlar = [4, 8, 16, 32, 64, 128, 256, 512]
    boyutlar += [1024 * tib for tib in range(1, 65)]
    return boyutlar


ULTRA_DISK_GIB_ADIMLARI = _ultra_disk_boyutlari()


def kademe_adi(kademe: str, dil: str) -> str:
    return _KADEME_ETIKETLERI.get(kademe, {}).get(dil, kademe)


def sure_birimi_adi(birim: str, dil: str) -> str:
    return _SURE_ETIKETLERI.get(birim, {}).get(dil, birim)


def _gib_etiket(gib: int) -> str:
    return f"{gib:,} GiB".replace(",", ".")


def bos_yapilandirma() -> dict:
    return {
        "bolge": VARSAYILAN_BOLGE,
        "kademe": "standardhdd",
        "yedeklilik": "LRS",
        "sku": "S4",
        "disk_boyutu_gib": 32,
        "iops": 3000,
        "throughput_mbps": 125,
        "sure_birimi": "saat",
        "sure_miktar": 730,
        "adet": 1,
        "islem_adet": 100,
        "anlik_goruntu": False,
        "gizli_sifreleme": False,
        "patlama_etkin": False,
        "fiyatlandirma_modeli": "payg",
    }


def secenekleri_coz(yapilandirma: dict, dil: str) -> SecenekSonucu:
    yeni = dict(yapilandirma)
    kademe = yeni.get("kademe")
    if kademe not in KADEMELER:
        kademe = "standardhdd"
    yeni["kademe"] = kademe

    if not yeni.get("bolge"):
        yeni["bolge"] = VARSAYILAN_BOLGE

    secenekler: dict[str, list[tuple[str, str]]] = {
        "bolge": [(b.kod, b.ad) for b in BOLGELER],
        "kademe": [(k, kademe_adi(k, dil)) for k in KADEMELER],
    }

    if kademe in REDUNDANS_DESTEKLEYEN_KADEMELER:
        secenekler["yedeklilik"] = [("LRS", "LRS"), ("ZRS", "ZRS")]
        if yeni.get("yedeklilik") not in ("LRS", "ZRS"):
            yeni["yedeklilik"] = "LRS"
    else:
        yeni["yedeklilik"] = "LRS"

    if kademe in SABIT_SKU_TABLOLARI:
        tablo = SABIT_SKU_TABLOLARI[kademe]
        secenekler["sku"] = [(kod, f"{kod}: {_gib_etiket(gib)}") for kod, gib in tablo.items()]
        if yeni.get("sku") not in tablo:
            yeni["sku"] = next(iter(tablo))
        yeni["disk_boyutu_gib"] = tablo[yeni["sku"]]
    else:
        yeni["sku"] = None
        if kademe == "ultrassd":
            secenekler["disk_boyutu_gib"] = [
                (str(g), _gib_etiket(g)) for g in ULTRA_DISK_GIB_ADIMLARI
            ]
            if yeni.get("disk_boyutu_gib") not in ULTRA_DISK_GIB_ADIMLARI:
                yeni["disk_boyutu_gib"] = 4
            if not yeni.get("iops"):
                yeni["iops"] = 100
            if not yeni.get("throughput_mbps"):
                yeni["throughput_mbps"] = 1
        else:  # premiumssdv2 - serbest GiB/IOPS/throughput girisi
            if not yeni.get("disk_boyutu_gib"):
                yeni["disk_boyutu_gib"] = 1
            if not yeni.get("iops"):
                yeni["iops"] = 3000
            if not yeni.get("throughput_mbps"):
                yeni["throughput_mbps"] = 125

    gorunur: set[str] = {"bolge", "kademe", "adet"}

    if kademe in SURE_SECICI_KADEMELER:
        secenekler["sure_birimi"] = [(b, sure_birimi_adi(b, dil)) for b in _SURE_BIRIM_KODLARI]
        if yeni.get("sure_birimi") not in SAAT_CARPANLARI:
            yeni["sure_birimi"] = "saat"
            yeni["sure_miktar"] = 730
        gorunur |= {"sure_birimi", "sure_miktar", "iops", "throughput_mbps"}

    if kademe not in ISLEM_DESTEKLEYEN_KADEMELER:
        yeni["islem_adet"] = 0
    else:
        gorunur.add("islem_adet")

    if kademe not in SNAPSHOT_DESTEKLEYEN_KADEMELER:
        yeni["anlik_goruntu"] = False
    else:
        gorunur.add("anlik_goruntu")

    if kademe not in GIZLI_SIFRELEME_DESTEKLEYEN_KADEMELER:
        yeni["gizli_sifreleme"] = False
    else:
        gorunur.add("gizli_sifreleme")

    if kademe != "premiumssd" or yeni.get("sku") not in PREMIUMSSD_PATLAMA_UYGUN_SKU:
        yeni["patlama_etkin"] = False
    else:
        gorunur.add("patlama_etkin")

    if kademe in REZERVASYON_DESTEKLEYEN_KADEMELER:
        secenekler["fiyatlandirma_modeli"] = [
            ("payg", {"tr": "Kullandikca ode", "en": "Pay as you go"}[dil]),
            ("reservation_1y", {"tr": "1 yillik rezervasyon", "en": "1 year reserved"}[dil]),
        ]
        if yeni.get("fiyatlandirma_modeli") not in ("payg", "reservation_1y"):
            yeni["fiyatlandirma_modeli"] = "payg"
    else:
        yeni["fiyatlandirma_modeli"] = "payg"

    return SecenekSonucu(yapilandirma=yeni, secenekler=secenekler, gorunur_alanlar=gorunur)
