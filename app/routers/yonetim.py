from fastapi import APIRouter, Depends, Request

from app.sablonlar import render
from app.yetkilendirme import (
    IZIN_YONETIM_ERISIM,
    YETKI_HARITASI_DOSYASI,
    yetki_gerekli,
    yetki_haritasini_yukle,
)

router = APIRouter()


@router.get("/yonetim")
async def yonetim_ekrani(
    request: Request, kullanici: dict = Depends(yetki_gerekli(IZIN_YONETIM_ERISIM))
):
    harita = yetki_haritasini_yukle()
    return render(
        request,
        "yonetim.html",
        {
            "harita": harita,
            "yetki_dosyasi": str(YETKI_HARITASI_DOSYASI),
        },
    )
