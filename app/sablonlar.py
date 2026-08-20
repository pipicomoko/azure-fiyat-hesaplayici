"""Paylasilan Jinja2 sablon ortami.

Tum router'lar buradaki `templates`/`render` fonksiyonlarini kullanir; boylece
`t()` (ceviri) ve `kullanici_izinli_mi()` (yetki) her sablonda ayni sekilde,
tek yerden kayitli olur -- sablonlardaki gorunurluk kontrolleri ile backend
bagimliliklari ayni fonksiyonu cagirir (bkz. app/yetkilendirme.py).
"""

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.i18n import istekten_dil_al, t
from app.kayitli_tahmin import birim_etiketi, kalem_aciklamasi, kalem_bolgesi
from app.yetkilendirme import hesaplama_departmani, kullanici_izinli_mi
from app.zaman import yerel_saate_cevir

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["t"] = t
templates.env.globals["kullanici_izinli_mi"] = kullanici_izinli_mi
templates.env.globals["hesaplama_departmani"] = hesaplama_departmani
templates.env.globals["kalem_aciklamasi"] = kalem_aciklamasi
templates.env.globals["kalem_bolgesi"] = kalem_bolgesi


_STATIK_DIZIN = Path("app/static")


def statik_surum(dosya_adi: str) -> str:
    """Statik dosyanin son degisiklik zamanini surum etiketi olarak dondurur.

    Sablonlarda `/static/app.js?v={{ statik_surum('app.js') }}` seklinde
    kullanilir: dosya degistiginde URL de degisir, boylece tarayici eski
    kopyayi onbellekten sunmaya devam etmez.
    """
    try:
        return str(int((_STATIK_DIZIN / dosya_adi).stat().st_mtime))
    except OSError:
        return "0"


templates.env.globals["statik_surum"] = statik_surum


def _para_bicimlendir(deger: float, para_birimi: str = "USD") -> str:
    return f"{deger:,.2f} {para_birimi}"


def _birim_fiyat_bicimlendir(deger: float, para_birimi: str = "USD") -> str:
    if deger == 0:
        return f"0 {para_birimi}"
    metin = f"{deger:.6f}".rstrip("0").rstrip(".")
    return f"{metin} {para_birimi}"


def _yillik(deger: float) -> float:
    return deger * 12


templates.env.filters["para"] = _para_bicimlendir
templates.env.filters["birim_fiyat"] = _birim_fiyat_bicimlendir
templates.env.filters["birim"] = birim_etiketi
templates.env.filters["yillik"] = _yillik
templates.env.filters["yerel_saat"] = yerel_saate_cevir


def render(request: Request, sablon_adi: str, baglam: dict | None = None, durum_kodu: int = 200):
    tam_baglam = dict(baglam or {})
    tam_baglam.setdefault("dil", istekten_dil_al(request))
    tam_baglam.setdefault("kullanici", request.session.get("kullanici"))
    return templates.TemplateResponse(request, sablon_adi, tam_baglam, status_code=durum_kodu)
