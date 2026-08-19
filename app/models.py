from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


class Hesaplama(SQLModel, table=True):
    """Bir maliyet tahmini (senaryo). Birden fazla kalemden olusur.

    Ornek: "Web sunucusu - Ocak teklifi" adiyla kaydedilen, icinde bir VM ve
    bir disk kalemi bulunan tahmin.

    `olusturan_kullanici_adi`: kullanicinin sadece kendi kayitlarini
    gorebilmesi/silebilmesi icin BILINCLI olarak saklanan AD kullanici adi
    (kullaniciyla birlikte netlestirilmis, "asla kullanici adi saklama"
    varsayilan kuralinin bu tek alan icin gevsetilmesi). Sifre/kimlik bilgisi
    HICBIR ZAMAN saklanmaz; bu kural degismedi.

    `olusturan_gruplar`: admin gecmis ekraninda kayitlari IT/HR gibi
    organizasyonel basliklar altinda duzenleyebilmek icin, kaydetme anindaki
    AD grup snapshot'i.

    `olusturan_departman`: erisim kontrolu ve admin gruplamasinda kullanilan
    departman anahtari (it, hr, diger).
    """

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

    kalemler: list["HesaplamaKalemi"] = Relationship(
        back_populates="hesaplama",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class HesaplamaKalemi(SQLModel, table=True):
    """Bir tahmin icindeki tek bir urun kalemi (bir VM ya da bir disk).

    `yapilandirma`, ilgili urun modulunun (app/products/...) yapilandirma
    sozlugudur; `fiyat_kalemleri` ise kaydetme anindaki fiyat dokumunun
    (Compute, OS, Depolama, Islemler, Bant genisligi gibi bilesenlerin)
    JSON snapshot'idir. Fiyat, kaydetme aninda hesaplanip donmus haliyle
    saklanir; Microsoft fiyatlari sonradan degisse bile bu kayit degismez
    (gecmisle karsilastirma ozelligi bu sayede anlamli kalir).
    """

    __tablename__ = "hesaplama_kalemleri"

    id: Optional[int] = Field(default=None, primary_key=True)
    hesaplama_id: int = Field(foreign_key="hesaplamalar.id")

    urun_tipi: str
    ozet: str
    aylik_maliyet: float

    yapilandirma: dict = Field(default_factory=dict, sa_column=Column(JSON))
    fiyat_kalemleri: list = Field(default_factory=list, sa_column=Column(JSON))

    hesaplama: Optional[Hesaplama] = Relationship(back_populates="kalemler")
