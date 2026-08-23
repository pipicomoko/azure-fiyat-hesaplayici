from datetime import datetime, timezone

from sqlmodel import Session

from app.main import app
from app.models import (
    DURUM_ONAY_BEKLIYOR,
    DURUM_ONAYLANDI,
    DURUM_TASLAK,
    AktiviteKaydi,
    Hesaplama,
)
from app.yetkilendirme import aktif_kullanici, giris_sonrasi_yol


AHMET = {
    "kullanici_adi": "ahmet.yildirim",
    "ad_soyad": "Ahmet Yildirim",
    "unvan": "Genel Mudur",
    "gruplar": ["AFH-Calisanlar", "AFH-Direktorler"],
    "manager": "",
    "manager_zinciri": [],
    "rol": "direktor",
}


def _kayit(
    ad: str,
    durum: str,
    tutar: float,
    para: str = "USD",
    departman: str = "finans",
    sahibi: str = "elif.aydin",
) -> Hesaplama:
    simdi = datetime.now(timezone.utc)
    return Hesaplama(
        ad=ad,
        durum=durum,
        toplam_aylik_maliyet=tutar,
        para_birimi=para,
        olusturulma_tarihi=simdi,
        onay_tarihi=simdi if durum == DURUM_ONAYLANDI else None,
        olusturan_kullanici_adi=sahibi,
        olusturan_ad_soyad="Elif Aydin",
        olusturan_departman=departman,
        olusturan_manager_zinciri=[
            "caner.bulut",
            "sibel.arslan",
            "murat.ozturk",
            "ahmet.yildirim",
        ],
        onay_hedefi="ahmet.yildirim" if durum == DURUM_ONAY_BEKLIYOR else None,
    )


def test_ahmet_sirket_ozetini_ve_para_birimlerini_ayri_gorur(client, veritabani):
    app.dependency_overrides[aktif_kullanici] = lambda: AHMET
    with Session(veritabani) as oturum:
        oturum.add(_kayit("Finans USD", DURUM_ONAYLANDI, 1250, "USD"))
        oturum.add(_kayit("IT EUR", DURUM_ONAYLANDI, 800, "EUR", "it-yazilim"))
        oturum.add(_kayit("Bekleyen", DURUM_ONAY_BEKLIYOR, 300, "USD"))
        oturum.add(_kayit("Gizli Taslak", DURUM_TASLAK, 99999, "USD"))
        oturum.commit()

    yanit = client.get("/")

    assert yanit.status_code == 200
    assert "Şirket Maliyet Özeti" in yanit.text
    assert "Finans USD" in yanit.text
    assert "IT EUR" in yanit.text
    assert "Bekleyen" in yanit.text
    assert "Gizli Taslak" not in yanit.text
    assert "1.250,00" in yanit.text
    assert "800,00" in yanit.text


def test_ahmet_kapsami_disindaki_kaydi_gormez(client, veritabani):
    app.dependency_overrides[aktif_kullanici] = lambda: AHMET
    dis_kayit = _kayit("Baska Sirket", DURUM_ONAYLANDI, 500)
    dis_kayit.olusturan_manager_zinciri = ["baska.yonetici"]
    with Session(veritabani) as oturum:
        oturum.add(dis_kayit)
        oturum.commit()

    yanit = client.get("/")
    assert yanit.status_code == 200
    assert "Baska Sirket" not in yanit.text


def test_gecersiz_tarih_araligi_bu_aya_doner(client, veritabani):
    app.dependency_overrides[aktif_kullanici] = lambda: AHMET
    yanit = client.get("/?baslangic=2026-12-31&bitis=2026-01-01")
    assert yanit.status_code == 200
    assert "Tarih aralığı geçersizdi" in yanit.text


def test_normal_calisan_mevcut_kisisel_panoyu_gorur(client, veritabani):
    yanit = client.get("/")
    assert yanit.status_code == 200
    assert "Şirket Maliyet Özeti" not in yanit.text
    assert "Taslak, gönderilen, onaylanan" in yanit.text


def test_durum_sayaclari_audit_islem_tarihini_kullanir(client, veritabani):
    app.dependency_overrides[aktif_kullanici] = lambda: AHMET
    with Session(veritabani) as oturum:
        hesaplama = _kayit("Reddedilen Talep", DURUM_TASLAK, 100)
        hesaplama.red_gerekce = "Revize edilmeli"
        oturum.add(hesaplama)
        oturum.flush()
        oturum.add(
            AktiviteKaydi(
                aktor_kullanici_adi="ahmet.yildirim",
                islem="reddedildi",
                hesaplama_id=hesaplama.id,
            )
        )
        oturum.commit()

    yanit = client.get("/")
    assert yanit.status_code == 200
    assert "Reddedildi</span><strong>1</strong>" in yanit.text


def test_ahmet_giris_sonrasi_yonetici_ozetine_yonlenir():
    assert giris_sonrasi_yol(AHMET) == "/"
