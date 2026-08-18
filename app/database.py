import os

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://apc:apc@localhost:5432/apc"
)

engine = create_engine(DATABASE_URL, echo=False)


def veritabanini_olustur() -> None:
    """Tablolari (yoksa) olusturur. Uygulama baslangicinda cagrilir."""
    SQLModel.metadata.create_all(engine)


def oturum_al():
    """FastAPI dependency: her istek icin bir veritabani oturumu verir."""
    with Session(engine) as oturum:
        yield oturum
