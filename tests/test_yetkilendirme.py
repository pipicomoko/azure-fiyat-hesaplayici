# tests/test_yetkilendirme.py — AFH-* gruplari
import json

from ldap3.core.exceptions import LDAPBindError

from app.yetkilendirme import (
    GORUNEN_DURUM_FILTRE_SIRASI,
    GORUNEN_DURUM_SIRASI,
    _grup_adini_cikar,
    _tls_ayarlari,
    giris_dogrula,
    hesaplamayi_kopyalayabilir_mi,
    kendi_hesaplamasini_isliyor_mu,
    kendi_onay_hedefi_mi,
    kullanici_izinli_mi,
    kullanicinin_izinleri,
    ldap_uretim_guvenlik_dogrula,
    onay_hedefi_zincirde_mi,
    yetki_haritasini_yukle,
)


def test_grup_adini_cikar_dn_den_ismi_ayirir():
    dn = "CN=AFH-Adminler,OU=Gruplar,DC=sirket,DC=local"
    assert _grup_adini_cikar(dn) == "AFH-Adminler"


def test_gorunen_durum_sirasi_bekleyen_onay_red_taslak():
    assert GORUNEN_DURUM_SIRASI == (
        "onay_bekliyor",
        "onaylandi",
        "reddedildi",
        "taslak",
    )
    assert GORUNEN_DURUM_FILTRE_SIRASI == GORUNEN_DURUM_SIRASI + ("iptal_edildi",)


def test_hesaplama_gorunen_durum_reddedileni_taslaktan_ayirir():
    from types import SimpleNamespace

    from app.yetkilendirme import hesaplama_gorunen_durum

    taslak = SimpleNamespace(
        durum="taslak", red_gerekce=None, reddeden_kullanici_adi=None
    )
    gerekceli = SimpleNamespace(
        durum="taslak", red_gerekce="eksik", reddeden_kullanici_adi=None
    )
    reddedenli = SimpleNamespace(
        durum="taslak", red_gerekce=None, reddeden_kullanici_adi="onur.simsek"
    )
    bekleyen = SimpleNamespace(
        durum="onay_bekliyor", red_gerekce=None, reddeden_kullanici_adi=None
    )
    assert hesaplama_gorunen_durum(taslak) == "taslak"
    assert hesaplama_gorunen_durum(gerekceli) == "reddedildi"
    assert hesaplama_gorunen_durum(reddedenli) == "reddedildi"
    assert hesaplama_gorunen_durum(bekleyen) == "onay_bekliyor"


def test_kopya_kaynak_adi_copy_son_ekini_ayirir():
    from app.yetkilendirme import kopya_kaynak_adi

    assert kopya_kaynak_adi("OnurŞimşek RED COPY (2)") == "OnurŞimşek RED"
    assert kopya_kaynak_adi("OnurŞimşek RED COPY") == "OnurŞimşek RED"
    assert kopya_kaynak_adi("OnurŞimşek RED") is None
    assert kopya_kaynak_adi("Foo COPY COPY") == "Foo COPY"


def test_hesaplama_reddeden_fallback_sirasi():
    from types import SimpleNamespace

    from app.yetkilendirme import hesaplama_reddeden_sam, hesaplamalara_reddeden_ata

    alan = SimpleNamespace(
        id=1,
        durum="taslak",
        red_gerekce="x",
        reddeden_kullanici_adi="ali.veli",
        onaylayan_kullanici_adi="eski.kisi",
        ad="A",
        olusturan_kullanici_adi="ayse",
    )
    hesaplamalara_reddeden_ata([alan], aktiviteler=[])
    assert hesaplama_reddeden_sam(alan) == "ali.veli"

    aktivite_kaydi = SimpleNamespace(
        id=2,
        durum="taslak",
        red_gerekce="x",
        reddeden_kullanici_adi=None,
        onaylayan_kullanici_adi="eski.kisi",
        ad="B",
        olusturan_kullanici_adi="ayse",
    )
    aktivite = SimpleNamespace(
        islem="reddedildi",
        hesaplama_id=2,
        aktor_kullanici_adi="onur.simsek",
        olusturulma_tarihi=None,
    )
    hesaplamalara_reddeden_ata([aktivite_kaydi], aktiviteler=[aktivite])
    assert hesaplama_reddeden_sam(aktivite_kaydi) == "onur.simsek"

    onaylayan = SimpleNamespace(
        id=3,
        durum="taslak",
        red_gerekce="x",
        reddeden_kullanici_adi=None,
        onaylayan_kullanici_adi="eski.kisi",
        ad="C",
        olusturan_kullanici_adi="ayse",
    )
    hesaplamalara_reddeden_ata([onaylayan], aktiviteler=[])
    assert hesaplama_reddeden_sam(onaylayan) == "eski.kisi"

    kaynak = SimpleNamespace(
        id=10,
        durum="taslak",
        red_gerekce="x",
        reddeden_kullanici_adi="onur.simsek",
        onaylayan_kullanici_adi=None,
        ad="OnurŞimşek RED",
        olusturan_kullanici_adi="test.kullanici",
    )
    kopya = SimpleNamespace(
        id=11,
        durum="taslak",
        red_gerekce="x",
        reddeden_kullanici_adi=None,
        onaylayan_kullanici_adi=None,
        ad="OnurŞimşek RED COPY (2)",
        olusturan_kullanici_adi="test.kullanici",
    )
    hesaplamalara_reddeden_ata([kopya, kaynak], aktiviteler=[])
    assert hesaplama_reddeden_sam(kopya) == "onur.simsek"


