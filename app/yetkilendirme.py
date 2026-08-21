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
IZIN_DIREKTOR_ERISIM = "gecmis.direktor_gor"
IZIN_ADMIN_ERISIM = "gecmis.admin_gor"
IZIN_ONAY_ISLEM = "onay.islem"
IZIN_RAPOR_GOR = "rapor.gor"
IZIN_AUDIT_GOR = "audit.gor"
# Eski anahtar (geriye donuk); artik kullanilmiyor ama testler import edebilir
IZIN_GECMIS_DEPARTMAN = "gecmis.departman_gor"

GENEL_MUDUR_SAM = os.getenv("GENEL_MUDUR_SAM", "ahmet.yildirim").lower()

ROL_ADMIN = "admin"
ROL_DIREKTOR = "direktor"
ROL_YONETICI = "yonetici"
ROL_CALISAN = "calisan"


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
    """OU, unvan veya grup adi gibi degerlerden departman anahtari uretir.

    Bilinen eslemeler onceliklidir; bilinmeyen bir OU/unvan gelirse deger
    dogrudan normalize edilip anahtar olarak kullanilir — bu sayede AD'ye
    yeni bir OU eklendiginde kod degistirmeden otomatik calisir.
    """
    if not deger:
        return None
    norm = deger.strip().lower()
    norm_sikistir = re.sub(r"\s+", "", norm)

    # Sadece yonetici/genel roller ve bilinen kisaltmalar/esanlamlilar icin
    # sabit esleme; bunlar disindaki her deger kendi normalize halini anahtar yapar.
    bilinen_eslemeler: dict[str, str] = {
        # Finans
        "financial": "finans",
        # IK es anlamlilari
        "insankaynaklari": "ik",
        "humanresources": "ik",
        "hr": "ik",
        # IT es anlamlilari
        "bilgiislem": "it",
        "informationtechnology": "it",
        # Muhasebe es anlamlilari
        "accounting": "muhasebe",
        # Genel yonetici rolleri — departman kodu olarak islenmemeli
        "yonetici": "diger",
        "genelmudur": "diger",
        "generalmanager": "diger",
        "genel mudur": "diger",
    }
    if norm_sikistir in bilinen_eslemeler:
        return bilinen_eslemeler[norm_sikistir]

    # Unvan "X Muduru" / "X Uzmani" seklindeyse kok departmani cikar
    # Ornek: "Finans Muduru" -> "finans", "Lojistik Uzmani" -> "lojistik"
    for sonek in (" muduru", " uzmani", " analisti", " yoneticisi", " direktoru", " sorumlusu"):
        if norm.endswith(sonek):
            kok = norm[: -len(sonek)].strip()
            if kok:
                return re.sub(r"\s+", "", kok)

    # Bilinmeyen deger: dogrudan normalize et (bosluklari kaldir)
    # Ornek: "Lojistik" -> "lojistik", "Satis ve Pazarlama" -> "satisvepaizarlama"
    anahtar = norm_sikistir
    # "diger" ve bos degerler departman sayilmaz
    if not anahtar or anahtar == "diger":
        return None
    return anahtar


def _manager_sam_from_dn(manager_dn: str | None) -> str | None:
    """CN=Ad Soyad,OU=... veya CN=sam.account,... -> sAMAccountName tahmini.
    Prefer CN when it looks like user.principal; else return None and resolve later."""
    if not manager_dn:
        return None
    ilk = str(manager_dn).split(",")[0]
    if "=" not in ilk:
        return None
    cn = ilk.split("=", 1)[1].strip()
    if "." in cn and " " not in cn:
        return cn.lower()
    # Ad Soyad formundaysa seed --use-username-as-cn kullandiysa CN=sam olur;
    # aksi halde manager DN'den sam cozumlemesi aramada yapilir.
    return None


