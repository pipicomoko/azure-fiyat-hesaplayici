from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

# BUG-21: app.* import'larindan once .env (database/yapilandirma env okur)
load_dotenv()

from app.database import veritabanini_olustur  # noqa: E402
from app.saglik import ldap_tcp_erisilebilir_mi, veritabani_erisilebilir_mi  # noqa: E402
from app.guvenlik import CsrfMiddleware  # noqa: E402
from app.http_basliklari import guvenlik_basliklarini_uygula  # noqa: E402
from app.routers import dashboard, giris, onay, tahmin, yonetim  # noqa: E402
from app.yapilandirma import (  # noqa: E402
    fastapi_docs_kwargs,
    oturum_secret_key,
    uretim_ortami_mi,
)
from app.yetkilendirme import GirisGerekli  # noqa: E402


class GuvenlikBasliklariMiddleware(BaseHTTPMiddleware):
    """Temel tarayici guvenlik basliklari (BUG-13)."""

    async def dispatch(self, request: Request, call_next):
        yanit = await call_next(request)
        return guvenlik_basliklarini_uygula(request, yanit)


@asynccontextmanager
async def lifespan(app: FastAPI):
    veritabanini_olustur()
    yield


app = FastAPI(
    title="Azure Fiyat Hesaplayici",
    lifespan=lifespan,
    **fastapi_docs_kwargs(),
)
# Middleware sirasi: son eklenen once calisir — session en disarida kalsin
app.add_middleware(GuvenlikBasliklariMiddleware)
app.add_middleware(CsrfMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=oturum_secret_key(),
    session_cookie="apc_session",
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=uretim_ortami_mi(),
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(dashboard.router)
app.include_router(giris.router)
app.include_router(tahmin.router)
app.include_router(tahmin.gecmis_router)
app.include_router(onay.router)
app.include_router(yonetim.router)


@app.exception_handler(GirisGerekli)
async def giris_gerekli_yoneticisi(request: Request, exc: GirisGerekli):
    return RedirectResponse("/giris", status_code=303)


@app.get("/canli")
def canli_kontrolu() -> dict:
    """Liveness: surec ayakta. DB/LDAP buraya konmaz (gecici kesintide restart olmasin)."""
    return {"durum": "calisiyor"}


@app.get("/saglik")
def saglik_kontrolu():
    """Readiness: Postgres SELECT 1 + LDAP TCP (bind yok)."""
    veritabani = veritabani_erisilebilir_mi()
    ldap = ldap_tcp_erisilebilir_mi()
    govde = {
        "durum": "calisiyor" if veritabani and ldap else "bozuk",
        "veritabani": veritabani,
        "ldap": ldap,
    }
    if veritabani and ldap:
        return govde
    return JSONResponse(govde, status_code=503)
