"""Tahmin calisma alani: urun ekleme, alan degisiminde aninda yeniden
hesaplama, kaldirma, kaydetme, Excel'e aktarma ve dil degistirme.

Tum kalemler TEK bir <form id="tahmin-formu"> icinde yasar (bkz.
templates/tahmin.html); her kalemin alanlari `{kalem_id}.{alan}` seklinde
adlandirilir (bkz. app/form_yardimcilari.py). htmx, bir forma ait elemanlarda
varsayilan olarak en yakin formun TUM degerlerini istekle birlikte gonderir;
bu sayede tek bir kalem degisince o kalemi (URL'deki ?kalem_id ile) izole
edip yeniden hesaplayabiliriz, ayni zamanda dil degisimi/kaydetme/disa
aktarim gibi TOPLU islemler de ayni formdan TUM kalemleri toplu okuyabilir.

Fiyat, HER ZAMAN bu istekte yeniden hesaplanir (asla istemciden gelen bir
fiyat degerine guvenilmez) -- boylece "no fabricated price" kurali ve
"Excel'deki rakamlar ekranla birebir tutarli olmali" kurali ayni anda,
tek bir gercek kaynaktan saglanir.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy import or_
from sqlmodel import Session, select

from app.database import oturum_al
from app.disa_aktar import TahminBosHatasi, calisma_kitabi_olustur
from app.fiyat_api import FiyatApiHatasi
from app.form_yardimcilari import (
    bos_degerleri_temizle,
    boolean_alanlarini_normallestir,
    coklu_kalem_formunu_ayir,
)
from app.i18n import DESTEKLENEN_DILLER, DIL_COOKIE_ADI, Dil, form_alanindan_dil_al, istekten_dil_al, t
from app.models import Hesaplama, HesaplamaKalemi
from app.para_birimleri import PARA_BIRIMLERI, VARSAYILAN_PARA_BIRIMI, guvenli_para_birimi
from app.products import KAYITLI_URUNLER, urun_al
from app.products.base import DisaAktarimSatiri, FiyatBulunamadiHatasi, FiyatSonucu, UrunModulu
from app.sablonlar import render, templates
from app.yetkilendirme import (
    IZIN_HESAPLAMA_KULLAN,
    departman_etiketi,
    gecmis_erisim_kapsami,
    gruplardan_departman_belirle,
    hesaplama_departmani,
    hesaplamaya_erisebilir_mi,
    hesaplamayi_silebilir_mi,
    kullanicinin_departmanlari,
    kullanicinin_yonettigi_departmanlar,
    yetki_gerekli,
)

router = APIRouter(prefix="/tahmin")


@dataclass
class _KalemSonucu:
    kalem_id: str
    urun_tipi: str
    urun: UrunModulu
    yapilandirma: dict
    secenekler: dict
    gorunur_alanlar: set
    fiyat: FiyatSonucu | None
    hata: str | None


async def _fiyatla_guvenli(urun: UrunModulu, yapilandirma: dict, para_birimi: str, dil: Dil):
    try:
        return await urun.fiyatla(yapilandirma, para_birimi), None
    except FiyatBulunamadiHatasi:
        return None, t("fiyat_bulunamadi", dil)
    except FiyatApiHatasi:
        return None, t("fiyat_servisi_erisilemez", dil)


async def _kalemi_coz(kalem_id: str, ham_yapilandirma: dict, para_birimi: str, dil: Dil) -> _KalemSonucu | None:
    ham = dict(ham_yapilandirma)
    bos_degerleri_temizle(ham)
    boolean_alanlarini_normallestir(ham)
    urun_tipi = ham.pop("urun_tipi", "")
    urun = urun_al(urun_tipi)
    if urun is None:
        return None

    secenek_sonucu = await urun.secenekleri_getir(ham, dil)
    yapilandirma = secenek_sonucu.yapilandirma
    fiyat, hata = await _fiyatla_guvenli(urun, yapilandirma, para_birimi, dil)
    return _KalemSonucu(
        kalem_id, urun_tipi, urun, yapilandirma, secenek_sonucu.secenekler,
        secenek_sonucu.gorunur_alanlar, fiyat, hata,
    )


async def _tum_kalemleri_coz(kalemler_ham: dict[str, dict], para_birimi: str, dil: Dil) -> list[_KalemSonucu]:
    sonuclar = []
    for kalem_id, ham in kalemler_ham.items():
        sonuc = await _kalemi_coz(kalem_id, ham, para_birimi, dil)
        if sonuc is not None:
            sonuclar.append(sonuc)
    return sonuclar


def _kalem_baglami(kalem_id: str, sonuc: _KalemSonucu, para_birimi: str, dil: Dil) -> dict:
    return {
        "dil": dil,
        "urun": sonuc.urun,
        "urun_tipi": sonuc.urun_tipi,
        "kalem_id": kalem_id,
        "yapilandirma": sonuc.yapilandirma,
        "secenekler": sonuc.secenekler,
        "gorunur_alanlar": sonuc.gorunur_alanlar,
        "para_birimi": para_birimi,
        "fiyat": sonuc.fiyat,
        "hata": sonuc.hata,
    }


@router.get("")
async def tahmin_sayfasi(request: Request, kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN))):
    return render(
        request,
        "tahmin.html",
        {
            "urunler": list(KAYITLI_URUNLER.values()),
            "para_birimleri": PARA_BIRIMLERI,
            "para_birimi": VARSAYILAN_PARA_BIRIMI,
            "tahmin_modu": True,
        },
    )


@router.post("/kalem-ekle")
async def kalem_ekle(request: Request, kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN))):
    form = await request.form()
    urun_tipi = form.get("urun_tipi", "")
    para_birimi = guvenli_para_birimi(form.get("para_birimi"))
    dil = istekten_dil_al(request)

    urun = urun_al(urun_tipi)
    if urun is None:
        return HTMLResponse("", status_code=400)

    kalem_id = uuid.uuid4().hex
    sonuc = await _kalemi_coz(kalem_id, {**urun.bos_yapilandirma(), "urun_tipi": urun_tipi}, para_birimi, dil)
    if sonuc is None:
        return HTMLResponse("", status_code=400)

    return templates.TemplateResponse(request, urun.sablon_adi, _kalem_baglami(kalem_id, sonuc, para_birimi, dil))


@router.post("/kalem/hesapla")
async def kalem_hesapla(request: Request, kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN))):
    kalem_id = request.query_params.get("kalem_id", "")
    form = await request.form()
    genel, kalemler = coklu_kalem_formunu_ayir(form)

    ham = kalemler.get(kalem_id)
    if ham is None:
        return HTMLResponse("", status_code=400)

    para_birimi = guvenli_para_birimi(genel.get("para_birimi"))
    dil = form_alanindan_dil_al(genel.get("dil")) if genel.get("dil") in DESTEKLENEN_DILLER else istekten_dil_al(request)

    sonuc = await _kalemi_coz(kalem_id, ham, para_birimi, dil)
    if sonuc is None:
        return HTMLResponse("", status_code=400)

    return templates.TemplateResponse(request, sonuc.urun.sablon_adi, _kalem_baglami(kalem_id, sonuc, para_birimi, dil))


@router.post("/dil-degistir")
async def dil_degistir_tahmin(request: Request, kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN))):
    form = await request.form()
    genel, kalemler_ham = coklu_kalem_formunu_ayir(form)

    yeni_dil = form_alanindan_dil_al(genel.get("dil"))
    para_birimi = guvenli_para_birimi(genel.get("para_birimi"))

    kalem_sonuclari = await _tum_kalemleri_coz(kalemler_ham, para_birimi, yeni_dil)

    baglam = {
        "dil": yeni_dil,
        "kullanici": request.session.get("kullanici"),
        "urunler": list(KAYITLI_URUNLER.values()),
        "para_birimleri": PARA_BIRIMLERI,
        "para_birimi": para_birimi,
        "kalem_sonuclari": [(k.kalem_id, k) for k in kalem_sonuclari],
        "tahmin_modu": True,
    }
    # Ana icerigi VE nav'i (dil etiketleri icin out-of-band swap olarak) ayni
    # yanitta doner -- boylece tek istekte hem tahmin hem de sayfa govdesindeki
    # sabit metinler yeni dile gecer, tahmin ASLA kaybolmaz.
    icerik_html = templates.env.get_template("_tahmin_ic_icerik.html").render(request=request, **baglam)
    nav_html = templates.env.get_template("_nav.html").render(request=request, oob=True, **baglam)

    yanit = HTMLResponse(icerik_html + nav_html)
    yanit.set_cookie(DIL_COOKIE_ADI, yeni_dil, max_age=60 * 60 * 24 * 365, samesite="lax")
    return yanit


@router.post("/kaydet")
async def tahmin_kaydet(
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN)),
):
    dil = istekten_dil_al(request)
    form = await request.form()
    genel, kalemler_ham = coklu_kalem_formunu_ayir(form)
    para_birimi = guvenli_para_birimi(genel.get("para_birimi"))
    hesaplama_adi = (genel.get("hesaplama_adi") or "").strip()

    if not hesaplama_adi:
        return HTMLResponse(f'<div class="alert alert-danger">{t("kaydet_ad_gerekli", dil)}</div>', status_code=400)
    if not kalemler_ham:
        return HTMLResponse(f'<div class="alert alert-danger">{t("kaydet_bos_sepet", dil)}</div>', status_code=400)

    kalem_sonuclari = await _tum_kalemleri_coz(kalemler_ham, para_birimi, dil)
    if not kalem_sonuclari or any(k.hata for k in kalem_sonuclari):
        return HTMLResponse(f'<div class="alert alert-danger">{t("fiyat_bulunamadi", dil)}</div>', status_code=400)

    departman_anahtari = kullanici.get("departman")
    if not departman_anahtari:
        departman_anahtari, _ = gruplardan_departman_belirle(kullanici.get("gruplar"))
    hesaplama = Hesaplama(
        ad=hesaplama_adi,
        para_birimi=para_birimi,
        toplam_aylik_maliyet=0.0,
        olusturan_kullanici_adi=kullanici["kullanici_adi"],
        olusturan_gruplar=list(kullanici.get("gruplar", [])),
        olusturan_departman=departman_anahtari,
    )
    oturum.add(hesaplama)
    oturum.flush()

    toplam = 0.0
    for k in kalem_sonuclari:
        toplam += k.fiyat.aylik_toplam
        kalem = HesaplamaKalemi(
            hesaplama_id=hesaplama.id,
            urun_tipi=k.urun_tipi,
            ozet=k.urun.ozet(k.yapilandirma, dil),
            aylik_maliyet=k.fiyat.aylik_toplam,
            yapilandirma=k.yapilandirma,
            fiyat_kalemleri=[vars(kalem_kaydi) for kalem_kaydi in k.fiyat.kalemler],
        )
        oturum.add(kalem)

    hesaplama.toplam_aylik_maliyet = toplam
    oturum.add(hesaplama)
    oturum.commit()

    return HTMLResponse(
        f'<a href="/gecmis" class="kaydet-basari-banner">'
        f'<span class="kaydet-basari-icon">✓</span>'
        f'<span>"{hesaplama_adi}" {t("kaydet_basarili", dil)}</span>'
        f'</a>'
    )


@router.post("/disa-aktar")
async def tahmin_disa_aktar(request: Request, kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN))):
    dil = istekten_dil_al(request)
    form = await request.form()
    genel, kalemler_ham = coklu_kalem_formunu_ayir(form)
    para_birimi = guvenli_para_birimi(genel.get("para_birimi"))

    if not kalemler_ham:
        return HTMLResponse(f'<div class="alert alert-danger">{t("disa_aktar_bos_hata", dil)}</div>', status_code=400)

    kalem_sonuclari = await _tum_kalemleri_coz(kalemler_ham, para_birimi, dil)
    if not kalem_sonuclari or any(k.hata for k in kalem_sonuclari):
        return HTMLResponse(f'<div class="alert alert-danger">{t("fiyat_bulunamadi", dil)}</div>', status_code=400)

    satirlar: list[DisaAktarimSatiri] = []
    genel_toplam = 0.0
    for k in kalem_sonuclari:
        satirlar.extend(k.urun.disa_aktarim_satirlari(k.yapilandirma, k.fiyat, dil))
        genel_toplam += k.fiyat.aylik_toplam

    try:
        icerik = calisma_kitabi_olustur(satirlar, genel_toplam, para_birimi, dil)
    except TahminBosHatasi:
        return HTMLResponse(f'<div class="alert alert-danger">{t("disa_aktar_bos_hata", dil)}</div>', status_code=400)

    dosya_adi = f"azure-tahmin-{datetime.now().strftime('%Y%m%d-%H%M')}.xlsx"
    return StreamingResponse(
        io.BytesIO(icerik),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{dosya_adi}"'},
    )


gecmis_router = APIRouter()


@gecmis_router.get("/gecmis")
async def gecmis_listesi(
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN)),
):
    sorgu = select(Hesaplama).order_by(Hesaplama.olusturulma_tarihi.desc())
    kapsam = gecmis_erisim_kapsami(kullanici)
    if kapsam == "kendi":
        sorgu = sorgu.where(Hesaplama.olusturan_kullanici_adi == kullanici["kullanici_adi"])
        hesaplamalar = oturum.exec(sorgu).all()
    elif kapsam == "departman":
        departmanlar = list(kullanicinin_yonettigi_departmanlar(kullanici))
        if departmanlar:
            sorgu = sorgu.where(
                or_(
                    Hesaplama.olusturan_kullanici_adi == kullanici["kullanici_adi"],
                    Hesaplama.olusturan_departman.in_(departmanlar),
                )
            )
        else:
            # Departman belirlenemedi — sadece kendi kayıtları
            sorgu = sorgu.where(Hesaplama.olusturan_kullanici_adi == kullanici["kullanici_adi"])
        hesaplamalar = [
            hesaplama
            for hesaplama in oturum.exec(sorgu).all()
            if hesaplamaya_erisebilir_mi(kullanici, hesaplama)
        ]
    else:
        hesaplamalar = oturum.exec(sorgu).all()

    # Tüm kapsam seviyeleri için gruplu görünüm oluştur.
    # Kullanıcının kendi kayıtları her zaman "personal" grubunda; diğerleri departmana göre.
    kovalar: dict[str, dict] = {}
    PERSONAL_KEY = "personal"

    for hesaplama in hesaplamalar:
        sahip = (hesaplama.olusturan_kullanici_adi or "").lower() == (kullanici.get("kullanici_adi") or "").lower()
        if sahip:
            anahtar = PERSONAL_KEY
            etiket = "Personal"
        else:
            anahtar = hesaplama_departmani(hesaplama.olusturan_gruplar, hesaplama.olusturan_departman) or "diger"
            etiket = departman_etiketi(anahtar)
        if anahtar not in kovalar:
            kovalar[anahtar] = {"anahtar": anahtar, "etiket": etiket, "hesaplamalar": []}
        kovalar[anahtar]["hesaplamalar"].append(hesaplama)

    # Personal en üste, sonra departmanlar alfabetik
    gecmis_gruplari = []
    if PERSONAL_KEY in kovalar:
        gecmis_gruplari.append(kovalar.pop(PERSONAL_KEY))
    gecmis_gruplari.extend(sorted(kovalar.values(), key=lambda g: g["etiket"]))

    return render(
        request,
        "gecmis.html",
        {
            "hesaplamalar": hesaplamalar,
            "gecmis_gruplari": gecmis_gruplari,
            "gecmis_gorunumu": kapsam,
        },
    )


@gecmis_router.get("/gecmis/{hesaplama_id}")
async def gecmis_detay(
    hesaplama_id: int,
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN)),
):
    dil = istekten_dil_al(request)
    hesaplama = oturum.get(Hesaplama, hesaplama_id)
    if hesaplama is None:
        return HTMLResponse(f'<div class="alert alert-danger">{t("gecmis_bulunamadi", dil)}</div>', status_code=404)
    if not hesaplamaya_erisebilir_mi(kullanici, hesaplama):
        return HTMLResponse(
            f'<div class="alert alert-danger">{t("gecmis_yalnizca_sahibi_erisebilir", dil)}</div>', status_code=403
        )

    return render(
        request,
        "gecmis_detay.html",
        {"hesaplama": hesaplama, "gecmis_gorunumu": gecmis_erisim_kapsami(kullanici)},
    )


def _hesaplamadan_satirlar(hesaplama) -> tuple[list[DisaAktarimSatiri], float]:
    """Kaydedilmis bir Hesaplama nesnesinden DisaAktarimSatiri listesi uretir."""
    satirlar: list[DisaAktarimSatiri] = []
    for kalem in hesaplama.kalemler:
        for b in (kalem.fiyat_kalemleri or []):
            if isinstance(b, dict):
                satirlar.append(DisaAktarimSatiri(
                    urun=kalem.urun_tipi or "",
                    yapilandirma_ozeti=kalem.ozet or "",
                    bolge=b.get("bolge", ""),
                    miktar=float(b.get("miktar", 0)),
                    birim=b.get("birim", ""),
                    birim_fiyat=float(b.get("birim_fiyat", 0)),
                    ara_toplam=float(b.get("aylik_tutar", 0)),
                ))
    return satirlar, hesaplama.toplam_aylik_maliyet


@gecmis_router.get("/gecmis/{hesaplama_id}/excel")
async def gecmis_detay_excel(
    hesaplama_id: int,
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN)),
):
    dil = istekten_dil_al(request)
    hesaplama = oturum.get(Hesaplama, hesaplama_id)
    if hesaplama is None or not hesaplamaya_erisebilir_mi(kullanici, hesaplama):
        return HTMLResponse(f'<div class="alert alert-danger">{t("gecmis_bulunamadi", dil)}</div>', status_code=404)
    satirlar, toplam = _hesaplamadan_satirlar(hesaplama)
    try:
        icerik = calisma_kitabi_olustur(satirlar, toplam, hesaplama.para_birimi, dil)
    except TahminBosHatasi:
        return HTMLResponse(f'<div class="alert alert-danger">{t("disa_aktar_bos_hata", dil)}</div>', status_code=400)
    dosya_adi = f"azure-tahmin-{hesaplama.ad}-{hesaplama.olusturulma_tarihi.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        io.BytesIO(icerik),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{dosya_adi}"'},
    )


@gecmis_router.get("/gecmis-excel")
async def gecmis_tumu_excel(
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN)),
):
    """Kullanicinin gorebilecegi tum hesaplamalari tek bir Excel dosyasina aktarir."""
    dil = istekten_dil_al(request)
    from sqlalchemy import or_
    from app.yetkilendirme import gecmis_erisim_kapsami, kullanicinin_yonettigi_departmanlar

    kapsam = gecmis_erisim_kapsami(kullanici)
    sorgu = select(Hesaplama).order_by(Hesaplama.olusturulma_tarihi.desc())
    if kapsam == "kendi":
        sorgu = sorgu.where(Hesaplama.olusturan_kullanici_adi == kullanici["kullanici_adi"])
        hesaplamalar = oturum.exec(sorgu).all()
    elif kapsam == "departman":
        departmanlar = list(kullanicinin_yonettigi_departmanlar(kullanici))
        if departmanlar:
            sorgu = sorgu.where(or_(
                Hesaplama.olusturan_kullanici_adi == kullanici["kullanici_adi"],
                Hesaplama.olusturan_departman.in_(departmanlar),
            ))
        else:
            sorgu = sorgu.where(Hesaplama.olusturan_kullanici_adi == kullanici["kullanici_adi"])
        hesaplamalar = [h for h in oturum.exec(sorgu).all() if hesaplamaya_erisebilir_mi(kullanici, h)]
    else:
        hesaplamalar = oturum.exec(sorgu).all()

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    kitap = Workbook()
    kitap.remove(kitap.active)

    for hesaplama in hesaplamalar:
        sayfa_adi = hesaplama.ad[:31] if hesaplama.ad else str(hesaplama.id)
        sayfa = kitap.create_sheet(title=sayfa_adi)
        basliklar = [t("xlsx_urun", dil), t("xlsx_ozet", dil), t("xlsx_bolge", dil),
                     t("xlsx_miktar", dil), t("xlsx_birim", dil), t("xlsx_birim_fiyat", dil), t("xlsx_ara_toplam", dil)]
        sayfa.append(basliklar)
        for hucre in sayfa[1]:
            hucre.font = Font(bold=True)
        satirlar, toplam = _hesaplamadan_satirlar(hesaplama)
        for s in satirlar:
            sayfa.append([s.urun, s.yapilandirma_ozeti, s.bolge, round(s.miktar, 4),
                          s.birim, round(s.birim_fiyat, 6), round(s.ara_toplam, 2)])
        sayfa.append([])
        sayfa.append([t("xlsx_genel_toplam", dil), "", "", "", "", "", round(toplam, 2)])
        for hucre in sayfa[sayfa.max_row]:
            hucre.font = Font(bold=True)
        sayfa.append([t("xlsx_genel_toplam_yillik", dil), "", "", "", "", "", round(toplam * 12, 2)])
        for hucre in sayfa[sayfa.max_row]:
            hucre.font = Font(bold=True)
        sayfa.append([t("xlsx_para_birimi", dil), hesaplama.para_birimi])
        olusturan = hesaplama.olusturan_kullanici_adi or ""
        if olusturan:
            sayfa.append([t("olusturan", dil), olusturan])
        for sutun_index in range(1, len(basliklar) + 1):
            harf = get_column_letter(sutun_index)
            genislik = max(14, min(48, max(len(str(h.value or "")) for h in sayfa[harf]) + 2))
            sayfa.column_dimensions[harf].width = genislik

    if not kitap.sheetnames:
        kitap.create_sheet("Bos")

    arabellek = io.BytesIO()
    kitap.save(arabellek)
    dosya_adi = f"azure-tahminler-{datetime.now().strftime('%Y%m%d-%H%M')}.xlsx"
    return StreamingResponse(
        io.BytesIO(arabellek.getvalue()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{dosya_adi}"'},
    )


@gecmis_router.post("/gecmis/{hesaplama_id}/sil")
async def gecmis_sil(
    hesaplama_id: int,
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN)),
):
    dil = istekten_dil_al(request)
    hesaplama = oturum.get(Hesaplama, hesaplama_id)
    if hesaplama is None:
        return HTMLResponse(f'<div class="alert alert-danger">{t("gecmis_bulunamadi", dil)}</div>', status_code=404)
    if not hesaplamayi_silebilir_mi(kullanici, hesaplama):
        return HTMLResponse(
            f'<div class="alert alert-danger">{t("gecmis_yalnizca_sahibi_erisebilir", dil)}</div>', status_code=403
        )

    oturum.delete(hesaplama)
    oturum.commit()
    return RedirectResponse("/gecmis", status_code=303)
