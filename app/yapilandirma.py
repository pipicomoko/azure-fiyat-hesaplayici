"""Uygulama ortam yapilandirmasi (guvenlik-kritik env)."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

# BUG-21: uvicorn app.main:app ile .env compose disinda da yuklensin
load_dotenv()

GELISTIRME_SECRET_KEY = "gelistirme-anahtari"
_ZAYIF_SECRET_KEYLER = frozenset(
    {
        GELISTIRME_SECRET_KEY,
        "secret",
        "changeme",
        "password",
        "123456",
        "test",
    }
)


def uretim_ortami_mi() -> bool:
    return (os.getenv("APP_ENV") or "development").strip().lower() == "production"


def fastapi_docs_kwargs() -> dict[str, Any]:
    """Production'da /docs, /redoc, /openapi.json kapali (BUG-08)."""
    if uretim_ortami_mi():
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


def oturum_secret_key() -> str:
    """SessionMiddleware imza anahtari.

    APP_ENV=production iken SECRET_KEY zorunlu ve gelistirme varsayilanlari
    reddedilir (BUG-05). Gelistirmede eksikse bilinen lokal varsayilan kullanilir.
    """
    anahtar = (os.getenv("SECRET_KEY") or "").strip()

    if uretim_ortami_mi():
        if not anahtar or anahtar in _ZAYIF_SECRET_KEYLER:
            raise RuntimeError(
                "Uretim ortaminda (APP_ENV=production) guclu bir SECRET_KEY zorunludur. "
                "SECRET_KEY ortam degiskenini ayarlayin; "
                f"'{GELISTIRME_SECRET_KEY}' ve diger zayif degerler kabul edilmez."
            )
        if len(anahtar) < 32:
            raise RuntimeError(
                "Uretim ortaminda SECRET_KEY en az 32 karakter olmalidir "
                '(or. python -c "import secrets; print(secrets.token_urlsafe(48))").'
            )
        return anahtar

    return anahtar or GELISTIRME_SECRET_KEY
