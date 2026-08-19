"""Tahminin .xlsx (Excel) olarak disa aktarilmasi.

Azure Pricing Calculator'in orijinal export formatina uygun cikti uretir:
Service type | Region | Description | Estimated monthly cost
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

    # ── Üst bilgi ─────────────────────────────────────────────────────────────
    sayfa.append([t("xlsx_baslik_satiri", dil)])
    sayfa["A1"].font = Font(bold=True, size=14)
    sayfa.append([
        t("xlsx_olusturulma_tarihi", dil),
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    ])
    sayfa.append([t("xlsx_para_birimi", dil), para_birimi])
    sayfa.append([])  # boş satır

    # ── Kolon başlıkları ──────────────────────────────────────────────────────
    basliklar = [
        t("xlsx_servis_tipi", dil),
        t("xlsx_bolge", dil),
        t("xlsx_aciklama", dil),
        t("xlsx_tahmini_aylik_maliyet", dil),
    ]
    sayfa.append(basliklar)
    baslik_satiri = sayfa.max_row
    for hucre in sayfa[baslik_satiri]:
        hucre.font = Font(bold=True, color="FFFFFF")
        hucre.fill = PatternFill("solid", fgColor="0078D4")  # Azure mavi
        hucre.alignment = Alignment(horizontal="center")

    # ── Veri satırları ────────────────────────────────────────────────────────
    for satir in satirlar:
        satirlar_verisi = [
            satir.urun,
            satir.bolge,
            satir.yapilandirma_ozeti,
            round(satir.ara_toplam, 2),
        ]
        sayfa.append(satirlar_verisi)
        # Maliyet hücresini sağa hizala
        maliyet_hucresi = sayfa.cell(row=sayfa.max_row, column=4)
        maliyet_hucresi.alignment = Alignment(horizontal="right")
        maliyet_hucresi.number_format = f'#,##0.00 "{para_birimi}"'

    # ── Toplam satırları ──────────────────────────────────────────────────────
    sayfa.append([])
    toplam_satiri = [
        t("xlsx_genel_toplam", dil), "", "",
        round(genel_toplam, 2),
    ]
    sayfa.append(toplam_satiri)
    for hucre in sayfa[sayfa.max_row]:
        hucre.font = Font(bold=True)
    sayfa.cell(row=sayfa.max_row, column=4).number_format = f'#,##0.00 "{para_birimi}"'

    yillik_satiri = [
        t("xlsx_genel_toplam_yillik", dil), "", "",
        round(genel_toplam * 12, 2),
    ]
    sayfa.append(yillik_satiri)
    for hucre in sayfa[sayfa.max_row]:
        hucre.font = Font(bold=True)
    sayfa.cell(row=sayfa.max_row, column=4).number_format = f'#,##0.00 "{para_birimi}"'

    # ── Sütun genişlikleri ────────────────────────────────────────────────────
    sutun_genislikleri = [28, 22, 48, 24]
    for idx, genislik in enumerate(sutun_genislikleri, 1):
        sayfa.column_dimensions[get_column_letter(idx)].width = genislik

    arabellek = io.BytesIO()
    kitap.save(arabellek)
    return arabellek.getvalue()
