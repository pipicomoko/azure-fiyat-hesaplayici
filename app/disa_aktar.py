"""Tahminin .xlsx (Excel) olarak disa aktarilmasi.

Girdi olarak, tahmin motorunun (routers/tahmin.py) O ANDA yeniden hesapladigi
kalem/fiyat ciftlerini alir -- burada YENIDEN fiyat hesaplanmaz, sadece
bicimlendirilir. Boylece dosyadaki rakamlar, hesaplamanin kendisiyle
(app/products/*/fiyatlama.py) her zaman birebir tutarlidir.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from app.i18n import Dil, t
from app.products.base import DisaAktarimSatiri


class TahminBosHatasi(Exception):
    """Bos bir tahmin disa aktarilamaz."""


def calisma_kitabi_olustur(
    satirlar: list[DisaAktarimSatiri],
    genel_toplam: float,
    para_birimi: str,
    dil: Dil,
) -> bytes:
    if not satirlar:
        raise TahminBosHatasi()

    kitap = Workbook()
    sayfa = kitap.active
    sayfa.title = t("xlsx_sayfa_adi", dil)

    basliklar = [
        t("xlsx_urun", dil),
        t("xlsx_ozet", dil),
        t("xlsx_bolge", dil),
        t("xlsx_miktar", dil),
        t("xlsx_birim", dil),
        t("xlsx_birim_fiyat", dil),
        t("xlsx_ara_toplam", dil),
    ]
    sayfa.append(basliklar)
    for hucre in sayfa[1]:
        hucre.font = Font(bold=True)

    for satir in satirlar:
        sayfa.append(
            [
                satir.urun,
                satir.yapilandirma_ozeti,
                satir.bolge,
                round(satir.miktar, 4),
                satir.birim,
                round(satir.birim_fiyat, 6),
                round(satir.ara_toplam, 2),
            ]
        )

    sayfa.append([])
    genel_toplam_satiri = [t("xlsx_genel_toplam", dil), "", "", "", "", "", round(genel_toplam, 2)]
    sayfa.append(genel_toplam_satiri)
    for hucre in sayfa[sayfa.max_row]:
        hucre.font = Font(bold=True)

    yillik_toplam_satiri = [t("xlsx_genel_toplam_yillik", dil), "", "", "", "", "", round(genel_toplam * 12, 2)]
    sayfa.append(yillik_toplam_satiri)
    for hucre in sayfa[sayfa.max_row]:
        hucre.font = Font(bold=True)

    sayfa.append([t("xlsx_para_birimi", dil), para_birimi])
    sayfa.append([t("xlsx_olusturulma_tarihi", dil), datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])

    for sutun_index in range(1, len(basliklar) + 1):
        harf = get_column_letter(sutun_index)
        genislik = max(14, min(48, max(len(str(hucre.value or "")) for hucre in sayfa[harf]) + 2))
        sayfa.column_dimensions[harf].width = genislik

    arabellek = io.BytesIO()
    kitap.save(arabellek)
    return arabellek.getvalue()
