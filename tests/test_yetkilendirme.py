# tests/test_yetkilendirme.py — AFH-* gruplari
import json

from ldap3.core.exceptions import LDAPBindError

from app.yetkilendirme import (
    _grup_adini_cikar,
    giris_dogrula,
    kullanici_izinli_mi,
    kullanicinin_izinleri,
    yetki_haritasini_yukle,
)


def test_grup_adini_cikar_dn_den_ismi_ayirir():
    dn = "CN=AFH-Adminler,OU=Gruplar,DC=sirket,DC=local"
    assert _grup_adini_cikar(dn) == "AFH-Adminler"


class _SahteOznitelik:
    def __init__(self, deger):
        self.value = deger
        self.values = deger if isinstance(deger, list) else [deger]


class _SahteKayit:
    def __init__(self, cn, title, memberof, manager=None):
        self.cn = _SahteOznitelik(cn)
        self.title = _SahteOznitelik(title)
        self.memberOf = _SahteOznitelik(memberof)
        self.manager = _SahteOznitelik(manager) if manager else None
        self.displayName = _SahteOznitelik(cn)
        self.entry_attributes_as_dict = {
            "cn": cn,
            "title": title,
            "memberOf": memberof,
            "manager": manager,
        }


class _SahteBaglanti:
    def __init__(self, sunucu, user, password, authentication, auto_bind, **kwargs):
        if password != "dogru-sifre":
            raise LDAPBindError("gecersiz kimlik bilgileri")
        self.bound = True
        self.entries = []
        self._arama = 0

    def search(self, search_base, search_filter, attributes, **kwargs):
        self._arama += 1
        if self._arama == 1:
            self.entries = [
                _SahteKayit(
                    cn="Asli Demirtas",
                    title="Sistem Yoneticisi",
                    memberof=[
                        "CN=AFH-Adminler,OU=Gruplar,DC=sirket,DC=local",
                        "CN=SistemYoneticileri,OU=Gruplar,DC=sirket,DC=local",
                    ],
                )
            ]
        else:
            self.entries = []

    def unbind(self):
        pass


def test_giris_dogrula_dogru_sifreyle_kullanici_bilgisi_doner(monkeypatch):
    monkeypatch.setattr("app.yetkilendirme.Connection", _SahteBaglanti)

    sonuc = giris_dogrula("asli.demirtas", "dogru-sifre")

    assert sonuc is not None
    assert sonuc["ad_soyad"] == "Asli Demirtas"
    assert "AFH-Adminler" in sonuc["gruplar"]
    assert "sifre" not in sonuc and "password" not in sonuc


def test_giris_dogrula_yanlis_sifrede_none_doner(monkeypatch):
    monkeypatch.setattr("app.yetkilendirme.Connection", _SahteBaglanti)

    sonuc = giris_dogrula("asli.demirtas", "yanlis-sifre")

    assert sonuc is None


def test_yetki_haritasi_varsayilan_dosyadan_yuklenir():
    harita = yetki_haritasini_yukle()
    assert "hesaplama.kullan" in harita.get("AFH-Calisanlar", [])
    assert "audit.gor" in harita.get("AFH-Adminler", [])
    assert "onay.islem" in harita.get("AFH-Yoneticiler", [])


def test_yetki_haritasi_yapilandirilabilir_dosyadan_okunur(tmp_path, monkeypatch):
    ozel_dosya = tmp_path / "ozel_yetki.json"
    ozel_dosya.write_text(json.dumps({"BaskaGrup": ["ozel.izin"]}))
    monkeypatch.setattr("app.yetkilendirme.YETKI_HARITASI_DOSYASI", ozel_dosya)

    harita = yetki_haritasini_yukle()

    assert harita == {"BaskaGrup": ["ozel.izin"]}


def test_kullanicinin_izinleri_birden_fazla_gruptan_birlesir():
    kullanici = {"gruplar": ["AFH-Calisanlar", "AFH-Adminler"]}
    izinler = kullanicinin_izinleri(kullanici)
    assert "hesaplama.kullan" in izinler
    assert "audit.gor" in izinler


def test_gruba_uye_olmayan_kullanicinin_izni_yoktur():
    kullanici = {"gruplar": ["TanimsizGrup"]}
    assert kullanici_izinli_mi(kullanici, "hesaplama.kullan") is False


def test_oturumsuz_kullanicinin_izni_yoktur():
    assert kullanici_izinli_mi(None, "hesaplama.kullan") is False
