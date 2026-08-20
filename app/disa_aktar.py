"""Tahminin .xlsx (Excel) olarak disa aktarilmasi.

Export Tur A: Azure orijinal format + AFH ust bilgi / indirim / yillik sutunlari.
Export Tur B: Donemsel ozet (onaylanmis kayitlar).
"""

from __future__ import annotations

import io
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.i18n import Dil
from app.products.base import DisaAktarimSatiri


class TahminBosHatasi(Exception):
    """Bos bir tahmin disa aktarilamaz."""


_BASLIK_DOLGU = PatternFill("solid", fgColor="F2F2F2")
_ACIKLAMA_GENISLIGI = 110
_SATIR_YUKSEKLIGI = 15.0
_DISCLAIMER = (
    "All prices shown are in United States – Dollar ($). "
    "This is an estimate and is not a quote. Prices are subject to change."
)


@dataclass
class HesaplamaMeta:
    senaryo_adi: str = ""
    olusturan: str = ""
    birim: str = ""
    olusturma_tarihi: str = ""
    durum: str = ""
    revizyon: int = 1
    onaylayan: str = ""
    onay_tarihi: str = ""


def hesaplama_meta_olustur(hesaplama) -> HesaplamaMeta:
    from app.yetkilendirme import departman_etiketi, hesaplama_departmani

    dep = hesaplama_departmani(
        getattr(hesaplama, "olusturan_gruplar", None),
        getattr(hesaplama, "olusturan_departman", None),
    )
    onay_t = getattr(hesaplama, "onay_tarihi", None)
    olusturma = getattr(hesaplama, "olusturulma_tarihi", None)
    return HesaplamaMeta(
        senaryo_adi=str(getattr(hesaplama, "ad", "") or ""),
        olusturan=str(
            getattr(hesaplama, "olusturan_ad_soyad", None)
            or getattr(hesaplama, "olusturan_kullanici_adi", "")
            or ""
        ),
        birim=departman_etiketi(dep) if dep else "",
        olusturma_tarihi=olusturma.strftime("%Y-%m-%d %H:%M") if olusturma else "",
        durum=str(getattr(hesaplama, "durum", "") or ""),
        revizyon=int(getattr(hesaplama, "revizyon", 1) or 1),
        onaylayan=str(getattr(hesaplama, "onaylayan_kullanici_adi", "") or ""),
        onay_tarihi=onay_t.strftime("%Y-%m-%d %H:%M") if onay_t else "",
    )


