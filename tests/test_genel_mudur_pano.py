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
    assert 'name="departman"' in yanit.text
    assert "Tüm departmanlar" in yanit.text
    assert "Finans USD" in yanit.text
    assert "IT EUR" in yanit.text
    assert "Bekleyen" in yanit.text
    assert "Gizli Taslak" not in yanit.text
    assert "1.250,00" in yanit.text
    assert "800,00" in yanit.text


def test_ahmet_departman_filtresi_sadece_secileni_gosterir(client, veritabani):
    app.dependency_overrides[aktif_kullanici] = lambda: AHMET
    with Session(veritabani) as oturum:
        oturum.add(_kayit("Finans USD", DURUM_ONAYLANDI, 1250, "USD", "finans"))
        oturum.add(_kayit("IT EUR", DURUM_ONAYLANDI, 800, "EUR", "it"))
        oturum.commit()

    yanit = client.get("/?departman=it")
    assert yanit.status_code == 200
    assert "IT EUR" in yanit.text
    assert "Finans USD" not in yanit.text
    assert 'name="alt_birim"' in yanit.text
    assert (
        "IT Yazilim" in yanit.text
        or "IT Yazılım" in yanit.text
        or "IT Altyapi" in yanit.text
    )


def test_ahmet_alt_birim_filtresi(client, veritabani):
    app.dependency_overrides[aktif_kullanici] = lambda: AHMET
    with Session(veritabani) as oturum:
        oturum.add(_kayit("Yazilim Kaydi", DURUM_ONAYLANDI, 500, "USD", "it-yazilim"))
        oturum.add(_kayit("Altyapi Kaydi", DURUM_ONAYLANDI, 300, "USD", "it-altyapi"))
        oturum.commit()

    yanit = client.get("/?departman=it&alt_birim=it-yazilim")
    assert yanit.status_code == 200
    assert "Yazilim Kaydi" in yanit.text
    assert "Altyapi Kaydi" not in yanit.text
    assert 'value="it-yazilim"' in yanit.text


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
    from app.tarih_filtre import varsayilan_tarih_iso

    bas, bit = varsayilan_tarih_iso()
    assert f'name="baslangic" value="{bas}"' in yanit.text
    assert f'name="bitis" value="{bit}"' in yanit.text


def test_ahmet_pano_varsayilan_tarih_araligi(client, veritabani):
    app.dependency_overrides[aktif_kullanici] = lambda: AHMET
    from app.tarih_filtre import varsayilan_tarih_iso

    bas, bit = varsayilan_tarih_iso()
    yanit = client.get("/")
    assert yanit.status_code == 200
    assert f'name="baslangic" value="{bas}"' in yanit.text
    assert f'name="bitis" value="{bit}"' in yanit.text


def test_ahmet_pano_acik_tarih_parametreleri_korunur(client, veritabani):
    app.dependency_overrides[aktif_kullanici] = lambda: AHMET
    with Session(veritabani) as oturum:
        eski = _kayit("Eski Kayit", DURUM_ONAYLANDI, 100)
        eski.olusturulma_tarihi = datetime(2025, 1, 10, tzinfo=timezone.utc)
        eski.onay_tarihi = datetime(2025, 1, 10, tzinfo=timezone.utc)
        oturum.add(eski)
        oturum.commit()

    var = client.get("/?baslangic=2025-01-01&bitis=2025-01-31")
    assert var.status_code == 200
    assert "Eski Kayit" in var.text
    assert 'name="baslangic" value="2025-01-01"' in var.text
    assert 'name="bitis" value="2025-01-31"' in var.text

    baska = client.get("/?baslangic=2024-01-01&bitis=2024-01-31")
    assert baska.status_code == 200
    assert 'name="baslangic" value="2024-01-01"' in baska.text
    assert 'name="bitis" value="2024-01-31"' in baska.text


def test_normal_calisan_mevcut_kisisel_panoyu_gorur(client, veritabani):
    yanit = client.get("/")
    assert yanit.status_code == 200
    assert "Şirket Maliyet Özeti" not in yanit.text
    # Kisisel pano: ozet kartlari (Dashboard baslik karti kaldirildi)
    assert "dashboard-grid" in yanit.text or "dashboard-stat" in yanit.text
    assert "Taslak" in yanit.text or "Draft" in yanit.text


def test_calisan_pano_durum_kart_ve_liste_sirasi(client, veritabani):
    """Calisan ana sayfa kartlari ve alt listeler: bekleyen → onaylandı → reddedildi → taslak."""
    import re

    yanit = client.get("/")
    assert yanit.status_code == 200
    beklenen = ["Onay bekliyor", "Onaylandı", "Reddedildi", "Taslak"]
    etiketler = re.findall(
        r"(Onay bekliyor|Onaylandı|Reddedildi|Taslak)(?=\s*<)", yanit.text
    )
    assert etiketler == beklenen * 2


def test_gm_pano_durum_kart_sirasi(client, veritabani):
    """GM ozet kartlari: bekleyen → onaylandı → reddedildi → taslak."""
    import re

    app.dependency_overrides[aktif_kullanici] = lambda: AHMET
    yanit = client.get("/")
    assert yanit.status_code == 200
    etiketler = re.findall(r'executive-kpi__label">([^<]+)', yanit.text)
    assert etiketler == [
        "Bekleyen potansiyel maliyet",
        "Onaylı aylık maliyet",
        "Reddedildi",
        "Taslak",
    ]


def test_ahmet_arama_durum_filtre_sirasi(client, veritabani):
    """Sirket kayitlari durum filtresi: bekleyen → onaylandı → reddedildi → taslak → iptal."""
    import re

    app.dependency_overrides[aktif_kullanici] = lambda: AHMET
    yanit = client.get("/gecmis/arama")
    assert yanit.status_code == 200
    select = re.search(r'name="durum"[^>]*>(.*?)</select>', yanit.text, re.S)
    assert select, "durum filtresi bulunamadi"
    degerler = re.findall(r'<option value="([^"]*)"', select.group(1))
    assert degerler == [
        "",
        "onay_bekliyor",
        "onaylandi",
        "reddedildi",
        "taslak",
        "iptal_edildi",
    ]


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
