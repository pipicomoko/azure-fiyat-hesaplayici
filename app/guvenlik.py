"""CSRF, yerel yonlendirme ve giris hiz sinirlamasi yardimcilari."""

from __future__ import annotations

import os
import secrets
import threading
import time
from urllib.parse import parse_qs, urlparse

from fastapi import Request
from fastapi.responses import HTMLResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

CSRF_SESSION_ANAHTARI = "csrf_token"
CSRF_FORM_ALANI = "csrf_token"
CSRF_HEADER = "x-csrf-token"
CSRF_COOKIE = "csrf_token"

# Basarisiz giris: IP + kullanici adi basina pencere / esik (AD kilitleme DoS azaltimi)
_GIRIS_PENCERE_SN = 60
_GIRIS_MAX_BASARISIZ = 5
_giris_kilitleri: dict[str, list[float]] = {}
_giris_kilit = threading.Lock()


def csrf_token_al_veya_olustur(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_ANAHTARI)
    if not token or not isinstance(token, str):
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_ANAHTARI] = token
    return token


def csrf_cerez_ayarla(yanit: Response, token: str, *, secure: bool) -> None:
    yanit.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=60 * 60 * 8,
        httponly=False,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _form_csrf_tokenu(body: bytes, content_type: str) -> str | None:
    """Body'yi bozmadan csrf alanini okumaya calisir (urlencoded)."""
    ct = (content_type or "").lower()
    if "application/x-www-form-urlencoded" not in ct:
        return None
    try:
        metin = body.decode("utf-8", errors="ignore")
    except Exception:
        return None
    degerler = parse_qs(metin, keep_blank_values=True)
    liste = degerler.get(CSRF_FORM_ALANI) or []
    return liste[0] if liste else None


class CsrfMiddleware(BaseHTTPMiddleware):
    """Oturum CSRF tokeni; HTMX X-CSRF-Token veya form alani ile dogrular.

    BaseHTTPMiddleware govdeyi tuketebildigi icin body bir kez okunup
    asagiya yeniden verilir (BUG-17).
    """

    _MUAF_YOLLAR = frozenset({"/saglik", "/canli"})

    async def dispatch(self, request: Request, call_next):
        from app.yapilandirma import uretim_ortami_mi

        if "session" in request.scope:
            token = csrf_token_al_veya_olustur(request)
        else:
            token = None

        body = b""
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            body = await request.body()

            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request = StarletteRequest(request.scope, receive)

            yol = request.url.path
            if yol not in self._MUAF_YOLLAR:
                beklenen = request.session.get(CSRF_SESSION_ANAHTARI) if token else None
                header = (
                    request.headers.get(CSRF_HEADER)
                    or request.headers.get("X-CSRF-Token")
                    or ""
                ).strip()
                form_token = _form_csrf_tokenu(
                    body, request.headers.get("content-type") or ""
                )
                gelen = header or (form_token or "")
                if (
                    not beklenen
                    or not gelen
                    or not secrets.compare_digest(beklenen, gelen)
                ):
                    return HTMLResponse("CSRF dogrulaması başarısız.", status_code=403)

        yanit = await call_next(request)
        if token:
            csrf_cerez_ayarla(yanit, token, secure=uretim_ortami_mi())
        return yanit


def yerel_yonlendirme_yolu(
    referer: str | None,
    varsayilan: str = "/",
    *,
    izinli_host: str | None = None,
) -> str:
    """Ayni host'a ait Referer path'ini dondurur; dis URL / // engellenir (BUG-14, YENI-01).

    Tarayicilar Referer'i mutlak URL gonderir; host uygulama host'uysa path kullanilir.
    """
    if not referer:
        return varsayilan
    ham = referer.strip()
    if any(ch in ham for ch in ("\r", "\n", "\\")):
        return varsayilan

    yol: str
    if ham.startswith("//"):
        return varsayilan
    if "://" in ham:
        ayrilmis = urlparse(ham)
        if ayrilmis.scheme not in {"http", "https"}:
            return varsayilan
        if not izinli_host or ayrilmis.netloc.lower() != izinli_host.lower():
            return varsayilan
        yol = ayrilmis.path or "/"
        if ayrilmis.query:
            yol = f"{yol}?{ayrilmis.query}"
    else:
        yol = ham

    if not yol.startswith("/") or yol.startswith("//"):
        return varsayilan
    return yol


def _xff_guvenilir_mi(request: Request) -> bool:
    """X-Forwarded-For yalnizca FORWARDED_ALLOW_IPS ile guvenilen vekilden gelince.

    Bos (varsayilan): istemci basligina guvenilmez — BUG-16 atlatmasini kapatir.
    '*' veya peer IP listesi: vekil arkasinda dogru istemci IP'si icin.
    """
    allow = (os.getenv("FORWARDED_ALLOW_IPS") or "").strip()
    if not allow:
        return False
    peer = request.client.host if request.client else None
    if not peer:
        return False
    if allow == "*":
        return True
    izinliler = {x.strip() for x in allow.split(",") if x.strip()}
    return peer in izinliler


def istemci_ip(request: Request) -> str:
    """Istemci IP; XFF varsayilan olarak yok sayilir (BUG-16)."""
    if _xff_guvenilir_mi(request):
        iletilen = request.headers.get("x-forwarded-for")
        if iletilen:
            # Guvenilen vekil en saga ekler; en sagdaki deger kullanilir
            parcalar = [p.strip() for p in iletilen.split(",") if p.strip()]
            if parcalar:
                return parcalar[-1]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _giris_anahtarlari(ip: str, kullanici_adi: str = "") -> list[str]:
    anahtarlar = [f"ip:{(ip or 'unknown').strip() or 'unknown'}"]
    adi = (kullanici_adi or "").strip().lower()
    if adi:
        anahtarlar.append(f"user:{adi}")
    return anahtarlar


def giris_hiz_siniri_asildi_mi(ip: str, kullanici_adi: str = "") -> bool:
    """True ise istek reddedilmeli (429). IP veya kullanici adi esigi asildiysa."""
    simdi = time.monotonic()
    with _giris_kilit:
        for anahtar in _giris_anahtarlari(ip, kullanici_adi):
            kayitlar = [
                t
                for t in _giris_kilitleri.get(anahtar, [])
                if simdi - t < _GIRIS_PENCERE_SN
            ]
            _giris_kilitleri[anahtar] = kayitlar
            if len(kayitlar) >= _GIRIS_MAX_BASARISIZ:
                return True
        return False


def giris_basarisiz_kaydet(ip: str, kullanici_adi: str = "") -> None:
    simdi = time.monotonic()
    with _giris_kilit:
        for anahtar in _giris_anahtarlari(ip, kullanici_adi):
            kayitlar = [
                t
                for t in _giris_kilitleri.get(anahtar, [])
                if simdi - t < _GIRIS_PENCERE_SN
            ]
            kayitlar.append(simdi)
            _giris_kilitleri[anahtar] = kayitlar


def giris_basarili_temizle(ip: str, kullanici_adi: str = "") -> None:
    with _giris_kilit:
        for anahtar in _giris_anahtarlari(ip, kullanici_adi):
            _giris_kilitleri.pop(anahtar, None)


def giris_hiz_siniri_sifirla() -> None:
    """Testler icin."""
    with _giris_kilit:
        _giris_kilitleri.clear()
