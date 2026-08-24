from sqlmodel import Session, SQLModel, create_engine

from app.models import Hesaplama, HesaplamaKalemi


def test_hesaplama_ve_kalem_iliskisi():
    """Model iliskisi ve yapilandirma/fiyat_kalemleri JSON alanlari sqlite
    uzerinde dogrulanir (Postgres'e ihtiyac duymadan hizli birim testi icin)."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as oturum:
        hesaplama = Hesaplama(ad="Test senaryosu", para_birimi="USD")
        oturum.add(hesaplama)
        oturum.commit()
        oturum.refresh(hesaplama)

        kalem = HesaplamaKalemi(
            hesaplama_id=hesaplama.id,
            urun_tipi="managed_disks",
            ozet="Standard HDD - S4 - x1 - East US",
            aylik_maliyet=1.59,
            yapilandirma={"bolge": "eastus", "kademe": "standardhdd", "sku": "S4"},
            fiyat_kalemleri=[
                {"anahtar": "disk_bilesen_depolama", "aylik_tutar": 1.536}
            ],
        )
        oturum.add(kalem)
        oturum.commit()
        oturum.refresh(hesaplama)

        assert len(hesaplama.kalemler) == 1
        assert hesaplama.kalemler[0].urun_tipi == "managed_disks"
        assert hesaplama.kalemler[0].yapilandirma["sku"] == "S4"
        assert hesaplama.kalemler[0].fiyat_kalemleri[0]["aylik_tutar"] == 1.536


def test_sifre_hicbir_alanda_saklanmaz():
    """Sifre/kimlik bilgisi HICBIR ZAMAN saklanmamali -- bu kural mutlak.

    Kullanici adi ise, kullanicinin acikca onayladigi bir istisnayla (gecmis
    kayitlarinin sahibini takip edip sadece sahibinin/Adminlerin gormesini
    saglamak icin) `olusturan_kullanici_adi` alaninda BILEREK saklanir."""
    alanlar = set(Hesaplama.model_fields) | set(HesaplamaKalemi.model_fields)
    for alan in alanlar:
        assert "sifre" not in alan.lower()
        assert "password" not in alan.lower()
    assert "olusturan_kullanici_adi" in Hesaplama.model_fields
