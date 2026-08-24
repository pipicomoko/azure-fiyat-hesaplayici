from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from app.database import oturum_al
from app.guvenlik import (
    giris_basarili_temizle,
    giris_basarisiz_kaydet,
    giris_hiz_siniri_asildi_mi,
    istemci_ip,
    yerel_yonlendirme_yolu,
)
from app.i18n import DIL_COOKIE_ADI, form_alanindan_dil_al, istekten_dil_al, t
from app.models import (
    GIRIS_SONUC_BASARILI,
    GIRIS_SONUC_BASARISIZ,
    GIRIS_SONUC_KILITLI,
    GirisDenemesi,
)
from app.sablonlar import render
from app.yapilandirma import uretim_ortami_mi
from app.yetkilendirme import LdapTlsHatasi, giris_dogrula, giris_sonrasi_yol

router = APIRouter()

GIRIS_GUNLUGU_SAKLAMA_GUN = 90
_GIRIS_TEMIZLIK_SAYAC = 0


def _giris_denemesi_yaz(
    oturum: Session,
    *,
    kullanici_adi: str,
    ip: str,
    sonuc: str,
    hata_tipi: str | None = None,
) -> None:
    """Sifre yazilmaz. Her ~20 kayitta 90 gunden eski satirlari siler."""
    global _GIRIS_TEMIZLIK_SAYAC
    oturum.add(
        GirisDenemesi(
            kullanici_adi=(kullanici_adi or "").strip()[:128],
            ip=(ip or "")[:64],
            sonuc=sonuc,
            hata_tipi=hata_tipi,
        )
    )
    oturum.commit()
    _GIRIS_TEMIZLIK_SAYAC += 1
    if _GIRIS_TEMIZLIK_SAYAC % 20 != 0:
        return
    esik = datetime.now(timezone.utc) - timedelta(days=GIRIS_GUNLUGU_SAKLAMA_GUN)
    eski = oturum.exec(
        select(GirisDenemesi).where(GirisDenemesi.olusturulma_tarihi < esik)
    ).all()
    for kayit in eski:
        oturum.delete(kayit)
    if eski:
        oturum.commit()


@router.get("/giris")
async def giris_ekrani(request: Request):
    kullanici = request.session.get("kullanici")
    if kullanici:
        return RedirectResponse(giris_sonrasi_yol(kullanici), status_code=303)
    return render(request, "giris.html", {"hata": None})


@router.post("/giris")
async def giris_yap(
    request: Request,
    kullanici_adi: str = Form(...),
    sifre: str = Form(...),
    oturum: Session = Depends(oturum_al),
):
    ip = istemci_ip(request)
    dil = istekten_dil_al(request)
    if giris_hiz_siniri_asildi_mi(ip, kullanici_adi):
        _giris_denemesi_yaz(
            oturum,
            kullanici_adi=kullanici_adi,
            ip=ip,
            sonuc=GIRIS_SONUC_KILITLI,
            hata_tipi="hiz_siniri",
        )
        return render(
            request,
            "giris.html",
            {"hata": t("giris_hiz_siniri", dil)},
            durum_kodu=429,
        )

    try:
        sonuc = await run_in_threadpool(giris_dogrula, kullanici_adi, sifre)
    except LdapTlsHatasi:
        giris_basarisiz_kaydet(ip, kullanici_adi)
        _giris_denemesi_yaz(
            oturum,
            kullanici_adi=kullanici_adi,
            ip=ip,
            sonuc=GIRIS_SONUC_BASARISIZ,
            hata_tipi="ldap_tls",
        )
        return render(
            request,
            "giris.html",
            {"hata": t("giris_tls_hata", dil)},
            durum_kodu=503,
        )
    if sonuc is None:
        giris_basarisiz_kaydet(ip, kullanici_adi)
        _giris_denemesi_yaz(
            oturum,
            kullanici_adi=kullanici_adi,
            ip=ip,
            sonuc=GIRIS_SONUC_BASARISIZ,
            hata_tipi="yanlis_sifre",
        )
        return render(
            request,
            "giris.html",
            {"hata": t("giris_hata", dil)},
            durum_kodu=401,
        )

    giris_basarili_temizle(ip, kullanici_adi)
    _giris_denemesi_yaz(
        oturum, kullanici_adi=kullanici_adi, ip=ip, sonuc=GIRIS_SONUC_BASARILI
    )
    request.session["kullanici"] = sonuc
    return RedirectResponse(giris_sonrasi_yol(sonuc), status_code=303)


@router.get("/cikis")
async def cikis_yap(request: Request):
    request.session.clear()
    return RedirectResponse("/giris", status_code=303)


@router.post("/dil")
async def dil_degistir(request: Request, dil: str = Form(...)):
    """Dil tercihini bir cookie'de kalici hale getirir. Sayfa icerigi ayrica
    her istek uzerinden yeniden render edildigi icin (bkz. app/sablonlar.py),
    dil degisimi sayfadaki mevcut tahmin durumunu ETKILEMEZ -- cagiran taraf
    (tahmin sayfasi) tum kalemleri ayni istekte gonderip formu yeniden cizdirir."""
    secilen_dil = form_alanindan_dil_al(dil)
    # Tarayici Referer mutlak URL gonderir; ayni Host path'i korunur (YENI-01)
    hedef = yerel_yonlendirme_yolu(
        request.headers.get("referer"),
        "/",
        izinli_host=request.headers.get("host") or request.url.netloc,
    )
    yanit = RedirectResponse(hedef, status_code=303)
    yanit.set_cookie(
        DIL_COOKIE_ADI,
        secilen_dil,
        max_age=60 * 60 * 24 * 365,
        samesite="lax",
        secure=uretim_ortami_mi(),
    )
    return yanit
