"""Desteklenen para birimleri.

Resmi Azure Pricing Calculator'in para birimi listesiyle aynidir (canli
inceleme ile dogrulanmistir). Kur DEGERI icermez -- Retail Prices API'sine
`currencyCode` parametresi olarak gecilir, donusum Microsoft tarafinda yapilir.
"""

from dataclasses import dataclass

VARSAYILAN_PARA_BIRIMI = "USD"


@dataclass(frozen=True)
class ParaBirimi:
    kod: str
    ad: str


PARA_BIRIMLERI: list[ParaBirimi] = [
    ParaBirimi("USD", "United States - Dollar ($)"),
    ParaBirimi("AUD", "Australia - Dollar ($)"),
    ParaBirimi("BRL", "Brazil - Real (R$)"),
    ParaBirimi("CAD", "Canada - Dollar ($)"),
    ParaBirimi("DKK", "Denmark - Krone (kr)"),
    ParaBirimi("EUR", "Euro Zone - Euro (€)"),
    ParaBirimi("INR", "India - Rupee (₹)"),
    ParaBirimi("JPY", "Japan - Yen (¥)"),
    ParaBirimi("KRW", "Korea - Won (₩)"),
    ParaBirimi("NZD", "New Zealand - Dollar ($)"),
    ParaBirimi("NOK", "Norway - Krone (kr)"),
    ParaBirimi("RUB", "Russia - Ruble (руб)"),
    ParaBirimi("SEK", "Sweden - Krona (kr)"),
    ParaBirimi("CHF", "Switzerland - Franc (chf)"),
    ParaBirimi("TWD", "Taiwan - Dollar (NT$)"),
    ParaBirimi("GBP", "United Kingdom - Pound (£)"),
]

_KODLAR = {p.kod for p in PARA_BIRIMLERI}


def para_birimi_gecerli_mi(kod: str) -> bool:
    return kod in _KODLAR


def guvenli_para_birimi(kod: str | None) -> str:
    if kod and para_birimi_gecerli_mi(kod):
        return kod
    return VARSAYILAN_PARA_BIRIMI
