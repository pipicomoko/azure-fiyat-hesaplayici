"""Kimlik dogrulama (LDAP) ve yetkilendirme (AD grubu -> izin eslemesi).

Kimlik dogrulama sadece LDAP bind ile yapilir; kullanici adi/sifre HICBIR
ZAMAN veritabanina yazilmaz ve HICBIR ZAMAN loglanmaz (asagida sifre sadece
LDAP kutuphanesine parametre olarak gecilir, baska hicbir yerde tutulmaz).

Uretimde LDAP baglantisi LDAPS ya da StartTLS ile TLS altinda calisir;
LDAP_TLS_MODU=kapali sadece gelistirme ortaminda kullanilabilir.

Yetkilendirme, AD grup uyeliklerinin uygulama izinlerine eslenmesiyle
belirlenir. Bu esleme config/yetki_haritasi.json dosyasindan (ya da
YETKI_HARITASI_DOSYASI ortam degiskeniyle belirtilen baska bir dosyadan)
okunur; kod degistirmeden yeniden yapilandirilabilir. Ayni `yetki_gerekli`
bagimliligi hem sayfa/uc noktalarinda hem de (kullanici_izinli_mi araciligiyla)
sablonlarda kullanilir, boylece on yuz ve arka uc ayni kurallari uygular.
"""

import json
import logging
import os
import ssl
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from ldap3 import ALL, AUTO_BIND_NO_TLS, AUTO_BIND_TLS_BEFORE_BIND, SIMPLE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException

logger = logging.getLogger(__name__)

APP_ORTAMI = os.getenv("APP_ENV", "development")

LDAP_SUNUCU = os.getenv("LDAP_SUNUCU", "192.168.56.10")
_LDAP_PORT_HAM = os.getenv("LDAP_PORT", "")
LDAP_PORT = int(_LDAP_PORT_HAM) if _LDAP_PORT_HAM.strip() else None
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN", "sirket.local")
LDAP_ARAMA_TABANI = os.getenv("LDAP_ARAMA_TABANI", "DC=sirket,DC=local")
# kapali: sadece gelistirme. starttls: LDAP baglantisi acilir, sonra TLS'e
# yukseltilir (RFC 2830). ldaps: baslangictan itibaren TLS/SSL soket.
LDAP_TLS_MODU = os.getenv("LDAP_TLS_MODU", "starttls")
LDAP_CA_SERTIFIKA_DOSYASI = os.getenv("LDAP_CA_SERTIFIKA_DOSYASI") or None

if APP_ORTAMI == "production" and LDAP_TLS_MODU == "kapali":
    raise RuntimeError(
        "Uretim ortaminda (APP_ENV=production) LDAP_TLS_MODU=kapali kullanilamaz. "
        "LDAP_TLS_MODU'nu 'ldaps' veya 'starttls' olarak ayarlayin."
    )

# Grup adi -> izin listesi eslemesi. Varsayilan dosya config/yetki_haritasi.json;
# YETKI_HARITASI_DOSYASI ile degistirilebilir (ops/admin, kod degistirmeden
# hangi AD grubunun hangi izne sahip oldugunu yapilandirabilir).
_VARSAYILAN_YETKI_DOSYASI = Path(__file__).resolve().parent.parent / "config" / "yetki_haritasi.json"
YETKI_HARITASI_DOSYASI = Path(os.getenv("YETKI_HARITASI_DOSYASI") or _VARSAYILAN_YETKI_DOSYASI)

IZIN_HESAPLAMA_KULLAN = "hesaplama.kullan"
IZIN_YONETIM_ERISIM = "yonetim.eris"


def _sunucu_olustur() -> Server:
    if LDAP_TLS_MODU == "kapali":
        return Server(LDAP_SUNUCU, port=LDAP_PORT, get_info=ALL)

    tls = Tls(
        validate=ssl.CERT_REQUIRED,
        ca_certs_file=LDAP_CA_SERTIFIKA_DOSYASI,
        version=ssl.PROTOCOL_TLS_CLIENT,
    )
    if LDAP_TLS_MODU == "ldaps":
        return Server(LDAP_SUNUCU, port=LDAP_PORT or 636, use_ssl=True, tls=tls, get_info=ALL)
    if LDAP_TLS_MODU == "starttls":
        return Server(LDAP_SUNUCU, port=LDAP_PORT or 389, use_ssl=False, tls=tls, get_info=ALL)
    raise RuntimeError(f"Gecersiz LDAP_TLS_MODU: {LDAP_TLS_MODU!r}")


