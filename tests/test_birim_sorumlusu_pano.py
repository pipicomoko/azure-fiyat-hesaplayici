from datetime import datetime, timezone

import pytest
from sqlmodel import Session

from app.main import app
from app.models import DURUM_ONAY_BEKLIYOR, DURUM_ONAYLANDI, Hesaplama
from app.yetkilendirme import aktif_kullanici


BIRIM_SORUMLULARI = [
    ("baris.kocak", "Baris Kocak", "it", "serkan.aydemir"),
    ("sibel.arslan", "Sibel Arslan", "finans", "murat.ozturk"),
    ("tolga.yavuz", "Tolga Yavuz", "muhasebe", "hande.aksoy"),
    ("ugur.bayrak", "Ugur Bayrak", "ik", "zehra.kaplan"),
    ("derya.celik", "Derya Celik", "lojistik", "cem.aktas"),
]


def _kullanici(sam: str, ad: str, departman: str, manager: str) -> dict:
    return {
        "kullanici_adi": sam,
        "ad_soyad": ad,
        "unvan": f"{departman} Yoneticisi",
        "departman": departman,
        "gruplar": ["AFH-Calisanlar", "AFH-Yoneticiler"],
        "manager": manager,
        "manager_zinciri": [manager, "ahmet.yildirim"],
        "rol": "yonetici",
    }


def _kayit(ad: str, durum: str, departman: str, zincir: list[str]) -> Hesaplama:
    simdi = datetime.now(timezone.utc)
    return Hesaplama(
        ad=ad,
        durum=durum,
        toplam_aylik_maliyet=420,
        para_birimi="USD",
        olusturulma_tarihi=simdi,
        onay_tarihi=simdi if durum == DURUM_ONAYLANDI else None,
        olusturan_kullanici_adi="uzman.kullanici",
        olusturan_ad_soyad="Uzman Kullanici",
        olusturan_departman=departman,
        olusturan_manager_zinciri=zincir,
    )


@pytest.mark.parametrize("sam,ad,departman,manager", BIRIM_SORUMLULARI)
def test_bes_birim_sorumlusu_ortak_paneli_gorur(
    client, veritabani, sam, ad, departman, manager
):
    app.dependency_overrides[aktif_kullanici] = lambda: _kullanici(
        sam, ad, departman, manager
    )

    yanit = client.get("/")

    assert yanit.status_code == 200
    assert "Birim Yönetim Özeti" in yanit.text
    assert "Birim Yönetimi" in yanit.text
    assert "Birim Kayıtları" in yanit.text


def test_birim_sorumlusu_yalnizca_kendi_alt_agacini_gorur(client, veritabani):
    sibel = _kullanici("sibel.arslan", "Sibel Arslan", "finans", "murat.ozturk")
    app.dependency_overrides[aktif_kullanici] = lambda: sibel
    with Session(veritabani) as oturum:
        oturum.add(
            _kayit(
                "Sibel Ekibi",
                DURUM_ONAYLANDI,
                "finans",
                ["caner.bulut", "sibel.arslan", "murat.ozturk", "ahmet.yildirim"],
            )
        )
        oturum.add(
            _kayit(
                "Murat Diger Kayit",
                DURUM_ONAYLANDI,
                "finans",
                ["murat.ozturk", "ahmet.yildirim"],
            )
        )
        bekleyen = _kayit(
            "Sibel Onayi",
            DURUM_ONAY_BEKLIYOR,
            "finans",
            ["sibel.arslan", "murat.ozturk", "ahmet.yildirim"],
        )
        bekleyen.onay_hedefi = "sibel.arslan"
        oturum.add(bekleyen)
        oturum.commit()

    yanit = client.get("/")

    assert "Sibel Ekibi" in yanit.text
    assert "Sibel Onayi" in yanit.text
    assert "Murat Diger Kayit" not in yanit.text


def test_birim_sorumlusu_pano_durum_kart_sirasi(client, veritabani):
    """Birim sorumlusu ozet kartlari: bekleyen → onaylandı → reddedildi → taslak (aktif calisan sonda)."""
    import re

    sibel = _kullanici("sibel.arslan", "Sibel Arslan", "finans", "murat.ozturk")
    app.dependency_overrides[aktif_kullanici] = lambda: sibel
    yanit = client.get("/")
    assert yanit.status_code == 200
    etiketler = re.findall(r'executive-kpi__label">([^<]+)', yanit.text)
    assert etiketler == [
        "Bekleyen potansiyel maliyet",
        "Birim onaylı maliyeti",
        "Reddedildi",
        "Taslak",
        "Aktif çalışan",
    ]


def test_daha_alt_yonetici_birim_sorumlusu_panelini_gormez(client, veritabani):
    emre = {
        "kullanici_adi": "emre.turan",
        "ad_soyad": "Emre Turan",
        "unvan": "IT Bolum Muduru",
        "departman": "it-altyapi",
        "gruplar": ["AFH-Calisanlar", "AFH-Yoneticiler"],
        "manager": "baris.kocak",
        "manager_zinciri": ["baris.kocak", "serkan.aydemir", "ahmet.yildirim"],
        "rol": "yonetici",
    }
    app.dependency_overrides[aktif_kullanici] = lambda: emre

    yanit = client.get("/")

    assert yanit.status_code == 200
    assert "Birim Yönetimi" not in yanit.text
    assert "dashboard-grid" in yanit.text or "dashboard-stat" in yanit.text
    assert "Taslak" in yanit.text or "Draft" in yanit.text


def test_birim_sorumlusu_trend_tablosu_gunumuzden_gecmise(client, veritabani):
    from tests.test_genel_mudur_pano import _html_trend_sirasi, _trend_donemleri

    sibel = _kullanici("sibel.arslan", "Sibel Arslan", "finans", "murat.ozturk")
    app.dependency_overrides[aktif_kullanici] = lambda: sibel
    with Session(veritabani) as oturum:
        oturum.add(
            _kayit(
                "Sibel Trend",
                DURUM_ONAYLANDI,
                "finans",
                ["caner.bulut", "sibel.arslan", "murat.ozturk", "ahmet.yildirim"],
            )
        )
        oturum.commit()

    yanit = client.get("/")
    assert yanit.status_code == 200
    eski_yeni, yeni_eski = _trend_donemleri()
    grafik, tablolar = _html_trend_sirasi(yanit.text)
    assert grafik == eski_yeni
    assert tablolar == [yeni_eski]
