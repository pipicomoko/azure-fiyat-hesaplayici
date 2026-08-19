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

import ipaddress
import json
import logging
import os
import re
import ssl
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from ldap3 import AUTO_BIND_TLS_BEFORE_BIND, NONE, SIMPLE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException, LDAPStartTLSError
from ldap3.utils.conv import escape_filter_chars

logger = logging.getLogger(__name__)

APP_ORTAMI = os.getenv("APP_ENV", "development")

LDAP_SUNUCU = os.getenv("LDAP_SUNUCU", "192.168.56.10")
_LDAP_PORT_HAM = os.getenv("LDAP_PORT", "")
LDAP_PORT = int(_LDAP_PORT_HAM) if _LDAP_PORT_HAM.strip() else None
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN", "sirket.local")
LDAP_ARAMA_TABANI = os.getenv("LDAP_ARAMA_TABANI", "DC=sirket,DC=local")
# kapali: sadece gelistirme. starttls: LDAP baglantisi acilir, sonra TLS'e
# yukseltilir (RFC 2830). ldaps: baslangictan itibaren TLS/SSL soket.
LDAP_TLS_MODU = os.getenv("LDAP_TLS_MODU", "ldaps")
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
_VARSAYILAN_DEPARTMAN_DOSYASI = Path(__file__).resolve().parent.parent / "config" / "departman_haritasi.json"
DEPARTMAN_HARITASI_DOSYASI = Path(os.getenv("DEPARTMAN_HARITASI_DOSYASI") or _VARSAYILAN_DEPARTMAN_DOSYASI)

IZIN_HESAPLAMA_KULLAN = "hesaplama.kullan"
IZIN_YONETICI_ERISIM = "gecmis.yonetici_gor"
IZIN_GECMIS_DEPARTMAN = "gecmis.departman_gor"


class LdapTlsHatasi(Exception):
    """AD DC TLS el sikismasi kurulamadi. Yanlis sifre degildir."""


