from datetime import datetime, timezone

import pytest
from sqlmodel import Session

from app.main import app
from app.models import DURUM_ONAY_BEKLIYOR, DURUM_ONAYLANDI, Hesaplama
from app.yetkilendirme import aktif_kullanici


DEPARTMAN_BASLARI = [
    ("serkan.aydemir", "Serkan Aydemir", "it"),
    ("murat.ozturk", "Murat Ozturk", "finans"),
    ("hande.aksoy", "Hande Aksoy", "muhasebe"),
    ("zehra.kaplan", "Zehra Kaplan", "ik"),
    ("cem.aktas", "Cem Aktas", "lojistik"),
]


def _kullanici(sam: str, ad: str, departman: str) -> dict:
    return {
        "kullanici_adi": sam,
        "ad_soyad": ad,
        "unvan": f"{departman} Muduru",
        "departman": departman,
        "gruplar": ["AFH-Calisanlar", "AFH-Direktorler"],
        "manager": "ahmet.yildirim",
        "manager_zinciri": ["ahmet.yildirim"],
        "rol": "direktor",
    }


def _kayit(ad: str, durum: str, departman: str, zincir: list[str]) -> Hesaplama:
    simdi = datetime.now(timezone.utc)
    return Hesaplama(
        ad=ad,
        durum=durum,
        toplam_aylik_maliyet=750,
        para_birimi="USD",
        olusturulma_tarihi=simdi,
        onay_tarihi=simdi if durum == DURUM_ONAYLANDI else None,
        olusturan_kullanici_adi="uzman.kullanici",
        olusturan_ad_soyad="Uzman Kullanici",
        olusturan_departman=departman,
        olusturan_manager_zinciri=zincir,
    )


@pytest.mark.parametrize("sam,ad,departman", DEPARTMAN_BASLARI)
def test_bes_departman_basi_ortak_yonetim_panelini_gorur(
    client, veritabani, sam, ad, departman
):
    app.dependency_overrides[aktif_kullanici] = lambda: _kullanici(sam, ad, departman)

    yanit = client.get("/")

    assert yanit.status_code == 200
    assert "Yönetim Özeti" in yanit.text
    assert "Departman Yönetimi" in yanit.text
    assert "Departman Kayıtları" in yanit.text
    # Departman filtresi yalnizca Ahmet panosunda; donem tarihleri ortak
    assert 'name="departman"' not in yanit.text
    assert 'name="baslangic"' in yanit.text
    assert 'name="bitis"' in yanit.text
    from app.tarih_filtre import varsayilan_tarih_iso

    bas, bit = varsayilan_tarih_iso()
    assert f'name="baslangic" value="{bas}"' in yanit.text
    assert f'name="bitis" value="{bit}"' in yanit.text


def test_departman_basi_yalnizca_manager_zincirindeki_kayitlari_gorur(
    client, veritabani
):
    murat = _kullanici("murat.ozturk", "Murat Ozturk", "finans")
    app.dependency_overrides[aktif_kullanici] = lambda: murat
    with Session(veritabani) as oturum:
        oturum.add(
            _kayit(
                "Finans Kaydi",
                DURUM_ONAYLANDI,
                "finans",
                ["caner.bulut", "sibel.arslan", "murat.ozturk", "ahmet.yildirim"],
            )
        )
        oturum.add(
            _kayit(
                "IT Kaydi",
                DURUM_ONAYLANDI,
                "it",
                ["serkan.aydemir", "ahmet.yildirim"],
            )
        )
        bekleyen = _kayit(
            "Murat Onayi",
            DURUM_ONAY_BEKLIYOR,
            "finans",
            ["murat.ozturk", "ahmet.yildirim"],
        )
        bekleyen.onay_hedefi = "murat.ozturk"
        oturum.add(bekleyen)
        oturum.commit()

    yanit = client.get("/")

    assert "Finans Kaydi" in yanit.text
    assert "Murat Onayi" in yanit.text
    assert "IT Kaydi" not in yanit.text


def test_departman_basi_pano_durum_kart_sirasi(client, veritabani):
    """Mudur ozet kartlari: bekleyen → onaylandı → reddedildi → taslak (aktif calisan sonda)."""
    import re

    murat = _kullanici("murat.ozturk", "Murat Ozturk", "finans")
    app.dependency_overrides[aktif_kullanici] = lambda: murat
    yanit = client.get("/")
    assert yanit.status_code == 200
    etiketler = re.findall(r'executive-kpi__label">([^<]+)', yanit.text)
    assert etiketler == [
        "Bekleyen potansiyel maliyet",
        "Departman onaylı maliyeti",
        "Reddedildi",
        "Taslak",
        "Aktif çalışan",
    ]


def test_ara_kademe_yonetici_departman_basi_panelini_gormez(client, veritabani):
    yonetici = {
        "kullanici_adi": "caner.bulut",
        "ad_soyad": "Caner Bulut",
        "unvan": "Finans Yoneticisi",
        "departman": "finans",
        "gruplar": ["AFH-Calisanlar", "AFH-Yoneticiler"],
        "manager": "sibel.arslan",
        "manager_zinciri": ["sibel.arslan", "murat.ozturk", "ahmet.yildirim"],
        "rol": "yonetici",
    }
    app.dependency_overrides[aktif_kullanici] = lambda: yonetici

    yanit = client.get("/")

    assert yanit.status_code == 200
    assert "Departman Yönetimi" not in yanit.text
    assert "dashboard-grid" in yanit.text or "dashboard-stat" in yanit.text
    assert "Taslak" in yanit.text or "Draft" in yanit.text
