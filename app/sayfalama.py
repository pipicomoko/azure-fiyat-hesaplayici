"""Liste sayfalama yardimcilari."""

from __future__ import annotations

from urllib.parse import urlencode

from starlette.requests import Request

VARSAYILAN_SAYFA_BOYUTU = 20
MAKS_SAYFA_BOYUTU = 100


def sayfa_numarasi(ham: int | str | None, *, varsayilan: int = 1) -> int:
    try:
        deger = int(ham)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return varsayilan
    return deger if deger >= 1 else varsayilan


def sayfala(
    kayitlar: list, sayfa: int, sayfa_boyutu: int = VARSAYILAN_SAYFA_BOYUTU
) -> tuple[list, dict]:
    toplam = len(kayitlar)
    sayfa_boyutu = max(1, min(sayfa_boyutu, MAKS_SAYFA_BOYUTU))
    toplam_sayfa = max(1, (toplam + sayfa_boyutu - 1) // sayfa_boyutu) if toplam else 1
    sayfa = max(1, min(sayfa_numarasi(sayfa), toplam_sayfa))
    bas = (sayfa - 1) * sayfa_boyutu
    dilim = kayitlar[bas : bas + sayfa_boyutu]
    return dilim, {
        "sayfa": sayfa,
        "sayfa_boyutu": sayfa_boyutu,
        "toplam_kayit": toplam,
        "toplam_sayfa": toplam_sayfa,
        "onceki_sayfa": sayfa - 1 if sayfa > 1 else None,
        "sonraki_sayfa": sayfa + 1 if sayfa < toplam_sayfa else None,
    }


def sayfa_sorgusu(request: Request, sayfa: int) -> str:
    """Mevcut query parametrelerini koruyarak ?sayfa=N uretir."""
    parametreler = [
        (anahtar, deger)
        for anahtar, deger in request.query_params.multi_items()
        if anahtar != "sayfa"
    ]
    parametreler.append(("sayfa", str(sayfa)))
    return "?" + urlencode(parametreler)