def _satir_yuksekligi(metin: str | None, sutun_genisligi: int) -> float:
    if not metin:
        return _SATIR_YUKSEKLIGI
    satir_sayisi = 0
    for paragraf in str(metin).split("\n"):
        sarilmis = textwrap.wrap(paragraf, width=sutun_genisligi) or [""]
        satir_sayisi += len(sarilmis)
    return max(_SATIR_YUKSEKLIGI, satir_sayisi * _SATIR_YUKSEKLIGI)


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
    meta: HesaplamaMeta | None = None,
) -> bytes:
    if not satirlar:
        raise TahminBosHatasi()

    kitap = Workbook()
    ws = kitap.active
    ws.title = "Your Estimate"

    _hucrele(ws, 1, 1, "Microsoft Azure Estimate", bold=True)
    ws.row_dimensions[1].height = 18

    # Ust bilgi (Tur A eklemeleri)
    row = 2
    if meta:
        _hucrele(ws, row, 1, meta.senaryo_adi or "Your Estimate")
        row += 1
        for etiket, deger in (
            ("Olusturan Calisan", meta.olusturan),
            ("Birim", meta.birim),
            ("Olusturulma Tarihi", meta.olusturma_tarihi),
            ("Durum", f"{meta.durum} / Rev {meta.revizyon}"),
            ("Onaylayan", meta.onaylayan),
            ("Onay Tarihi", meta.onay_tarihi),
        ):
            if not deger:
                continue
            _hucrele(ws, row, 1, etiket, bold=True)
            _hucrele(ws, row, 2, deger)
            row += 1
    else:
        _hucrele(ws, row, 1, "Your Estimate")
        row += 1

    baslik_satiri = row
    basliklar = [
        "Service category",
        "Service type",
        "Custom name",
        "Region",
        "Description",
        "Estimated monthly cost",
        "Indirim Yuzdesi",
        "Indirimli Aylik Maliyet",
        "Estimated upfront cost",
        "Yillik Tahmini Maliyet",
    ]
    for col, baslik in enumerate(basliklar, 1):
        _hucrele(
            ws,
            baslik_satiri,
            col,
            baslik,
            bold=True,
            fill=_BASLIK_DOLGU,
            align="center" if col >= 6 else "left",
        )
    ws.row_dimensions[baslik_satiri].height = 15

    for satir in satirlar:
        r = ws.max_row + 1
        aylik = float(satir.ara_toplam)
        indirim = getattr(satir, "indirim_yuzdesi", None)
        indirimli = getattr(satir, "indirimli_aylik", None)
        esas = float(indirimli) if indirimli is not None else aylik
        _hucrele(ws, r, 1, satir.servis_kategori or "")
        _hucrele(ws, r, 2, satir.urun)
        _hucrele(ws, r, 3, satir.ozel_ad or "")
        _hucrele(ws, r, 4, satir.bolge)
        _hucrele(ws, r, 5, satir.yapilandirma_ozeti)
        _hucrele(ws, r, 6, round(aylik, 2), align="right", number_format="#,##0.00")
        if indirim is not None:
            _hucrele(ws, r, 7, round(float(indirim), 2), align="right", number_format="0.00")
            _hucrele(ws, r, 8, round(float(indirimli or esas), 2), align="right", number_format="#,##0.00")
        else:
            _hucrele(ws, r, 7, "—")
            _hucrele(ws, r, 8, "—")
        _hucrele(ws, r, 9, round(satir.on_odeme, 2), align="right", number_format="#,##0.00")
        _hucrele(ws, r, 10, round(esas * 12, 2), align="right", number_format="#,##0.00")
        ws.row_dimensions[r].height = _satir_yuksekligi(satir.yapilandirma_ozeti, _ACIKLAMA_GENISLIGI)

    r = ws.max_row + 1
    _hucrele(ws, r, 1, "Support")
    _hucrele(ws, r, 2, "Support")
    _hucrele(ws, r, 3, "")
    _hucrele(ws, r, 4, "Support")
    _hucrele(ws, r, 5, "")
    _hucrele(ws, r, 6, 0, align="right", number_format="#,##0.00")
    _hucrele(ws, r, 7, "")
    _hucrele(ws, r, 8, "")
    _hucrele(ws, r, 9, 0, align="right", number_format="#,##0.00")
    _hucrele(ws, r, 10, 0, align="right", number_format="#,##0.00")

    r = ws.max_row + 1
    _hucrele(ws, r, 4, "Licensing Program")
    _hucrele(ws, r, 5, "Microsoft Customer Agreement (MCA)")
    r = ws.max_row + 1
    _hucrele(ws, r, 4, "Billing Account")
    _hucrele(ws, r, 5, "")
    r = ws.max_row + 1
    _hucrele(ws, r, 4, "Billing Profile")
    _hucrele(ws, r, 5, "")

    r = ws.max_row + 1
    _hucrele(ws, r, 4, "Total", bold=True)
    _hucrele(ws, r, 6, round(genel_toplam, 2), bold=True, align="right", number_format="#,##0.00")
    _hucrele(ws, r, 9, 0, bold=True, align="right", number_format="#,##0.00")
    _hucrele(ws, r, 10, round(genel_toplam * 12, 2), bold=True, align="right", number_format="#,##0.00")

    r = ws.max_row + 2
    _hucrele(ws, r, 1, _DISCLAIMER)
    r = ws.max_row + 1
    _hucrele(ws, r, 1, f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    sutun_genislikleri = {
        1: 18, 2: 20, 3: 16, 4: 18, 5: _ACIKLAMA_GENISLIGI,
        6: 22, 7: 14, 8: 22, 9: 22, 10: 22,
    }
    for col, genislik in sutun_genislikleri.items():
        ws.column_dimensions[get_column_letter(col)].width = genislik

    for row_obj in ws.iter_rows(min_row=baslik_satiri + 1, max_col=5, min_col=5):
        for cell in row_obj:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    arabellek = io.BytesIO()
    kitap.save(arabellek)
    return arabellek.getvalue()


def donemsel_rapor_kitabi_olustur(hesaplamalar: list[Any]) -> bytes:
    """Export Tur B — her satir bir onaylanmis hesaplama ozeti."""
    from app.yetkilendirme import departman_etiketi, hesaplama_departmani

    kitap = Workbook()
    ws = kitap.active
    ws.title = "Donemsel Rapor"
    basliklar = [
        "Tarih",
        "Calisan",
        "Birim",
        "Hizmet",
        "Kalem Sayisi",
        "Toplam Tutar",
        "Onaylayan",
        "Onay Tarihi",
    ]
    for col, baslik in enumerate(basliklar, 1):
        _hucrele(ws, 1, col, baslik, bold=True, fill=_BASLIK_DOLGU)

    for h in hesaplamalar:
        dep = hesaplama_departmani(h.olusturan_gruplar, h.olusturan_departman)
        hizmetler = sorted({(k.urun_tipi or "") for k in (h.kalemler or [])})
        onay_t = h.onay_tarihi
        olusturma = h.olusturulma_tarihi
        r = ws.max_row + 1
        _hucrele(ws, r, 1, olusturma.strftime("%Y-%m-%d") if olusturma else "")
        _hucrele(ws, r, 2, h.olusturan_ad_soyad or h.olusturan_kullanici_adi or "")
        _hucrele(ws, r, 3, departman_etiketi(dep) if dep else "")
        _hucrele(ws, r, 4, ", ".join(hizmetler) or h.ad)
        _hucrele(ws, r, 5, len(h.kalemler or []))
        _hucrele(ws, r, 6, round(float(h.toplam_aylik_maliyet or 0), 2), align="right", number_format="#,##0.00")
        _hucrele(ws, r, 7, h.onaylayan_kullanici_adi or "")
        _hucrele(ws, r, 8, onay_t.strftime("%Y-%m-%d") if onay_t else "")

    for col, genislik in enumerate([12, 22, 16, 28, 12, 14, 18, 14], 1):
        ws.column_dimensions[get_column_letter(col)].width = genislik

    arabellek = io.BytesIO()
    kitap.save(arabellek)
    return arabellek.getvalue()
