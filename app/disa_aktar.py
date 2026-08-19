"""Tahminin .xlsx (Excel) olarak disa aktarilmasi.

Microsoft Azure Pricing Calculator'in orijinal export formatına birebir uygun:

  Sayfa: "Your Estimate"
  A1: Microsoft Azure Estimate
  A2: Your Estimate
  Basliklar: Service category | Service type | Custom name | Region |
             Description | Estimated monthly cost | Estimated upfront cost
  Veriler: her kalem tek satir
  Support satiri: Support | Support | - | Support | - | 0 | 0
  Total satiri: Total / F=toplam / G=0
  Disclaimer YOK (kullanici istegi)
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.i18n import Dil, t
from app.products.base import DisaAktarimSatiri


class TahminBosHatasi(Exception):
    """Bos bir tahmin disa aktarilamaz."""


# Azure orijinalindeki başlık rengi (açık gri arka plan)
_BASLIK_DOLGU = PatternFill("solid", fgColor="F2F2F2")
_BASLIK_YAZI = Font(bold=True)
_TOPLAM_DOLGU = PatternFill("solid", fgColor="FFFFFF")
_TOPLAM_YAZI = Font(bold=True)


def _hucrele(ws, row: int, col: int, value, bold=False, fill=None, align="left", number_format=None):
    cell = ws.cell(row=row, column=col, value=value)
    if bold:
        cell.font = Font(bold=True)
    if fill:
        cell.fill = fill
    cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=False)
    if number_format:
        cell.number_format = number_format
    return cell


def calisma_kitabi_olustur(
    satirlar: list[DisaAktarimSatiri],
    genel_toplam: float,
    para_birimi: str,
    dil: Dil,
) -> bytes:
    if not satirlar:
        raise TahminBosHatasi()

    kitap = Workbook()
    ws = kitap.active
    ws.title = "Your Estimate"

    # ── Satır 1: Microsoft Azure Estimate ────────────────────────────────────
    _hucrele(ws, 1, 1, "Microsoft Azure Estimate", bold=True)
    ws.row_dimensions[1].height = 18

    # ── Satır 2: Your Estimate ────────────────────────────────────────────────
    _hucrele(ws, 2, 1, "Your Estimate")

    # ── Satır 3: Kolon başlıkları ─────────────────────────────────────────────
    basliklar = [
        "Service category",
        "Service type",
        "Custom name",
        "Region",
        "Description",
        "Estimated monthly cost",
        "Estimated upfront cost",
    ]
    for col, baslik in enumerate(basliklar, 1):
        _hucrele(ws, 3, col, baslik, bold=True, fill=_BASLIK_DOLGU,
                 align="center" if col >= 6 else "left")
    ws.row_dimensions[3].height = 15

    # ── Veri satırları ────────────────────────────────────────────────────────
    for satir in satirlar:
        row = ws.max_row + 1
        _hucrele(ws, row, 1, satir.servis_kategori or "")
        _hucrele(ws, row, 2, satir.urun)
        _hucrele(ws, row, 3, satir.ozel_ad or "")
        _hucrele(ws, row, 4, satir.bolge)
        _hucrele(ws, row, 5, satir.yapilandirma_ozeti)
        _hucrele(ws, row, 6, round(satir.ara_toplam, 2), align="right",
                 number_format=f'#,##0.00')
        _hucrele(ws, row, 7, round(satir.on_odeme, 2), align="right",
                 number_format=f'#,##0.00')
        ws.row_dimensions[row].height = 14

    # ── Support satırı (Azure orijinalinde her zaman var) ─────────────────────
    row = ws.max_row + 1
    _hucrele(ws, row, 1, "Support")
    _hucrele(ws, row, 2, "Support")
    _hucrele(ws, row, 3, "")
    _hucrele(ws, row, 4, "Support")
    _hucrele(ws, row, 5, "")
    _hucrele(ws, row, 6, 0, align="right", number_format='#,##0.00')
    _hucrele(ws, row, 7, 0, align="right", number_format='#,##0.00')

    # ── Lisans Programı (Azure orijinalinde var) ──────────────────────────────
    row = ws.max_row + 1
    _hucrele(ws, row, 4, "Licensing Program")
    _hucrele(ws, row, 5, "Microsoft Customer Agreement (MCA)")

    # ── Total satırı ─────────────────────────────────────────────────────────
    # 2 boş satır bırak (orijinalinde Billing Account, Billing Profile var)
    ws.max_row  # sadece referans
    row_billing1 = ws.max_row + 1
    _hucrele(ws, row_billing1, 4, "Billing Account")
    _hucrele(ws, row_billing1, 5, "")
    row_billing2 = ws.max_row + 1
    _hucrele(ws, row_billing2, 4, "Billing Profile")
    _hucrele(ws, row_billing2, 5, "")

    row = ws.max_row + 1
    _hucrele(ws, row, 4, "Total", bold=True)
    _hucrele(ws, row, 6, round(genel_toplam, 2), bold=True, align="right",
             number_format='#,##0.00')
    _hucrele(ws, row, 7, 0, bold=True, align="right", number_format='#,##0.00')

    # ── Sütun genişlikleri (orijinal orantıda) ────────────────────────────────
    sutun_genislikleri = {1: 18, 2: 20, 3: 16, 4: 18, 5: 80, 6: 26, 7: 26}
    for col, genislik in sutun_genislikleri.items():
        ws.column_dimensions[get_column_letter(col)].width = genislik

    # Description sütununda wrap text
    for row_obj in ws.iter_rows(min_row=4, max_col=5, min_col=5):
        for cell in row_obj:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    arabellek = io.BytesIO()
    kitap.save(arabellek)
    return arabellek.getvalue()
