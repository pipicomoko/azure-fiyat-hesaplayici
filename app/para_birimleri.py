"""Para birimi: Azure Pricing Calculator ile ayni — yalnizca USD.

Retail Prices API `currencyCode=USD` ile cagrilir; UI'da secim yoktur.
"""

from dataclasses import dataclass

VARSAYILAN_PARA_BIRIMI = "USD"


@dataclass(frozen=True)
class ParaBirimi:
    kod: str
    ad: str


# Geriye donuk importlar icin; UI secici kaldirildi.
PARA_BIRIMLERI: list[ParaBirimi] = [
    ParaBirimi("USD", "United States - Dollar ($)"),
]

_KODLAR = {p.kod for p in PARA_BIRIMLERI}


def para_birimi_gecerli_mi(kod: str) -> bool:
    return kod == VARSAYILAN_PARA_BIRIMI


def guvenli_para_birimi(kod: str | None) -> str:
    """Her zaman USD (formdan gelen deger yok sayilir)."""
    return VARSAYILAN_PARA_BIRIMI
