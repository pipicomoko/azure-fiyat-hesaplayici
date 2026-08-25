"""Onay kuyrugu, iptal, audit log ve raporlar."""

from __future__ import annotations

import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlmodel import Session, select

from app.database import oturum_al
from app.disa_aktar import donemsel_rapor_kitabi_olustur
from app.http_basliklari import ek_dosya_basligi
from app.i18n import istekten_dil_al, t
from app.models import (
    DURUM_IPTAL_EDILDI,
    DURUM_ONAY_BEKLIYOR,
    DURUM_ONAYLANDI,
    DURUM_TASLAK,
    AktiviteKaydi,
    GirisDenemesi,
    Hesaplama,
)
from app.sablonlar import render
from app.sayfalama import VARSAYILAN_SAYFA_BOYUTU, sayfala, sayfa_numarasi
from app.tarih_filtre import bos_tarihleri_doldur
from app.yetkilendirme import (
    IZIN_AUDIT_GOR,
    IZIN_ONAY_ISLEM,
    IZIN_RAPOR_GOR,
    departman_filtre_eslesir,
    departman_secenek_listesi,
    hesaplamaya_erisebilir_mi,
    hesaplamayi_iptal_edebilir_mi,
    kendi_hesaplamasini_isliyor_mu,
    yetki_gerekli,
)

router = APIRouter()


def _onayli_rapor_listesi(
    oturum: Session,
    kullanici: dict,
    *,
    kisi: str = "",
    birim: str = "",
    baslangic: str = "",
    bitis: str = "",
    ids: list[int] | None = None,
) -> list[Hesaplama]:
    tum = oturum.exec(
        select(Hesaplama)
        .where(Hesaplama.durum == DURUM_ONAYLANDI)
        .order_by(Hesaplama.onay_tarihi.desc())
    ).all()
    gorunen = [h for h in tum if hesaplamaya_erisebilir_mi(kullanici, h)]

    if ids:
        id_set = set(ids)
        gorunen = [h for h in gorunen if h.id in id_set]

    kisi_q = (kisi or "").strip().lower()
    birim_q = (birim or "").strip().lower()
    if not ids:
        baslangic, bitis = bos_tarihleri_doldur(baslangic, bitis)
    if kisi_q:
        gorunen = [
            h
            for h in gorunen
            if kisi_q in (h.olusturan_kullanici_adi or "").lower()
            or kisi_q in (h.olusturan_ad_soyad or "").lower()
        ]
    if birim_q:
        gorunen = [
            h for h in gorunen if departman_filtre_eslesir(h.olusturan_departman, birim_q)
        ]
    if baslangic:
        gorunen = [
            h
            for h in gorunen
            if h.onay_tarihi and h.onay_tarihi.strftime("%Y-%m-%d") >= baslangic
        ]
    if bitis:
        gorunen = [
            h
            for h in gorunen
            if h.onay_tarihi and h.onay_tarihi.strftime("%Y-%m-%d") <= bitis
        ]
    return gorunen


def _aktivite(
    oturum: Session,
    aktor: str,
    islem: str,
    hesaplama_id: int | None,
    detay: str | None = None,
) -> None:
    oturum.add(
        AktiviteKaydi(
            aktor_kullanici_adi=aktor,
            islem=islem,
            hesaplama_id=hesaplama_id,
            detay=detay,
        )
    )