def _ip_adresi_mi(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _ca_dosyasi() -> str | None:
    ham = (os.getenv("LDAP_CA_SERTIFIKA_DOSYASI") or "").strip()
    adaylar: list[Path] = []
    if ham:
        yol = Path(ham)
        if not yol.is_absolute():
            yol = Path(__file__).resolve().parent.parent / ham
        adaylar.append(yol)
    adaylar.append(Path(__file__).resolve().parent.parent / "config" / "ad-ca.pem")
    for yol in adaylar:
        if yol.is_file() and yol.stat().st_size > 0:
            return str(yol)
    return None


def _tls_hatasi_mi(hata: BaseException) -> bool:
    if isinstance(hata, (LDAPStartTLSError, ssl.SSLError, TimeoutError)):
        return True
    mesaj = str(hata).lower()
    return any(parca in mesaj for parca in ("ssl", "tls", "starttls", "certificate"))


def _tls_ayarlari() -> Tls:
    ca = _ca_dosyasi()
    ayar: dict = {
        "validate": ssl.CERT_REQUIRED if ca else ssl.CERT_NONE,
        "version": ssl.PROTOCOL_TLS_CLIENT,
    }
    if ca:
        ayar["ca_certs_file"] = ca
    if not _ip_adresi_mi(LDAP_SUNUCU):
        ayar["valid_names"] = [LDAP_SUNUCU, LDAP_DOMAIN]
    elif ca is None:
        logger.warning("LDAP TLS: CA dosyasi yok, sunucu sertifikasi dogrulanmiyor")
    return Tls(**ayar)


def _sunucu_olustur() -> Server:
    # get_info=NONE: her giriste AD sema/DSE sorgusu acilmasin. Bu sorgu
    # hem yavas hem de eszamanli girislerde DC uzerinde baglanti tuketir.
    ortak = {"connect_timeout": 8, "get_info": NONE}
    if LDAP_TLS_MODU == "kapali":
        return Server(LDAP_SUNUCU, port=LDAP_PORT or 389, **ortak)

    tls = _tls_ayarlari()
    if LDAP_TLS_MODU == "ldaps":
        return Server(LDAP_SUNUCU, port=LDAP_PORT or 636, use_ssl=True, tls=tls, **ortak)
    if LDAP_TLS_MODU == "starttls":
        return Server(LDAP_SUNUCU, port=LDAP_PORT or 389, use_ssl=False, tls=tls, **ortak)
    raise RuntimeError(f"Gecersiz LDAP_TLS_MODU: {LDAP_TLS_MODU!r}")


def _baglanti_olustur(sunucu: Server, kullanici_principal: str, sifre: str) -> Connection:
    # LDAPS: TLS soket seviyesinde zaten kurulu -> ek adim gerekmez.
    # StartTLS: duz baglanti acilir, bind'dan ONCE start_tls() otomatik cagrilir.
    auto_bind = AUTO_BIND_TLS_BEFORE_BIND if LDAP_TLS_MODU == "starttls" else True
    return Connection(
        sunucu,
        user=kullanici_principal,
        password=sifre,
        authentication=SIMPLE,
        auto_bind=auto_bind,
        raise_exceptions=True,
        receive_timeout=10,
        auto_referrals=False,
    )


def _bind_kimlikleri(kullanici_adi: str) -> list[str]:
    """AD, ayni hesabi UPN veya sAMAccountName ile kabul edebilir."""
    kimlikler = [f"{kullanici_adi}@{LDAP_DOMAIN}", kullanici_adi]
    netbios = LDAP_DOMAIN.split(".", 1)[0].upper()
    if netbios:
        kimlikler.append(f"{netbios}\\{kullanici_adi}")
    # Ayni degeri tekrar denememek icin sirayi koru.
    gorulen: list[str] = []
    for kimlik in kimlikler:
        if kimlik not in gorulen:
            gorulen.append(kimlik)
    return gorulen


def _grup_adini_cikar(distinguished_name: str) -> str:
    """'CN=Adminler,OU=Gruplar,DC=sirket,DC=local' -> 'Adminler'"""
    ilk_parca = distinguished_name.split(",")[0]
    return ilk_parca.split("=", 1)[1]


def _departman_anahtari_etiketten_turetilir(deger: str | None) -> str | None:
    """OU, unvan veya grup adi gibi degerlerden departman anahtari uretir."""
    if not deger:
        return None
    norm = deger.strip().lower()
    norm_sikistir = re.sub(r"\s+", "", norm)

    bilinen: dict[str, str] = {
        "finans": "finans",
        "finansanalisti": "finans",
        "finansmuduru": "finans",
        "financial": "finans",
        "ik": "ik",
        "ikmuduru": "ik",
        "ikuzmani": "ik",
        "insankaynaklari": "ik",
        "humanresources": "ik",
        "hr": "ik",
        "it": "it",
        "itmuduru": "it",
        "sistemyoneticisi": "it",
        "bilgiislem": "it",
        "informationtechnology": "it",
        "muhasebe": "muhasebe",
        "muhasebemuduru": "muhasebe",
        "muhasebeuzmani": "muhasebe",
        "accounting": "muhasebe",
        # departman disi genel roller
        "yonetici": "diger",
        "genelmudur": "diger",
        "generalmanager": "diger",
    }
    if norm_sikistir in bilinen:
        return bilinen[norm_sikistir]
    # Unvan içinde departman kelimesi geçiyorsa (örn. "IK Muduru", "IT Muduru")
    for anahtar, deger_dep in [("finans", "finans"), ("ik", "ik"), ("it", "it"), ("muhasebe", "muhasebe")]:
        if re.search(r"\b" + anahtar + r"\b", norm):
            return deger_dep
    return None


def _kayittan_kullanici(kayit, kullanici_adi: str) -> dict:
    oznitelikler = kayit.entry_attributes_as_dict
    grup_dns = oznitelikler.get("memberOf") or []
    if isinstance(grup_dns, str):
        grup_dns = [grup_dns]
    gruplar = [_grup_adini_cikar(str(dn)) for dn in grup_dns if dn]
    ad_soyad = kayit.cn.value if getattr(kayit, "cn", None) and kayit.cn.value else kullanici_adi
    unvan = kayit.title.value if getattr(kayit, "title", None) and kayit.title.value else ""
    dn = getattr(kayit, "entry_dn", "") or ""
    departman: str | None = None
    if dn:
        for parc in str(dn).split(","):
            if parc.upper().startswith("OU="):
                ou_adi = parc.split("=", 1)[1].strip()
                aday = _departman_anahtari_etiketten_turetilir(ou_adi)
                if aday is not None and aday != "diger":
                    departman = aday
                    break
    if not departman and unvan:
        departman = _departman_anahtari_etiketten_turetilir(unvan)
    return {
        "kullanici_adi": kullanici_adi,
        "ad_soyad": ad_soyad,
        "unvan": unvan,
        "gruplar": gruplar,
        "departman": departman,
    }


def _yanittan_kullanici(yanit: list | None, kullanici_adi: str) -> dict | None:
    """SAFE_SYNC/SYNC arama cevabindan kullanici bilgisi cikarir."""
    for madde in yanit or []:
        if not isinstance(madde, dict):
            continue
        if madde.get("type") not in (None, "searchResEntry") and "attributes" not in madde:
            continue
        nitelikler = madde.get("attributes") or {}
        if not nitelikler and not madde.get("dn"):
            continue
        grup_dns = nitelikler.get("memberOf") or []
        if isinstance(grup_dns, str):
            grup_dns = [grup_dns]
        cn = nitelikler.get("cn") or kullanici_adi
        if isinstance(cn, list):
            cn = cn[0] if cn else kullanici_adi
        title = nitelikler.get("title") or ""
        if isinstance(title, list):
            title = title[0] if title else ""
        dn = madde.get("dn") or ""
        departman: str | None = None
        if dn:
            for parc in str(dn).split(","):
                if parc.upper().startswith("OU="):
                    ou_adi = parc.split("=", 1)[1].strip()
                    aday = _departman_anahtari_etiketten_turetilir(ou_adi)
                    if aday is not None and aday != "diger":
                        departman = aday
                        break
        if not departman and title:
            departman = _departman_anahtari_etiketten_turetilir(str(title))
        return {
            "kullanici_adi": kullanici_adi,
            "ad_soyad": cn or kullanici_adi,
            "unvan": title or "",
            "gruplar": [_grup_adini_cikar(str(dn)) for dn in grup_dns if dn],
            "departman": departman,
        }
    return None


def giris_dogrula(kullanici_adi: str, sifre: str) -> dict | None:
    """LDAP'a kullanici adi/sifre ile bind olmayi dener. Basarili olursa
    kullanici bilgilerini (ad, unvan, AD gruplari) dondurur; basarisiz
    olursa (yanlis sifre, sunucuya ulasilamiyor vb.) None doner.

    Donen sozlukte YALNIZCA kimlik/goruntuleme bilgisi bulunur; izinler
    burada hesaplanmaz (bkz. kullanicinin_izinleri) ki yetki_haritasi.json
    degistiginde, kullanici tekrar giris yapmadan yeni izinler gecerli olsun.
    """
    kullanici_adi = (kullanici_adi or "").strip()
    if kullanici_adi.lower().endswith("@" + LDAP_DOMAIN.lower()):
        kullanici_adi = kullanici_adi[: -(len(LDAP_DOMAIN) + 1)]
    if not kullanici_adi or not sifre:
        return None

    sunucu = _sunucu_olustur()
    baglanti = None
    son_hata = None
    for kimlik in _bind_kimlikleri(kullanici_adi):
        try:
            baglanti = _baglanti_olustur(sunucu, kimlik, sifre)
            if baglanti.bound:
                break
            baglanti.unbind()
            baglanti = None
        except LDAPException as hata:
            if _tls_hatasi_mi(hata):
                logger.warning("LDAP TLS baglantisi kurulamadi: %s", type(hata).__name__)
                raise LdapTlsHatasi from hata
            son_hata = type(hata).__name__
            baglanti = None

    if baglanti is None or not baglanti.bound:
        logger.warning("LDAP bind basarisiz: %s", son_hata or "unbound")
        return None

    try:
        guvenli_ad = escape_filter_chars(kullanici_adi)
        guvenli_upn = escape_filter_chars(f"{kullanici_adi}@{LDAP_DOMAIN}")
        arama_sonucu = baglanti.search(
            search_base=LDAP_ARAMA_TABANI,
            search_filter=(
                f"(|(sAMAccountName={guvenli_ad})"
                f"(userPrincipalName={guvenli_upn})"
                f"(userPrincipalName={guvenli_ad}))"
            ),
            search_scope=SUBTREE,
            attributes=["cn", "title", "memberOf", "sAMAccountName"],
        )
        if baglanti.entries:
            return _kayittan_kullanici(baglanti.entries[0], kullanici_adi)

        yanit = arama_sonucu[2] if isinstance(arama_sonucu, tuple) and len(arama_sonucu) >= 3 else None
        kullanici = _yanittan_kullanici(yanit, kullanici_adi)
        if kullanici:
            return kullanici

        logger.warning("LDAP bind oldu ama kullanici kaydi bulunamadi")
        return None
    except LDAPException as hata:
        if _tls_hatasi_mi(hata):
            logger.warning("LDAP TLS arama sirasinda dustu: %s", type(hata).__name__)
            raise LdapTlsHatasi from hata
        logger.warning("LDAP arama basarisiz: %s", type(hata).__name__)
        return None
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


def departman_haritasini_yukle() -> dict:
    """Departman -> AD grup eslemesini dosyadan okur."""
    try:
        with open(DEPARTMAN_HARITASI_DOSYASI, encoding="utf-8") as dosya:
            return json.load(dosya)
    except (OSError, json.JSONDecodeError) as hata:
        logger.error("Departman haritasi yuklenemedi (%s): %s", DEPARTMAN_HARITASI_DOSYASI, hata)
        return {}


def _regex_departman_desenleri(harita: dict) -> dict[str, re.Pattern[str]]:
    desenler: dict[str, re.Pattern[str]] = {}
    for anahtar, desen in (harita.get("regex_departmanlar") or {}).items():
        if isinstance(desen, str):
            desenler[str(anahtar)] = re.compile(desen, re.IGNORECASE)
    return desenler


def departman_etiketi(anahtar: str) -> str:
    harita = departman_haritasini_yukle()
    bilgi = (harita.get("departmanlar") or {}).get(anahtar)
    if isinstance(bilgi, dict) and bilgi.get("etiket"):
        return str(bilgi["etiket"])
    if anahtar == str(harita.get("varsayilan_departman") or "diger"):
        return str(harita.get("varsayilan_etiket") or "Diger")
    return anahtar.upper()


def gruplardan_departman_belirle(gruplar: list[str] | None) -> tuple[str, str]:
    """AD grup listesinden departman anahtari ve goruntuleme etiketi dondurur."""
    gruplar = gruplar or []
    harita = departman_haritasini_yukle()
    departmanlar = harita.get("departmanlar") or {}
    regex_desenleri = _regex_departman_desenleri(harita)
    varsayilan = str(harita.get("varsayilan_departman") or "diger")
    varsayilan_etiket = str(harita.get("varsayilan_etiket") or "Diger")

    for anahtar, bilgi in departmanlar.items():
        if not isinstance(bilgi, dict):
            continue
        tanimli_gruplar = {str(grup) for grup in bilgi.get("gruplar") or []}
        if tanimli_gruplar.intersection(gruplar):
            return str(anahtar), str(bilgi.get("etiket") or anahtar.upper())

    for grup in gruplar:
        for anahtar, desen in regex_desenleri.items():
            if desen.search(grup):
                bilgi = departmanlar.get(anahtar) or {}
                return anahtar, str(bilgi.get("etiket") or anahtar.upper())

    return varsayilan, varsayilan_etiket


def kullanicinin_departmanlari(kullanici: dict | None) -> set[str]:
    if kullanici is None:
        return set()
    departman = kullanici.get("departman")
    if departman:
        return {str(departman)}
    anahtar, _ = gruplardan_departman_belirle(kullanici.get("gruplar"))
    return {anahtar}


def kullanicinin_yonettigi_departmanlar(kullanici: dict | None) -> set[str]:
    """Mudurler yalnizca acikca tanimli departmanlari (IT, HR vb.) yonetir."""
    if kullanici is None:
        return set()
    harita = departman_haritasini_yukle()
    varsayilan = str(harita.get("varsayilan_departman") or "diger")
    return {departman for departman in kullanicinin_departmanlari(kullanici) if departman != varsayilan}


def hesaplama_departmani(olusturan_gruplar: list[str] | None, olusturan_departman: str | None = None) -> str | None:
    if olusturan_departman:
        return olusturan_departman
    if not olusturan_gruplar:
        return None
    anahtar, _ = gruplardan_departman_belirle(olusturan_gruplar)
    return anahtar


def gecmis_erisim_kapsami(kullanici: dict | None) -> str:
    """yonetici: tum kayitlar | departman: kendi + departman | kendi: yalnizca kendi."""
    if kullanici is None:
        return "kendi"
    if kullanici_izinli_mi(kullanici, IZIN_YONETICI_ERISIM):
        return "yonetici"
    if kullanici_izinli_mi(kullanici, IZIN_GECMIS_DEPARTMAN) and kullanicinin_yonettigi_departmanlar(kullanici):
        return "departman"
    return "kendi"


def hesaplamaya_erisebilir_mi(kullanici: dict | None, hesaplama) -> bool:
    """Gecmis kaydina erisim: yonetici tumunu, mudur departmanini, calisan kendininkini."""
    if kullanici is None:
        return False

    kayit_sahibi = (hesaplama.olusturan_kullanici_adi or "").lower()
    oturum_kullanicisi = (kullanici.get("kullanici_adi") or "").lower()
    sahip = kayit_sahibi == oturum_kullanicisi
    if sahip:
        return True

    kapsam = gecmis_erisim_kapsami(kullanici)
    if kapsam == "yonetici":
        return True

    if hesaplama.olusturan_kullanici_adi is None:
        return False

    if kapsam != "departman":
        return False

    kayit_departmani = hesaplama_departmani(hesaplama.olusturan_gruplar, hesaplama.olusturan_departman)
    if kayit_departmani is None:
        return False
    if kayit_departmani not in kullanicinin_yonettigi_departmanlar(kullanici):
        return False

    # Mudur sadece calisanlarin kayitlarini gorebilir; baskalarinin (mudur/yonetici) kayitlarina erisemez.
    # olusturan_gruplar bos veya bilinmiyorsa guvenli tarafa gec: erisimi reddet.
    kayit_sahibi_gruplari = set(hesaplama.olusturan_gruplar or [])
    if not kayit_sahibi_gruplari:
        return False
    harita = yetki_haritasini_yukle()
    yetkili_gruplar = {
        grup
        for grup, izinler in harita.items()
        if not grup.startswith("_") and (
            IZIN_YONETICI_ERISIM in izinler or IZIN_GECMIS_DEPARTMAN in izinler
        )
    }
    if kayit_sahibi_gruplari.intersection(yetkili_gruplar):
        return False
    return True


def hesaplamayi_silebilir_mi(kullanici: dict | None, hesaplama) -> bool:
    """Silme: yalnizca kaydin sahibi silebilir. Hicbir yonetici/admin baskasinin kaydini silemez."""
    if kullanici is None:
        return False
    return (hesaplama.olusturan_kullanici_adi or "").lower() == (kullanici.get("kullanici_adi") or "").lower()


class GirisGerekli(Exception):
    """Oturum acilmamis bir istek, korumali bir sayfaya erismeye calisti.
    app/main.py'deki exception handler bunu yakalayip /giris'e yonlendirir."""


def aktif_kullanici(request: Request) -> dict:
    """FastAPI dependency: oturumdaki kullaniciyi dondurur, oturum yoksa
    GirisGerekli firlatir. Eksik departman bilgisini unvandan tamamlar."""
    kullanici = request.session.get("kullanici")
    if kullanici is None:
        raise GirisGerekli()
    guncellendi = False
    # Kullanıcı adını küçük harfe normalize et (DB'deki kayıtlarla eşleşmesi için)
    if kullanici.get("kullanici_adi") and kullanici["kullanici_adi"] != kullanici["kullanici_adi"].lower():
        kullanici["kullanici_adi"] = kullanici["kullanici_adi"].lower()
        guncellendi = True
    # Departman eksikse unvandan türet
    if not kullanici.get("departman") and kullanici.get("unvan"):
        departman = _departman_anahtari_etiketten_turetilir(kullanici["unvan"])
        if departman and departman != "diger":
            kullanici["departman"] = departman
            guncellendi = True
    if guncellendi:
        request.session["kullanici"] = kullanici
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
