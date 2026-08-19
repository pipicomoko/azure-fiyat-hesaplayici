import os

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

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


def oturum_al():
    """FastAPI dependency: her istek icin bir veritabani oturumu verir."""
    with Session(engine) as oturum:
        yield oturum