def _kayittan_kullanici(kayit, kullanici_adi: str) -> dict:
    oznitelikler = kayit.entry_attributes_as_dict
    grup_dns = oznitelikler.get("memberOf") or []
    if isinstance(grup_dns, str):
        grup_dns = [grup_dns]
    gruplar = [_grup_adini_cikar(str(dn)) for dn in grup_dns if dn]
    display = None
    if getattr(kayit, "displayName", None) and kayit.displayName.value:
        display = kayit.displayName.value
    ad_soyad = display or (
        kayit.cn.value if getattr(kayit, "cn", None) and kayit.cn.value else kullanici_adi
    )
    unvan = kayit.title.value if getattr(kayit, "title", None) and kayit.title.value else ""
    manager_dn = ""
    if getattr(kayit, "manager", None) and kayit.manager.value:
        manager_dn = str(kayit.manager.value)
    manager_sam = _manager_sam_from_dn(manager_dn)
    if manager_dn and not manager_sam:
        # CN=Ad Soyad — sAMAccountName icin CN'deki bosluklari noktali forma cevirmeye calisma;
        # seed kullanicilari --use-username-as-cn ile olusturulur (CN=sam).
        manager_sam = _grup_adini_cikar(manager_dn).lower().replace(" ", ".")
    dn = getattr(kayit, "entry_dn", "") or ""
    departman: str | None = None
    # DEPT-* gruplarindan once oku
    anahtar, _ = gruplardan_departman_belirle(gruplar)
    if anahtar and anahtar != "diger":
        departman = anahtar
    if not departman and dn:
        # En derin (ilk) anlamli OU — IT alt birimleri once
        ou_parcalar = [
            parc.split("=", 1)[1].strip()
            for parc in str(dn).split(",")
            if parc.upper().startswith("OU=")
        ]
        for ou_adi in ou_parcalar:
            if ou_adi.lower() in {"kullanicilar", "gruplar", "bagimsizhesaplar", "servishesaplari"}:
                continue
            aday = _departman_anahtari_etiketten_turetilir(ou_adi)
            if aday and aday != "diger":
                departman = aday
                break
    if not departman and unvan:
        departman = _departman_anahtari_etiketten_turetilir(unvan)
    return {
        "kullanici_adi": kullanici_adi.lower(),
        "ad_soyad": ad_soyad,
        "unvan": unvan,
        "gruplar": gruplar,
        "departman": departman,
        "manager": (manager_sam or "").lower() or None,
        "manager_dn": manager_dn or None,
        "rol": kullanici_rolu({"gruplar": gruplar}),
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
        display = nitelikler.get("displayName") or cn
        if isinstance(display, list):
            display = display[0] if display else cn
        manager_raw = nitelikler.get("manager") or ""
        if isinstance(manager_raw, list):
            manager_raw = manager_raw[0] if manager_raw else ""
        manager_dn = str(manager_raw) if manager_raw else ""
        manager_sam = _manager_sam_from_dn(manager_dn)
        if manager_dn and not manager_sam:
            manager_sam = _grup_adini_cikar(manager_dn).lower().replace(" ", ".")
        gruplar = [_grup_adini_cikar(str(g)) for g in grup_dns if g]
        if not departman:
            anahtar, _ = gruplardan_departman_belirle(gruplar)
            if anahtar and anahtar != "diger":
                departman = anahtar
        return {
            "kullanici_adi": kullanici_adi.lower(),
            "ad_soyad": display or kullanici_adi,
            "unvan": title or "",
            "gruplar": gruplar,
            "departman": departman,
            "manager": (manager_sam or "").lower() or None,
            "manager_dn": manager_dn or None,
            "rol": kullanici_rolu({"gruplar": gruplar}),
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
            attributes=["cn", "displayName", "title", "memberOf", "sAMAccountName", "manager", "department"],
        )
        if baglanti.entries:
            kullanici = _kayittan_kullanici(baglanti.entries[0], kullanici_adi)
            kullanici["manager_zinciri"], kullanici["manager_adlari"] = _manager_zinciri_yukle(
                baglanti, kullanici.get("manager")
            )
            return kullanici

        yanit = arama_sonucu[2] if isinstance(arama_sonucu, tuple) and len(arama_sonucu) >= 3 else None
        kullanici = _yanittan_kullanici(yanit, kullanici_adi)
        if kullanici:
            kullanici["manager_zinciri"], kullanici["manager_adlari"] = _manager_zinciri_yukle(
                baglanti, kullanici.get("manager")
            )
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


def giris_sonrasi_yol(kullanici: dict | None) -> str:
    """Oturum acildiktan sonra kullanicinin yetkisine uygun ilk sayfa."""
    if kullanici_izinli_mi(kullanici, IZIN_AUDIT_GOR):
        return "/admin/aktivite"
    # Genel mudur / ustu olmayan tahmin kullanicisi: onay/arama/rapor
    if kullanici is not None and ustu_olmayan_mi(kullanici):
        if kullanici_izinli_mi(kullanici, IZIN_ONAY_ISLEM):
            return "/onay-kuyrugu"
        if kullanici_izinli_mi(kullanici, IZIN_ADMIN_ERISIM) or kullanici_izinli_mi(
            kullanici, IZIN_DIREKTOR_ERISIM
        ) or kullanici_izinli_mi(kullanici, IZIN_YONETICI_ERISIM):
            return "/gecmis/arama"
        if kullanici_izinli_mi(kullanici, IZIN_RAPOR_GOR):
            return "/raporlar"
    if kullanici_izinli_mi(kullanici, IZIN_HESAPLAMA_KULLAN):
        return "/"
    if kullanici_izinli_mi(kullanici, IZIN_ADMIN_ERISIM):
        return "/gecmis/arama"
    if kullanici_izinli_mi(kullanici, IZIN_RAPOR_GOR):
        return "/raporlar"
    return "/gecmis/taslaklar"


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


_BILINEN_DEPARTMAN_ETIKETLERI: dict[str, str] = {
    "finans": "Finans",
    "ik": "IK",
    "it": "IT",
    "muhasebe": "Muhasebe",
    "satinalma": "Satın Alma",
    "lojistik": "Lojistik",
    "satis": "Satış",
    "pazarlama": "Pazarlama",
    "hukuk": "Hukuk",
    "yonetici": "Yönetici",
    "diger": "Diğer",
}


def departman_etiketi(anahtar: str) -> str:
    # 1) departman_haritasi.json'dan
    harita = departman_haritasini_yukle()
    bilgi = (harita.get("departmanlar") or {}).get(anahtar)
    if isinstance(bilgi, dict) and bilgi.get("etiket"):
        return str(bilgi["etiket"])
    if anahtar == str(harita.get("varsayilan_departman") or "diger"):
        return str(harita.get("varsayilan_etiket") or "Diğer")
    # 2) bilinen sabit etiket tablosu
    if anahtar in _BILINEN_DEPARTMAN_ETIKETLERI:
        return _BILINEN_DEPARTMAN_ETIKETLERI[anahtar]
    # 3) bilinmeyen: ilk harf büyük
    return anahtar.capitalize()


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


def kullanici_rolu(kullanici: dict | None) -> str:
    """En yuksek yetkiden asagi: admin > direktor > yonetici > calisan."""
    if kullanici is None:
        return ROL_CALISAN
    gruplar = set(kullanici.get("gruplar") or [])
    if "AFH-Adminler" in gruplar:
        return ROL_ADMIN
    if "AFH-Direktorler" in gruplar:
        return ROL_DIREKTOR
    if "AFH-Yoneticiler" in gruplar:
        return ROL_YONETICI
    # Izin haritasindan da turet (eski grup adlari icin)
    if kullanici_izinli_mi(kullanici, IZIN_ADMIN_ERISIM):
        return ROL_ADMIN
    if kullanici_izinli_mi(kullanici, IZIN_DIREKTOR_ERISIM):
        return ROL_DIREKTOR
    if kullanici_izinli_mi(kullanici, IZIN_YONETICI_ERISIM):
        return ROL_YONETICI
    return ROL_CALISAN


def _manager_zinciri_yukle(
    baglanti: Connection, baslangic_manager: str | None, max_derinlik: int = 12
) -> tuple[list[str], dict[str, str]]:
    """Manager zincirini ve her sam icin gorunen adi (displayName) dondurur."""
    zincir: list[str] = []
    adlar: dict[str, str] = {}
    guncel = (baslangic_manager or "").lower().strip()
    gorulen: set[str] = set()
    while guncel and guncel not in gorulen and len(zincir) < max_derinlik:
        gorulen.add(guncel)
        zincir.append(guncel)
        guvenli = escape_filter_chars(guncel)
        try:
            baglanti.search(
                search_base=LDAP_ARAMA_TABANI,
                search_filter=f"(sAMAccountName={guvenli})",
                search_scope=SUBTREE,
                attributes=["manager", "sAMAccountName", "displayName", "cn"],
            )
        except LDAPException:
            adlar[guncel] = sam_gorunen_adi(guncel)
            break
        if not baglanti.entries:
            adlar[guncel] = sam_gorunen_adi(guncel)
            break
        kayit = baglanti.entries[0]
        display = None
        if getattr(kayit, "displayName", None) and kayit.displayName.value:
            display = str(kayit.displayName.value)
        elif getattr(kayit, "cn", None) and kayit.cn.value:
            cn = str(kayit.cn.value)
            if " " in cn:
                display = cn
        adlar[guncel] = display or sam_gorunen_adi(guncel)
        manager_dn = ""
        if getattr(kayit, "manager", None) and kayit.manager.value:
            manager_dn = str(kayit.manager.value)
        guncel = (_manager_sam_from_dn(manager_dn) or "").lower()
        if manager_dn and not guncel:
            guncel = _grup_adini_cikar(manager_dn).lower().replace(" ", ".")
    return zincir, adlar


def sam_gorunen_adi(sam: str | None, kayitli: str | None = None) -> str:
    """sAMAccountName veya kayitli ad-soyadi gorunen metne cevirir."""
    if (kayitli or "").strip():
        return kayitli.strip()
    ham = (sam or "").strip()
    if not ham:
        return ""
    if " " in ham and "." not in ham.split()[0]:
        return ham
    parcalar = [p for p in ham.replace("_", ".").split(".") if p]
    return " ".join(p[:1].upper() + p[1:].lower() for p in parcalar)


def oturum_manager_zincirini_genislet(kullanici: dict) -> list[str]:
    """Oturumdaki dogrudan manager + bilinen ust zincir (session'da biriktirilir)."""
    zincir = [str(z).lower() for z in (kullanici.get("manager_zinciri") or []) if z]
    dogrudan = (kullanici.get("manager") or "").lower()
    if dogrudan and dogrudan not in zincir:
        zincir.insert(0, dogrudan)
    return zincir


def ustu_olmayan_mi(kullanici: dict | None) -> bool:
    """Hiyerarside ustu olmayan tahmin kullanicisi (or. Genel Mudur).

    Admin gibi bagimsiz hesaplar (hesaplama.kullan yok) bu kurala girmez.
    """
    if kullanici is None:
        return False
    if not kullanici_izinli_mi(kullanici, IZIN_HESAPLAMA_KULLAN):
        return False
    sam = (kullanici.get("kullanici_adi") or "").lower()
    if sam and sam == GENEL_MUDUR_SAM:
        return True
    return not oturum_manager_zincirini_genislet(kullanici)


# Geriye donuk alias
kendinden_onaylayabilir_mi = ustu_olmayan_mi


def oturum_manager_adi(kullanici: dict | None, sam: str | None) -> str:
    """Oturumdaki manager_adlari haritasindan veya sam'dan gorunen ad."""
    anahtar = (sam or "").lower().strip()
    if not anahtar:
        return ""
    adlar = (kullanici or {}).get("manager_adlari") or {}
    return sam_gorunen_adi(anahtar, adlar.get(anahtar))


def departman_basi_mi(kullanici: dict | None) -> bool:
    """Manager zincirinde dogrudan Genel Mudur'e bagli kisi (spesifikasyon 1.7)."""
    if kullanici is None:
        return False
    return (kullanici.get("manager") or "").lower() == GENEL_MUDUR_SAM


def gecmis_erisim_kapsami(kullanici: dict | None) -> str:
    """admin | direktor | yonetici | kendi"""
    if kullanici is None:
        return "kendi"
    rol = kullanici.get("rol") or kullanici_rolu(kullanici)
    if rol == ROL_ADMIN or kullanici_izinli_mi(kullanici, IZIN_ADMIN_ERISIM):
        return "admin"
    if rol == ROL_DIREKTOR or kullanici_izinli_mi(kullanici, IZIN_DIREKTOR_ERISIM):
        return "direktor"
    if rol == ROL_YONETICI or kullanici_izinli_mi(kullanici, IZIN_YONETICI_ERISIM):
        return "yonetici"
    return "kendi"


def hesaplamaya_erisebilir_mi(kullanici: dict | None, hesaplama) -> bool:
    """Gorunurluk: sahip her zaman; admin surecte olanlari; yonetici/direktor manager zinciri."""
    from app.models import DURUM_TASLAK

    if kullanici is None:
        return False

    kayit_sahibi = (hesaplama.olusturan_kullanici_adi or "").lower()
    oturum = (kullanici.get("kullanici_adi") or "").lower()
    if kayit_sahibi == oturum:
        return True

    kapsam = gecmis_erisim_kapsami(kullanici)
    durum = getattr(hesaplama, "durum", None) or DURUM_TASLAK

    if kapsam == "admin":
        # Admin taslaklari gormez (kararlar.md)
        return durum != DURUM_TASLAK

    if kapsam in ("yonetici", "direktor"):
        # Onaylanmis / iptal / onay bekleyen — taslak degil (altindaki kisilerin)
        if durum == DURUM_TASLAK:
            return False
        zincir = [z.lower() for z in (getattr(hesaplama, "olusturan_manager_zinciri", None) or [])]
        # Kayit sahibi manager zincirinde oturum kullanicisi var mi?
        if oturum in zincir:
            return True
        # Alternatif: olusturan'in manager'i dogrudan bu kullanici (snapshot yoksa)
        return False

    return False


def hesaplama_gorunen_durum(hesaplama) -> str:
    """UI durumu: reddedilmis taslaklar 'reddedildi' olarak gosterilir."""
    from app.models import DURUM_TASLAK

    durum = getattr(hesaplama, "durum", None) or DURUM_TASLAK
    if durum == DURUM_TASLAK and getattr(hesaplama, "red_gerekce", None):
        return "reddedildi"
    return durum


def hesaplamayi_duzenleyebilir_mi(kullanici: dict | None, hesaplama) -> bool:
    """Sahibi, taslak (veya reddedilip taslaga donmus) kaydi duzenleyebilir."""
    from app.models import DURUM_TASLAK

    if kullanici is None:
        return False
    if (hesaplama.olusturan_kullanici_adi or "").lower() != (kullanici.get("kullanici_adi") or "").lower():
        return False
    return (getattr(hesaplama, "durum", DURUM_TASLAK) or DURUM_TASLAK) == DURUM_TASLAK


def hesaplamayi_silebilir_mi(kullanici: dict | None, hesaplama) -> bool:
    """Silme: yalnizca sahibi ve yalnizca taslak/reddedilmis (taslak) kayitlar."""
    return hesaplamayi_duzenleyebilir_mi(kullanici, hesaplama)


def hesaplamayi_iptal_edebilir_mi(kullanici: dict | None, hesaplama) -> bool:
    """Sadece kaydin departman basi onaylanmis kaydi iptal edebilir."""
    from app.models import DURUM_ONAYLANDI

    if kullanici is None or not departman_basi_mi(kullanici):
        return False
    if getattr(hesaplama, "durum", None) != DURUM_ONAYLANDI:
        return False
    # Ayni departman
    kayit_dep = hesaplama_departmani(
        getattr(hesaplama, "olusturan_gruplar", None),
        getattr(hesaplama, "olusturan_departman", None),
    )
    return bool(kayit_dep) and kayit_dep in kullanicinin_departmanlari(kullanici)


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
    if kullanici.get("kullanici_adi") and kullanici["kullanici_adi"] != kullanici["kullanici_adi"].lower():
        kullanici["kullanici_adi"] = kullanici["kullanici_adi"].lower()
        guncellendi = True
    mevcut_dep = kullanici.get("departman")
    if (not mevcut_dep or mevcut_dep == "diger") and kullanici.get("unvan"):
        departman = _departman_anahtari_etiketten_turetilir(kullanici["unvan"])
        if departman and departman != "diger":
            kullanici["departman"] = departman
            guncellendi = True
    rol = kullanici_rolu(kullanici)
    if kullanici.get("rol") != rol:
        kullanici["rol"] = rol
        guncellendi = True
    if not kullanici.get("manager_zinciri"):
        kullanici["manager_zinciri"] = oturum_manager_zincirini_genislet(kullanici)
        guncellendi = True
    else:
        # Manager alani sonradan geldiyse zinciri tamamla
        birlesik = oturum_manager_zincirini_genislet(kullanici)
        if birlesik != list(kullanici.get("manager_zinciri") or []):
            kullanici["manager_zinciri"] = birlesik
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


def gecmis_goruntule_gerekli(kullanici: dict = Depends(aktif_kullanici)) -> dict:
    """Hesaplama kullanicisi veya admin (salt okunur gecmis) erisebilir."""
    if kullanici_izinli_mi(kullanici, IZIN_HESAPLAMA_KULLAN) or kullanici_izinli_mi(
        kullanici, IZIN_ADMIN_ERISIM
    ):
        return kullanici
    raise HTTPException(status_code=403, detail="Bu islem icin yetkiniz yok.")
