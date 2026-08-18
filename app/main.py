import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database import veritabanini_olustur
from app.routers import giris, tahmin, yonetim
from app.yetkilendirme import GirisGerekli


@asynccontextmanager
async def lifespan(app: FastAPI):
    veritabanini_olustur()
    yield


app = FastAPI(title="Azure Fiyat Hesaplayici", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "gelistirme-anahtari")
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(giris.router)
app.include_router(tahmin.router)
app.include_router(tahmin.gecmis_router)
app.include_router(yonetim.router)


@app.exception_handler(GirisGerekli)
async def giris_gerekli_yoneticisi(request: Request, exc: GirisGerekli):
    return RedirectResponse("/giris", status_code=303)


@app.get("/saglik")
def saglik_kontrolu() -> dict:
    """Basit saglik kontrolu ucu. Docker/CI'nin uygulamanin ayakta oldugunu
    dogrulamasi icin kullanilir."""
    return {"durum": "calisiyor"}


@app.get("/")
async def anasayfa(request: Request):
    if request.session.get("kullanici"):
        return RedirectResponse("/tahmin", status_code=303)
    return RedirectResponse("/giris", status_code=303)