@router.get("/onay-kuyrugu")
async def onay_kuyrugu(
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_ONAY_ISLEM)),
    sayfa: str = Query("1"),
    birim: str = Query(""),
    baslangic: str = Query(""),
    bitis: str = Query(""),
):
    dil = istekten_dil_al(request)
    sam = (kullanici.get("kullanici_adi") or "").lower()
    bekleyen = oturum.exec(
        select(Hesaplama)
        .where(Hesaplama.durum == DURUM_ONAY_BEKLIYOR)
        .where(Hesaplama.onay_hedefi == sam)
        .order_by(Hesaplama.olusturulma_tarihi.desc())
    ).all()
    # BUG-03: kendi olusturdugu kayitlar kuyrukta gorunmesin
    bekleyen = [h for h in bekleyen if not kendi_hesaplamasini_isliyor_mu(kullanici, h)]
    birim_q = (birim or "").strip().lower()
    baslangic, bitis = bos_tarihleri_doldur(baslangic, bitis)
    if birim_q:
        bekleyen = [
            h
            for h in bekleyen
            if departman_filtre_eslesir(h.olusturan_departman, birim_q)
        ]
    if baslangic:
        bekleyen = [
            h
            for h in bekleyen
            if h.olusturulma_tarihi
            and h.olusturulma_tarihi.strftime("%Y-%m-%d") >= baslangic
        ]
    if bitis:
        bekleyen = [
            h
            for h in bekleyen
            if h.olusturulma_tarihi
            and h.olusturulma_tarihi.strftime("%Y-%m-%d") <= bitis
        ]
    sayfali, sayfalama = sayfala(
        bekleyen, sayfa_numarasi(sayfa), VARSAYILAN_SAYFA_BOYUTU
    )
    return render(
        request,
        "onay_kuyrugu.html",
        {
            "bekleyenler": sayfali,
            "dil": dil,
            "sayfalama": sayfalama,
            "filtre_birim": birim,
            "filtre_baslangic": baslangic,
            "filtre_bitis": bitis,
            "departman_listesi": departman_secenek_listesi(),
        },
    )


@router.post("/onay/{hesaplama_id}/onayla")
async def onayla(
    hesaplama_id: int,
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_ONAY_ISLEM)),
):
    dil = istekten_dil_al(request)
    hesaplama = oturum.get(Hesaplama, hesaplama_id)
    sam = (kullanici.get("kullanici_adi") or "").lower()
    if (
        hesaplama is None
        or hesaplama.durum != DURUM_ONAY_BEKLIYOR
        or (hesaplama.onay_hedefi or "").lower() != sam
    ):
        return HTMLResponse(t("gecmis_bulunamadi", dil), status_code=404)
    if kendi_hesaplamasini_isliyor_mu(kullanici, hesaplama):
        return HTMLResponse(
            f'<div class="ui-alert ui-alert--danger">{t("onay_kendi_kayit_yasak", dil)}</div>',
            status_code=403,
        )
    hesaplama.durum = DURUM_ONAYLANDI
    hesaplama.onaylayan_kullanici_adi = sam
    hesaplama.onay_tarihi = datetime.now(timezone.utc)
    hesaplama.red_gerekce = None
    hesaplama.reddeden_kullanici_adi = None
    oturum.add(hesaplama)
    _aktivite(oturum, sam, "onaylandi", hesaplama.id, hesaplama.ad)
    oturum.commit()
    return RedirectResponse("/onay-kuyrugu", status_code=303)


@router.post("/onay/{hesaplama_id}/reddet")
async def reddet(
    hesaplama_id: int,
    request: Request,
    gerekce: str = Form(""),
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_ONAY_ISLEM)),
):
    dil = istekten_dil_al(request)
    hesaplama = oturum.get(Hesaplama, hesaplama_id)
    sam = (kullanici.get("kullanici_adi") or "").lower()
    if (
        hesaplama is None
        or hesaplama.durum != DURUM_ONAY_BEKLIYOR
        or (hesaplama.onay_hedefi or "").lower() != sam
    ):
        return HTMLResponse(t("gecmis_bulunamadi", dil), status_code=404)
    if kendi_hesaplamasini_isliyor_mu(kullanici, hesaplama):
        return HTMLResponse(
            f'<div class="ui-alert ui-alert--danger">{t("onay_kendi_kayit_yasak", dil)}</div>',
            status_code=403,
        )
    hesaplama.durum = DURUM_TASLAK
    hesaplama.red_gerekce = (gerekce or "").strip() or None
    hesaplama.reddeden_kullanici_adi = sam
    hesaplama.onay_hedefi = None
    hesaplama.revizyon = int(hesaplama.revizyon or 1) + 1
    oturum.add(hesaplama)
    _aktivite(oturum, sam, "reddedildi", hesaplama.id, hesaplama.red_gerekce)
    oturum.commit()
    return RedirectResponse("/onay-kuyrugu", status_code=303)


