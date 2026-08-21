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
from app.yetkilendirme import (
    departman_basi_alt_kademe_mi,
    departman_basi_mi,
    gecmis_erisim_kapsami,
    genel_mudur_mu,
    hesaplama_departmani,
    hesaplama_gorunen_durum,
    hesaplamayi_duzenleyebilir_mi,
    kullanici_izinli_mi,
    sam_gorunen_adi,
    ustu_olmayan_mi,
)
from app.zaman import yerel_saate_cevir

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["t"] = t
templates.env.globals["kullanici_izinli_mi"] = kullanici_izinli_mi
templates.env.globals["gecmis_erisim_kapsami"] = gecmis_erisim_kapsami
templates.env.globals["genel_mudur_mu"] = genel_mudur_mu
templates.env.globals["departman_basi_mi"] = departman_basi_mi
templates.env.globals["departman_basi_alt_kademe_mi"] = departman_basi_alt_kademe_mi
templates.env.globals["hesaplama_departmani"] = hesaplama_departmani
templates.env.globals["hesaplama_gorunen_durum"] = hesaplama_gorunen_durum
templates.env.globals["hesaplamayi_duzenleyebilir_mi"] = hesaplamayi_duzenleyebilir_mi
templates.env.globals["ustu_olmayan_mi"] = ustu_olmayan_mi
templates.env.globals["kendinden_onaylayabilir_mi"] = ustu_olmayan_mi  # alias
templates.env.globals["sam_gorunen_adi"] = sam_gorunen_adi
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


def _para_bicimlendir(deger: float, para_birimi: str = "USD", dil: str = "tr") -> str:
    """Intl.NumberFormat benzeri para formatı (locale + currency code)."""
    try:
        tutar = float(deger)
    except (TypeError, ValueError):
        tutar = 0.0
    locale = "tr_TR" if dil == "tr" else "en_US"
    try:
        import babel.numbers as bn

        return bn.format_currency(tutar, para_birimi, locale=locale)
    except Exception:
        if dil == "tr":
            govde = f"{tutar:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{govde} {para_birimi}"
        return f"{tutar:,.2f} {para_birimi}"


def _birim_fiyat_bicimlendir(deger: float, para_birimi: str = "USD", dil: str = "tr") -> str:
    try:
        tutar = float(deger)
    except (TypeError, ValueError):
        tutar = 0.0
    if tutar == 0:
        return _para_bicimlendir(0, para_birimi, dil)
    # Birim fiyat için daha fazla basamak; para filtresiyle aynı locale
    if dil == "tr":
        metin = f"{tutar:.6f}".rstrip("0").rstrip(".")
        if "." in metin:
            tam, kesir = metin.split(".", 1)
            tam = f"{int(tam):,}".replace(",", ".")
            return f"{tam},{kesir} {para_birimi}"
        return f"{int(float(metin)):,}".replace(",", ".") + f" {para_birimi}"
    metin = f"{tutar:.6f}".rstrip("0").rstrip(".")
    return f"{metin} {para_birimi}"


def _yillik(deger: float) -> float:
    return deger * 12


templates.env.filters["para"] = _para_bicimlendir
templates.env.filters["birim_fiyat"] = _birim_fiyat_bicimlendir
templates.env.filters["birim"] = birim_etiketi
templates.env.filters["yillik"] = _yillik
templates.env.filters["yerel_saat"] = yerel_saate_cevir
templates.env.filters["gorunen_durum"] = hesaplama_gorunen_durum


def render(request: Request, sablon_adi: str, baglam: dict | None = None, durum_kodu: int = 200):
    tam_baglam = dict(baglam or {})
    tam_baglam.setdefault("dil", istekten_dil_al(request))
    tam_baglam.setdefault("kullanici", request.session.get("kullanici"))
    # Sablon yardimcilari: reload/eski worker senaryolarinda global kaybolmasin
    tam_baglam.setdefault("hesaplama_gorunen_durum", hesaplama_gorunen_durum)
    tam_baglam.setdefault("hesaplamayi_duzenleyebilir_mi", hesaplamayi_duzenleyebilir_mi)
    tam_baglam.setdefault("hesaplama_departmani", hesaplama_departmani)
    tam_baglam.setdefault("kullanici_izinli_mi", kullanici_izinli_mi)
    return templates.TemplateResponse(request, sablon_adi, tam_baglam, status_code=durum_kodu)
