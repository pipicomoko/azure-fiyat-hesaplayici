from app.sayfalama import sayfa_numarasi, sayfala
from app.yetkilendirme import _sunucu_olustur, ldap_sunucu_hostlari
from ldap3 import Server, ServerPool


def test_sayfala_bos_liste():
    dilim, meta = sayfala([], sayfa=3)
    assert dilim == []
    assert meta["sayfa"] == 1
    assert meta["toplam_sayfa"] == 1
    assert meta["onceki_sayfa"] is None
    assert meta["sonraki_sayfa"] is None


def test_sayfala_son_sayfa_ve_gecersiz():
    kayitlar = list(range(25))
    dilim, meta = sayfala(kayitlar, sayfa=2, sayfa_boyutu=20)
    assert dilim == list(range(20, 25))
    assert meta["toplam_sayfa"] == 2
    assert meta["sonraki_sayfa"] is None
    assert meta["onceki_sayfa"] == 1

    _, tasma = sayfala(kayitlar, sayfa=99, sayfa_boyutu=20)
    assert tasma["sayfa"] == 2
    assert sayfa_numarasi("degil") == 1
    assert sayfa_numarasi(0) == 1


def test_ldap_sunucu_hostlari_virgulle():
    assert ldap_sunucu_hostlari("dc01.sirket.local, dc02.sirket.local") == [
        "dc01.sirket.local",
        "dc02.sirket.local",
    ]
    assert ldap_sunucu_hostlari("tek.ornek") == ["tek.ornek"]
    assert ldap_sunucu_hostlari("  ,  ") == []


def test_sunucu_olustur_birden_fazla_dc_pool(monkeypatch):
    import app.yetkilendirme as y

    monkeypatch.setattr(y, "LDAP_SUNUCU", "dc01.sirket.local,dc02.sirket.local")
    monkeypatch.setattr(y, "LDAP_TLS_MODU", "kapali")
    sunucu = _sunucu_olustur()
    assert isinstance(sunucu, ServerPool)


def test_sunucu_olustur_tek_host_server(monkeypatch):
    import app.yetkilendirme as y

    monkeypatch.setattr(y, "LDAP_SUNUCU", "dc01.sirket.local")
    monkeypatch.setattr(y, "LDAP_TLS_MODU", "kapali")
    sunucu = _sunucu_olustur()
    assert isinstance(sunucu, Server)