@router.post("/gecmis/{hesaplama_id}/iptal")
async def iptal_et(
    hesaplama_id: int,
    request: Request,
    gerekce: str = Form(""),
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_ONAY_ISLEM)),
):
    dil = istekten_dil_al(request)
    hesaplama = oturum.get(Hesaplama, hesaplama_id)
    if hesaplama is None or not hesaplamayi_iptal_edebilir_mi(kullanici, hesaplama):
        return HTMLResponse(t("gecmis_bulunamadi", dil), status_code=403)
    sam = (kullanici.get("kullanici_adi") or "").lower()
    hesaplama.durum = DURUM_IPTAL_EDILDI
    hesaplama.iptal_gerekce = (gerekce or "").strip() or None
    oturum.add(hesaplama)
    _aktivite(oturum, sam, "iptal_edildi", hesaplama.id, hesaplama.iptal_gerekce)
    oturum.commit()
    return RedirectResponse(f"/gecmis/{hesaplama_id}", status_code=303)


@router.get("/admin/aktivite")
async def aktivite_gunlugu(
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_AUDIT_GOR)),
    sayfa: str = Query("1"),
):
    kayitlar = oturum.exec(
        select(AktiviteKaydi).order_by(AktiviteKaydi.olusturulma_tarihi.desc())
    ).all()
    sayfali, sayfalama = sayfala(
        kayitlar, sayfa_numarasi(sayfa), VARSAYILAN_SAYFA_BOYUTU
    )
    return render(
        request, "aktivite.html", {"kayitlar": sayfali, "sayfalama": sayfalama}
    )


@router.get("/admin/giris-gunlugu")
async def giris_gunlugu(
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_AUDIT_GOR)),
    sayfa: str = Query("1"),
):
    kayitlar = oturum.exec(
        select(GirisDenemesi).order_by(GirisDenemesi.olusturulma_tarihi.desc())
    ).all()
    sayfali, sayfalama = sayfala(
        kayitlar, sayfa_numarasi(sayfa), VARSAYILAN_SAYFA_BOYUTU
    )
    return render(
        request,
        "giris_gunlugu.html",
        {"kayitlar": sayfali, "sayfalama": sayfalama},
    )


@router.get("/raporlar")
async def raporlar(
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_RAPOR_GOR)),
    kisi: str = Query(""),
    birim: str = Query(""),
    baslangic: str = Query(""),
    bitis: str = Query(""),
    sayfa: str = Query("1"),
):
    baslangic, bitis = bos_tarihleri_doldur(baslangic, bitis)
    gorunen = _onayli_rapor_listesi(
        oturum,
        kullanici,
        kisi=kisi,
        birim=birim,
        baslangic=baslangic,
        bitis=bitis,
    )
    sayfali, sayfalama = sayfala(
        gorunen, sayfa_numarasi(sayfa), VARSAYILAN_SAYFA_BOYUTU
    )

    return render(
        request,
        "raporlar.html",
        {
            "hesaplamalar": sayfali,
            "filtre_kisi": kisi,
            "filtre_birim": birim,
            "filtre_baslangic": baslangic,
            "filtre_bitis": bitis,
            "sayfalama": sayfalama,
            "departman_listesi": departman_secenek_listesi(),
        },
    )


@router.get("/raporlar/excel")
async def raporlar_excel(
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_RAPOR_GOR)),
    kisi: str = Query(""),
    birim: str = Query(""),
    baslangic: str = Query(""),
    bitis: str = Query(""),
    ids: list[int] = Query(default=[]),
):
    dil = istekten_dil_al(request)
    gorunen = _onayli_rapor_listesi(
        oturum,
        kullanici,
        kisi=kisi,
        birim=birim,
        baslangic=baslangic,
        bitis=bitis,
        ids=ids or None,
    )
    if ids and not gorunen:
        return HTMLResponse(
            f'<div class="alert alert-danger">{t("rapor_secilen_yok", dil)}</div>',
            status_code=400,
        )
    icerik = donemsel_rapor_kitabi_olustur(gorunen)
    zaman = datetime.now().strftime("%Y%m%d-%H%M")
    dosya_adi = f"azure-tahminler-{zaman}.xlsx"
    return StreamingResponse(
        io.BytesIO(icerik),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": ek_dosya_basligi(dosya_adi)},
    )
