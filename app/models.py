from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

# Hesaplama durum makinesi (spesifikasyon §2)
DURUM_TASLAK = "taslak"
DURUM_ONAY_BEKLIYOR = "onay_bekliyor"
DURUM_ONAYLANDI = "onaylandi"
DURUM_IPTAL_EDILDI = "iptal_edildi"
# Reddedilince kayit tekrar taslak olur; red gerekcesi ve revizyon artar.


class Hesaplama(SQLModel, table=True):
    """Bir maliyet tahmini (senaryo). Onay akisi ve rol bazli gorunurluk destekler."""

    __tablename__ = "hesaplamalar"

    id: Optional[int] = Field(default=None, primary_key=True)
    ad: str = Field(description="Tahmine verilen isim")
    olusturulma_tarihi: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    toplam_aylik_maliyet: float = Field(default=0.0)
    para_birimi: str = Field(default="USD")
    olusturan_kullanici_adi: Optional[str] = Field(default=None, index=True)
    olusturan_gruplar: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    olusturan_departman: Optional[str] = Field(default=None, index=True)
    olusturan_unvan: Optional[str] = Field(default=None)
    olusturan_ad_soyad: Optional[str] = Field(default=None)

    durum: str = Field(default=DURUM_TASLAK, index=True)
    revizyon: int = Field(default=1)
    onay_hedefi: Optional[str] = Field(default=None, index=True)
    onay_hedefi_ad_soyad: Optional[str] = Field(default=None)
    onaylayan_kullanici_adi: Optional[str] = Field(default=None)
    onay_tarihi: Optional[datetime] = Field(default=None)
    red_gerekce: Optional[str] = Field(default=None)
    iptal_gerekce: Optional[str] = Field(default=None)
    # Manager zinciri anlik goruntusu (onaya gonderildiginde)
    olusturan_manager_zinciri: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )

    kalemler: list["HesaplamaKalemi"] = Relationship(
        back_populates="hesaplama",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class HesaplamaKalemi(SQLModel, table=True):
    """Tahmin icindeki tek urun kalemi; opsiyonel indirim yuzdesi tutar."""

    __tablename__ = "hesaplama_kalemleri"

    id: Optional[int] = Field(default=None, primary_key=True)
    hesaplama_id: int = Field(foreign_key="hesaplamalar.id")

    urun_tipi: str
    ozet: str
    aylik_maliyet: float
    indirim_yuzdesi: Optional[float] = Field(default=None)
    indirimli_aylik_maliyet: Optional[float] = Field(default=None)

    yapilandirma: dict = Field(default_factory=dict, sa_column=Column(JSON))
    fiyat_kalemleri: list = Field(default_factory=list, sa_column=Column(JSON))

    hesaplama: Optional[Hesaplama] = Relationship(back_populates="kalemler")


GIRIS_SONUC_BASARILI = "basarili"
GIRIS_SONUC_BASARISIZ = "basarisiz"
GIRIS_SONUC_KILITLI = "kilitli"


class GirisDenemesi(SQLModel, table=True):
    """Basarili/basarisiz giris denemeleri. Sifre asla yazilmaz."""

    __tablename__ = "giris_denemeleri"

    id: Optional[int] = Field(default=None, primary_key=True)
    olusturulma_tarihi: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
    kullanici_adi: str = Field(index=True)
    ip: str = Field(default="")
    sonuc: str = Field(index=True)
    hata_tipi: Optional[str] = Field(default=None)


class AktiviteKaydi(SQLModel, table=True):
    """Audit log: kim ne zaman onayladi/reddetti/iptal etti."""

    __tablename__ = "aktivite_kayitlari"

    id: Optional[int] = Field(default=None, primary_key=True)
    olusturulma_tarihi: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
    aktor_kullanici_adi: str = Field(index=True)
    islem: str = Field(index=True)
    hesaplama_id: Optional[int] = Field(default=None, index=True)
    detay: Optional[str] = Field(default=None)
