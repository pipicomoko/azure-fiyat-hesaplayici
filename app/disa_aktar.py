"""Tahminin .xlsx (Excel) olarak disa aktarilmasi.

Azure Pricing Calculator'in orijinal export formatina uygun cikti uretir:
Service type | Region | Description | Estimated monthly cost

Her fiziksel tahmin kalemi (VM, Disk vb.) icin tek bir satir yazilir;
alt-bilesenler (Compute, OS, Disk, Bant genisligi) toplam uzerinden
birlestirilir — aynen Azure'un orijinal Excel export'u gibi.
"""

from __future__ import annotations

import io
from collections import defaultdict
from datetime import datetime, timezone
from typing import NamedTuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.i18n import Dil, t
from app.products.base import DisaAktarimSatiri


class TahminBosHatasi(Exception):
    """Bos bir tahmin disa aktarilamaz."""


class _GrupAnahtari(NamedTuple):
    urun: str
    bolge: str
    # Konfigürasyon özetinin kalem-adı kısmını çıkar (ilk " / " öncesi)
    ozet_kok: str


def _ozet_koku(yapilandirma_ozeti: str) -> str:
    """'1 x D2s v3 - Ubuntu - East US / Compute' → '1 x D2s v3 - Ubuntu - East US'"""
    return yapilandirma_ozeti.split(" / ")[0].strip()


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
    sayfa["A1"].font = Font(bold=True, size=14, color="0078D4")
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
        hucre.fill = PatternFill("solid", fgColor="0078D4")
        hucre.alignment = Alignment(horizontal="center", vertical="center")

    # ── Alt bileşenleri grupla → her fiziksel kalem için tek satır ────────────
    gruplar: dict[_GrupAnahtari, float] = defaultdict(float)
    grup_sirasi: list[_GrupAnahtari] = []

    for satir in satirlar:
        anahtar = _GrupAnahtari(
            urun=satir.urun,
            bolge=satir.bolge,
            ozet_kok=_ozet_koku(satir.yapilandirma_ozeti),
        )
        if anahtar not in gruplar:
            grup_sirasi.append(anahtar)
        gruplar[anahtar] += satir.ara_toplam

    for anahtar in grup_sirasi:
        toplam = round(gruplar[anahtar], 2)
        sayfa.append([
            anahtar.urun,
            anahtar.bolge,
            anahtar.ozet_kok,
            toplam,
        ])
        satir_no = sayfa.max_row
        # Zebra renklendirme (soluk mavi / beyaz)
        if (satir_no - baslik_satiri) % 2 == 0:
            for hucre in sayfa[satir_no]:
                hucre.fill = PatternFill("solid", fgColor="EBF3FB")
        maliyet_hucresi = sayfa.cell(row=satir_no, column=4)
        maliyet_hucresi.alignment = Alignment(horizontal="right")
        maliyet_hucresi.number_format = f'#,##0.00 "{para_birimi}"'

    # ── Toplam satırları ──────────────────────────────────────────────────────
    sayfa.append([])

    toplam_satiri_no = sayfa.max_row + 1
    sayfa.append([
        t("xlsx_genel_toplam", dil), "", "",
        round(genel_toplam, 2),
    ])
    for hucre in sayfa[sayfa.max_row]:
        hucre.font = Font(bold=True)
        hucre.fill = PatternFill("solid", fgColor="D0E8F8")
    sayfa.cell(row=sayfa.max_row, column=4).number_format = f'#,##0.00 "{para_birimi}"'
    sayfa.cell(row=sayfa.max_row, column=4).alignment = Alignment(horizontal="right")

    sayfa.append([
        t("xlsx_genel_toplam_yillik", dil), "", "",
        round(genel_toplam * 12, 2),
    ])
    for hucre in sayfa[sayfa.max_row]:
        hucre.font = Font(bold=True)
        hucre.fill = PatternFill("solid", fgColor="D0E8F8")
    sayfa.cell(row=sayfa.max_row, column=4).number_format = f'#,##0.00 "{para_birimi}"'
    sayfa.cell(row=sayfa.max_row, column=4).alignment = Alignment(horizontal="right")

    # ── Sütun genişlikleri ────────────────────────────────────────────────────
    sutun_genislikleri = [28, 22, 52, 26]
    for idx, genislik in enumerate(sutun_genislikleri, 1):
        sayfa.column_dimensions[get_column_letter(idx)].width = genislik

    # ── Başlık satırı yüksekliği ──────────────────────────────────────────────
    sayfa.row_dimensions[baslik_satiri].height = 20

    arabellek = io.BytesIO()
    kitap.save(arabellek)
    return arabellek.getvalue()