def _baglanti_olustur(sunucu: Server, kullanici_principal: str, sifre: str) -> Connection:
    # LDAPS: TLS soket seviyesinde zaten kurulu -> ek adim gerekmez.
    # StartTLS: duz baglanti acilir, bind'dan ONCE start_tls() otomatik cagrilir.
    auto_bind = AUTO_BIND_TLS_BEFORE_BIND if LDAP_TLS_MODU == "starttls" else AUTO_BIND_NO_TLS
    return Connection(
        sunucu,
        user=kullanici_principal,
        password=sifre,
        authentication=SIMPLE,
        auto_bind=auto_bind,
    )


def _grup_adini_cikar(distinguished_name: str) -> str:
    """'CN=Adminler,OU=Gruplar,DC=sirket,DC=local' -> 'Adminler'"""
    ilk_parca = distinguished_name.split(",")[0]
    return ilk_parca.split("=", 1)[1]


def giris_dogrula(kullanici_adi: str, sifre: str) -> dict | None:
    """LDAP'a kullanici adi/sifre ile bind olmayi dener. Basarili olursa
    kullanici bilgilerini (ad, unvan, AD gruplari) dondurur; basarisiz
    olursa (yanlis sifre, sunucuya ulasilamiyor vb.) None doner.

    Donen sozlukte YALNIZCA kimlik/goruntuleme bilgisi bulunur; izinler
    burada hesaplanmaz (bkz. kullanicinin_izinleri) ki yetki_haritasi.json
    degistiginde, kullanici tekrar giris yapmadan yeni izinler gecerli olsun.
    """
    kullanici_principal = f"{kullanici_adi}@{LDAP_DOMAIN}"
    sunucu = _sunucu_olustur()

    try:
        baglanti = _baglanti_olustur(sunucu, kullanici_principal, sifre)
    except LDAPException:
        return None

    try:
        baglanti.search(
            search_base=LDAP_ARAMA_TABANI,
            search_filter=f"(userPrincipalName={kullanici_principal})",
            attributes=["cn", "title", "memberOf"],
        )
        if not baglanti.entries:
            return None

        kayit = baglanti.entries[0]
        gruplar = [_grup_adini_cikar(dn) for dn in kayit.memberOf.values]

        return {
            "kullanici_adi": kullanici_adi,
            "ad_soyad": kayit.cn.value,
            "unvan": kayit.title.value if kayit.title.value else "",
            "gruplar": gruplar,
        }
    finally:
        baglanti.unbind()


def yetki_haritasini_yukle() -> dict[str, list[str]]:
    """Grup -> izin listesi eslemesini dosyadan okur. Kucuk bir dosya oldugu
    icin her cagrida yeniden okunur; bu sayede dosya degisikligi, uygulama
    yeniden baslatilmadan bir sonraki istekte etkin olur."""
    try:
        with open(YETKI_HARITASI_DOSYASI, encoding="utf-8") as dosya:
            veri = json.load(dosya)
    except (OSError, json.JSONDecodeError) as hata:
        logger.error("Yetki haritasi yuklenemedi (%s): %s", YETKI_HARITASI_DOSYASI, hata)
        return {}

    return {
        grup: list(izinler)
        for grup, izinler in veri.items()
        if not grup.startswith("_") and isinstance(izinler, list)
    }


def kullanicinin_izinleri(kullanici: dict | None) -> set[str]:
    if kullanici is None:
        return set()
    harita = yetki_haritasini_yukle()
    izinler: set[str] = set()
    for grup in kullanici.get("gruplar", []):
        izinler.update(harita.get(grup, []))
    return izinler


def kullanici_izinli_mi(kullanici: dict | None, izin: str) -> bool:
    return izin in kullanicinin_izinleri(kullanici)


class GirisGerekli(Exception):
    """Oturum acilmamis bir istek, korumali bir sayfaya erismeye calisti.
    app/main.py'deki exception handler bunu yakalayip /giris'e yonlendirir."""


def aktif_kullanici(request: Request) -> dict:
    """FastAPI dependency: oturumdaki kullaniciyi dondurur, oturum yoksa
    GirisGerekli firlatir."""
    kullanici = request.session.get("kullanici")
    if kullanici is None:
        raise GirisGerekli()
    return kullanici


def yetki_gerekli(izin: str):
    """FastAPI dependency factory: verilen izne sahip olmayan kullanicilar
    icin 403 dondurur. Sayfa route'lari kadar, htmx parca uclari ve disa
    aktarim uc noktasi da bu bagimlilikla korunur -- boylece arayuzde
    gizlenen bir islem, uc noktaya dogrudan istek atarak atlatilamaz."""

    def _bagimlilik(kullanici: dict = Depends(aktif_kullanici)) -> dict:
        if not kullanici_izinli_mi(kullanici, izin):
            raise HTTPException(status_code=403, detail="Bu islem icin yetkiniz yok.")
        return kullanici

    return _bagimlilik