def test_yeni_taslak_red_rozetsiz_kalir():
    from types import SimpleNamespace

    from app.yetkilendirme import (
        hesaplama_gorunen_durum,
        hesaplama_reddeden_sam,
        hesaplamalara_reddeden_ata,
    )

    taslak = SimpleNamespace(
        id=20,
        durum="taslak",
        red_gerekce=None,
        reddeden_kullanici_adi=None,
        onaylayan_kullanici_adi=None,
        ad="OnurŞimşek RED COPY",
        olusturan_kullanici_adi="test.kullanici",
    )
    hesaplamalara_reddeden_ata([taslak], aktiviteler=[])
    assert hesaplama_gorunen_durum(taslak) == "taslak"
    assert hesaplama_reddeden_sam(taslak) == ""


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


def test_kendi_onay_hedefi_mi_self_approve():
    kullanici = {"kullanici_adi": "onur.simsek"}
    assert kendi_onay_hedefi_mi(kullanici, "onur.simsek") is True
    assert kendi_onay_hedefi_mi(kullanici, "Onur.Simsek") is True
    assert kendi_onay_hedefi_mi(kullanici, "emre.turan") is False
    assert kendi_onay_hedefi_mi(kullanici, None) is False


def test_kendi_hesaplamasini_isliyor_mu():
    class _H:
        olusturan_kullanici_adi = "onur.simsek"

    kullanici = {"kullanici_adi": "onur.simsek"}
    assert kendi_hesaplamasini_isliyor_mu(kullanici, _H()) is True
    assert (
        kendi_hesaplamasini_isliyor_mu({"kullanici_adi": "emre.turan"}, _H()) is False
    )


def test_onay_hedefi_zincirde_mi():
    zincir = ["emre.turan", "baris.kocak"]
    assert onay_hedefi_zincirde_mi(zincir, "emre.turan") is True
    assert onay_hedefi_zincirde_mi(zincir, "Emre.Turan") is True
    assert onay_hedefi_zincirde_mi(zincir, "rastgele.kisi") is False
    assert onay_hedefi_zincirde_mi([], "emre.turan") is False
    assert onay_hedefi_zincirde_mi(zincir, None) is False


def test_bug10_uretim_ca_yoksa_reddedilir():
    import pytest

    with pytest.raises(RuntimeError, match="CA|CERT_NONE|sertifika"):
        ldap_uretim_guvenlik_dogrula(ortam="production", tls_modu="ldaps", ca_yolu=None)


def test_bug10_uretim_tls_kapali_reddedilir():
    import pytest

    with pytest.raises(RuntimeError, match="kapali"):
        ldap_uretim_guvenlik_dogrula(
            ortam="production", tls_modu="kapali", ca_yolu="/x.pem"
        )


def test_bug10_gelistirmede_ca_yok_izinli():
    ldap_uretim_guvenlik_dogrula(ortam="development", tls_modu="ldaps", ca_yolu=None)


def test_bug10_tls_ayarlari_uretimde_ca_yoksa_raise(monkeypatch):
    import pytest
    import app.yetkilendirme as y

    monkeypatch.setattr(y, "APP_ORTAMI", "production")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(y, "_ca_dosyasi", lambda: None)
    with pytest.raises(RuntimeError, match="CA|CERT_NONE|sertifika"):
        _tls_ayarlari()


def test_hesaplamayi_kopyalayabilir_mi_durum_ve_izin():
    from types import SimpleNamespace

    sahip = {
        "kullanici_adi": "ayse.yilmaz",
        "gruplar": ["AFH-Calisanlar"],
    }
    admin = {
        "kullanici_adi": "asli.demirtas",
        "gruplar": ["AFH-Adminler"],
        "rol": "admin",
    }

    def _h(durum, red=None, sahip_adi="ayse.yilmaz", reddeden=None):
        return SimpleNamespace(
            olusturan_kullanici_adi=sahip_adi,
            durum=durum,
            red_gerekce=red,
            reddeden_kullanici_adi=reddeden,
            olusturan_manager_zinciri=["onur.simsek"],
        )

    assert hesaplamayi_kopyalayabilir_mi(sahip, _h("taslak")) is True
    assert hesaplamayi_kopyalayabilir_mi(sahip, _h("onay_bekliyor")) is True
    assert hesaplamayi_kopyalayabilir_mi(sahip, _h("taslak", red="eksik")) is True
    assert (
        hesaplamayi_kopyalayabilir_mi(sahip, _h("taslak", reddeden="onur.simsek"))
        is True
    )
    assert hesaplamayi_kopyalayabilir_mi(sahip, _h("onaylandi")) is False
    assert hesaplamayi_kopyalayabilir_mi(sahip, _h("iptal_edildi")) is False
    assert hesaplamayi_kopyalayabilir_mi(admin, _h("onay_bekliyor")) is False
    assert hesaplamayi_kopyalayabilir_mi(None, _h("taslak")) is False


def test_departman_filtre_eslesir_ana_ve_alt():
    from app.yetkilendirme import departman_filtre_eslesir

    assert departman_filtre_eslesir("it", "it") is True
    assert departman_filtre_eslesir("it-yazilim", "it") is True
    assert departman_filtre_eslesir("finans", "it") is False
    assert departman_filtre_eslesir("it-yazilim", "it-yazilim") is True
    assert departman_filtre_eslesir("it", "it-yazilim") is False
    assert departman_filtre_eslesir("it", "") is True


def test_departman_secenek_listesi_haritadan_gelir():
    from app.yetkilendirme import departman_secenek_listesi

    liste = departman_secenek_listesi()
    anahtarlar = {d["anahtar"] for d in liste}
    assert "it" in anahtarlar
    assert "finans" in anahtarlar
    assert "it-yazilim" in anahtarlar
    etiketler = {d["etiket"] for d in liste}
    assert "IT" in etiketler
    assert "Finans" in etiketler
