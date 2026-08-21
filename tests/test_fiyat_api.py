import asyncio

import httpx

from app.fiyat_api import kayitlari_getir, odata_metin_kacir, onbellek_temizle

_ORNEK_KAYIT = {
    "serviceName": "Virtual Machines",
    "productName": "Virtual Machines Dsv5 Series",
    "meterName": "D2s v5",
    "armRegionName": "westeurope",
    "unitOfMeasure": "1 Hour",
    "retailPrice": 0.096,
    "currencyCode": "USD",
}


class _SahteYanit:
    def __init__(self, veri, status_code: int = 200):
        self._veri = veri
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("GET", "https://prices.azure.com/api/retail/prices"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._veri


class _SahteIstemci:
    """httpx.AsyncClient yerine gecen, gercek aga cikmayan sahte istemci.
    Iki sayfaya bolunmus bir sonucu simule eder (NextPageLink takibini test eder)."""

    cagri_sayisi = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None):
        _SahteIstemci.cagri_sayisi += 1
        if url == "https://prices.azure.com/api/retail/prices":
            return _SahteYanit({"Items": [_ORNEK_KAYIT], "NextPageLink": "https://prices.azure.com/sayfa2"})
        return _SahteYanit({"Items": [_ORNEK_KAYIT], "NextPageLink": None})


def test_kayitlari_getir_sayfalamayi_takip_eder(monkeypatch):
    import app.fiyat_api as modul

    onbellek_temizle()
    _SahteIstemci.cagri_sayisi = 0
    monkeypatch.setattr(modul.httpx, "AsyncClient", _SahteIstemci)

    sonuclar = asyncio.run(kayitlari_getir("serviceName eq 'Virtual Machines'", onbellek_kullan=False))

    assert len(sonuclar) == 2  # iki sayfa, sayfa basina 1 kayit
    assert _SahteIstemci.cagri_sayisi == 2


def test_kayitlari_getir_onbellekler(monkeypatch):
    import app.fiyat_api as modul

    onbellek_temizle()
    _SahteIstemci.cagri_sayisi = 0
    monkeypatch.setattr(modul.httpx, "AsyncClient", _SahteIstemci)

    asyncio.run(kayitlari_getir("serviceName eq 'Virtual Machines'"))
    ilk_cagri_sayisi = _SahteIstemci.cagri_sayisi
    asyncio.run(kayitlari_getir("serviceName eq 'Virtual Machines'"))

    assert _SahteIstemci.cagri_sayisi == ilk_cagri_sayisi  # ikinci cagri onbellekten donuyor


def test_odata_metin_kacir_tek_tirnagi_kacislar():
    assert odata_metin_kacir("O'Brien") == "O''Brien"


class _429SonraOkIstemci:
    """Ilk GET 429, sonraki basarili — yeniden deneme yolunu dogrular."""

    cagri_sayisi = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None):
        _429SonraOkIstemci.cagri_sayisi += 1
        if _429SonraOkIstemci.cagri_sayisi == 1:
            yanit = httpx.Response(429, headers={"Retry-After": "0"}, request=httpx.Request("GET", url))
            return yanit
        return _SahteYanit({"Items": [_ORNEK_KAYIT], "NextPageLink": None})


def test_kayitlari_getir_429_sonra_yeniden_dener(monkeypatch):
    import app.fiyat_api as modul

    onbellek_temizle()
    _429SonraOkIstemci.cagri_sayisi = 0
    monkeypatch.setattr(modul.httpx, "AsyncClient", _429SonraOkIstemci)

    async def _hemen(*_a, **_k):
        return None

    monkeypatch.setattr(modul.asyncio, "sleep", _hemen)

    sonuclar = asyncio.run(kayitlari_getir("serviceName eq 'Virtual Machines'", onbellek_kullan=False))

    assert len(sonuclar) == 1
    assert _429SonraOkIstemci.cagri_sayisi == 2
