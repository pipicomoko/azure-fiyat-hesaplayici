from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.i18n import DIL_COOKIE_ADI, form_alanindan_dil_al, istekten_dil_al, t
from app.sablonlar import render
from app.yetkilendirme import LdapTlsHatasi, giris_dogrula

router = APIRouter()


@router.get("/giris")
async def giris_ekrani(request: Request):
    return render(request, "giris.html", {"hata": None})


@router.post("/giris")
async def giris_yap(
    request: Request,
    kullanici_adi: str = Form(...),
    sifre: str = Form(...),
):
    try:
        sonuc = await run_in_threadpool(giris_dogrula, kullanici_adi, sifre)
    except LdapTlsHatasi:
        return render(
            request,
            "giris.html",
            {"hata": t("giris_tls_hata", istekten_dil_al(request))},
            durum_kodu=503,
        )
    if sonuc is None:
        return render(
            request,
            "giris.html",
            {"hata": t("giris_hata", istekten_dil_al(request))},
            durum_kodu=401,
        )

    request.session["kullanici"] = sonuc
    return RedirectResponse("/tahmin", status_code=303)


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
    yanit = RedirectResponse(
        request.headers.get("referer", "/"),
        status_code=303,
    )
    yanit.set_cookie(DIL_COOKIE_ADI, secilen_dil, max_age=60 * 60 * 24 * 365, samesite="lax")
    return yanit
