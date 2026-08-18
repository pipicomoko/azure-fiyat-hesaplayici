import asyncio

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
    def __init__(self, veri):
        self._veri = veri

    def raise_for_status(self):
        pass

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
