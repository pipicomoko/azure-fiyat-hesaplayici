"""HTTP yanıt basligi yardimcilari.

Starlette/uvicorn Content-Disposition degerlerini latin-1 ile kodlar.
Turkce (ve diger ASCII-disi) karakterler filename= alaninda UnicodeEncodeError
uretir. RFC 5987 filename*=UTF-8''… ile guvenli aktarim yapilir.

BUG-11: tahmin adindaki CRLF / tirnak / ; injection Content-Disposition'a
sizamamali; filename= yalnizca guvenli ASCII, filename* percent-encoded UTF-8.

BUG-13: CSP / HSTS / auth Cache-Control.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import Response

from app.yapilandirma import uretim_ortami_mi

# HTMX + Bootstrap + inline theme bootstrap script (taban.html)
CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

# RFC 5987 / content-disposition: parametre ayirici ve yol karakterleri
_ASCII_DOSYA = re.compile(r"[^A-Za-z0-9._-]+")
_UZANTILAR = (".xlsx", ".xls", ".csv", ".pdf", ".zip")


def _kontrol_karakterlerini_temizle(metin: str) -> str:
    """CRLF, NULL ve Unicode Cc/Cf kontrol karakterlerini siler."""
    parcalar: list[str] = []
    for ch in metin:
        if ch in ("\r", "\n", "\t", "\x00", "\x0b", "\x0c"):
            continue
        kategori = unicodedata.category(ch)
        if kategori.startswith("C"):  # Cc, Cf, Cs, Co, Cn
            continue
        parcalar.append(ch)
    return "".join(parcalar)


def dosya_adi_guvenli(dosya_adi: str, varsayilan: str = "download.xlsx") -> str:
    """Indirme dosya adini baslik enjeksiyonuna karsi temizler (BUG-11)."""
    ham = _kontrol_karakterlerini_temizle((dosya_adi or "").strip()) or varsayilan
    guvenli = (
        ham.replace('"', "")
        .replace("'", "")
        .replace("\\", "_")
        .replace("/", "_")
        .replace(";", "_")
        .replace("=", "_")
        .replace(":", "_")
    )
    # Yol gezintisi / bosluk yiginlari
    while ".." in guvenli:
        guvenli = guvenli.replace("..", "_")
    guvenli = re.sub(r"\s+", " ", guvenli).strip(" .") or varsayilan
    return guvenli


def ek_dosya_basligi(dosya_adi: str) -> str:
    """attachment Content-Disposition: ASCII fallback + UTF-8 filename*."""
    guvenli = dosya_adi_guvenli(dosya_adi)
    ascii_adi = _ASCII_DOSYA.sub(
        "_", guvenli.encode("ascii", "ignore").decode("ascii")
    ).strip("._")
    if not ascii_adi:
        ascii_adi = "download.xlsx"
    elif not any(ascii_adi.lower().endswith(ext) for ext in _UZANTILAR):
        ascii_adi = f"{ascii_adi}.xlsx"
    # Tek parametre seti; filename* tamamen percent-encoded (attr-char disi yok)
    encoded = quote(guvenli, safe="")
    baslik = f"attachment; filename=\"{ascii_adi}\"; filename*=UTF-8''{encoded}"
    # Savunma: uretilen baslik latin-1 ve enjeksiyonsuz olmali
    baslik.encode("latin-1")
    if baslik.count("filename=") != 1 or baslik.count("filename*=") != 1:
        raise ValueError("Content-Disposition beklenmeyen filename parametre sayisi")
    if "\r" in baslik or "\n" in baslik:
        raise ValueError("Content-Disposition CRLF iceremez")
    return baslik


def guvenlik_basliklarini_uygula(request: Request, yanit: Response) -> Response:
    """BUG-13: clickjacking / MIME / CSP / HSTS / auth Cache-Control."""
    yanit.headers.setdefault("X-Content-Type-Options", "nosniff")
    yanit.headers.setdefault("X-Frame-Options", "DENY")
    yanit.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    yanit.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    yanit.headers.setdefault("Content-Security-Policy", CSP)

    if uretim_ortami_mi():
        yanit.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )

    yol = request.url.path
    if yol == "/giris" or yol.startswith("/giris?") or yol == "/cikis":
        yanit.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        yanit.headers["Pragma"] = "no-cache"

    return yanit
