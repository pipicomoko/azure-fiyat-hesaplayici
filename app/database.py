import os

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://apc:apc@localhost:5432/apc"
)

engine = create_engine(DATABASE_URL, echo=False)


def _pg() -> bool:
    return engine.dialect.name == "postgresql"


def _ekle_sutun(tablo: str, sutun: str, tip_pg: str, tip_diger: str = "TEXT") -> None:
    denetleyici = inspect(engine)
    if tablo not in denetleyici.get_table_names():
        return
    mevcut = {s["name"] for s in denetleyici.get_columns(tablo)}
    if sutun in mevcut:
        return
    tip = tip_pg if _pg() else tip_diger
    with engine.begin() as baglanti:
        baglanti.execute(text(f"ALTER TABLE {tablo} ADD COLUMN {sutun} {tip}"))


def veritabanini_olustur() -> None:
    """Tablolari (yoksa) olusturur; eksik sutunlari ekler."""
    import app.models  # noqa: F401 — metadata kaydi

    SQLModel.metadata.create_all(engine)

    _ekle_sutun("hesaplamalar", "olusturan_gruplar", "JSON DEFAULT '[]'::json", "TEXT DEFAULT '[]'")
    _ekle_sutun("hesaplamalar", "olusturan_departman", "VARCHAR")
    _ekle_sutun("hesaplamalar", "olusturan_unvan", "VARCHAR")
    _ekle_sutun("hesaplamalar", "olusturan_ad_soyad", "VARCHAR")
    _ekle_sutun("hesaplamalar", "durum", "VARCHAR DEFAULT 'taslak'", "TEXT DEFAULT 'taslak'")
    _ekle_sutun("hesaplamalar", "revizyon", "INTEGER DEFAULT 1", "INTEGER DEFAULT 1")
    _ekle_sutun("hesaplamalar", "onay_hedefi", "VARCHAR")
    _ekle_sutun("hesaplamalar", "onay_hedefi_ad_soyad", "VARCHAR")
    _ekle_sutun("hesaplamalar", "onaylayan_kullanici_adi", "VARCHAR")
    _ekle_sutun("hesaplamalar", "onay_tarihi", "TIMESTAMP")
    _ekle_sutun("hesaplamalar", "red_gerekce", "VARCHAR")
    _ekle_sutun("hesaplamalar", "iptal_gerekce", "VARCHAR")
    _ekle_sutun(
        "hesaplamalar",
        "olusturan_manager_zinciri",
        "JSON DEFAULT '[]'::json",
        "TEXT DEFAULT '[]'",
    )
    _ekle_sutun("hesaplama_kalemleri", "indirim_yuzdesi", "DOUBLE PRECISION", "REAL")
    _ekle_sutun("hesaplama_kalemleri", "indirimli_aylik_maliyet", "DOUBLE PRECISION", "REAL")


def _eksik_departmanlari_doldur() -> None:
    """Grup snapshot'i olan ama departman alani bos kayitlari gunceller."""
    from app.models import Hesaplama
    from app.yetkilendirme import gruplardan_departman_belirle

    with Session(engine) as oturum:
        adaylar = oturum.exec(
            select(Hesaplama).where(Hesaplama.olusturan_departman.is_(None))  # type: ignore[union-attr]
        ).all()
        guncellendi = False
        for hesaplama in adaylar:
            if not hesaplama.olusturan_gruplar:
                continue
            anahtar, _ = gruplardan_departman_belirle(hesaplama.olusturan_gruplar)
            hesaplama.olusturan_departman = anahtar
            oturum.add(hesaplama)
            guncellendi = True
        if guncellendi:
            oturum.commit()


def oturum_al():
    """FastAPI dependency: her istek icin bir veritabani oturumu verir."""
    with Session(engine) as oturum:
        yield oturum
