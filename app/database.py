import os

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://apc:apc@localhost:5432/apc"
)

engine = create_engine(DATABASE_URL, echo=False)


def veritabanini_olustur() -> None:
    """Tablolari (yoksa) olusturur. Uygulama baslangicinda cagrilir."""
    SQLModel.metadata.create_all(engine)
    denetleyici = inspect(engine)
    sutunlar = {sutun["name"] for sutun in denetleyici.get_columns("hesaplamalar")}
    if "olusturan_gruplar" not in sutunlar:
        with engine.begin() as baglanti:
            baglanti.execute(
                text("ALTER TABLE hesaplamalar ADD COLUMN olusturan_gruplar JSON DEFAULT '[]'::json")
            )
    sutunlar = {sutun["name"] for sutun in denetleyici.get_columns("hesaplamalar")}
    if "olusturan_departman" not in sutunlar:
        with engine.begin() as baglanti:
            if engine.dialect.name == "postgresql":
                baglanti.execute(text("ALTER TABLE hesaplamalar ADD COLUMN olusturan_departman VARCHAR"))
            else:
                baglanti.execute(text("ALTER TABLE hesaplamalar ADD COLUMN olusturan_departman TEXT"))
    sutunlar = {sutun["name"] for sutun in denetleyici.get_columns("hesaplamalar")}
    if "olusturan_unvan" not in sutunlar:
        with engine.begin() as baglanti:
            if engine.dialect.name == "postgresql":
                baglanti.execute(text("ALTER TABLE hesaplamalar ADD COLUMN olusturan_unvan VARCHAR"))
            else:
                baglanti.execute(text("ALTER TABLE hesaplamalar ADD COLUMN olusturan_unvan TEXT"))
    sutunlar = {sutun["name"] for sutun in denetleyici.get_columns("hesaplamalar")}
    if "olusturan_ad_soyad" not in sutunlar:
        with engine.begin() as baglanti:
            if engine.dialect.name == "postgresql":
                baglanti.execute(text("ALTER TABLE hesaplamalar ADD COLUMN olusturan_ad_soyad VARCHAR"))
            else:
                baglanti.execute(text("ALTER TABLE hesaplamalar ADD COLUMN olusturan_ad_soyad TEXT"))


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
    _eksik_departmanlari_doldur()


def oturum_al():
    """FastAPI dependency: her istek icin bir veritabani oturumu verir."""
    with Session(engine) as oturum:
        yield oturum
