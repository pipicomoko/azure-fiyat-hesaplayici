"""Ana sayfa panosu: kullanicinin hesaplama durum ozeti."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import oturum_al
from app.models import DURUM_ONAY_BEKLIYOR, Hesaplama
from app.sablonlar import render
from app.yetkilendirme import (
    IZIN_HESAPLAMA_KULLAN,
    IZIN_ONAY_ISLEM,
    hesaplama_gorunen_durum,
    kullanici_izinli_mi,
    yetki_gerekli,
)

router = APIRouter()


def _ozet_satirlari(kayitlar: list[Hesaplama], limit: int = 5) -> list[Hesaplama]:
    return sorted(kayitlar, key=lambda h: h.olusturulma_tarihi or h.id, reverse=True)[:limit]


@router.get("/")
async def pano(
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN)),
):
    sam = (kullanici.get("kullanici_adi") or "").lower()
    tum = oturum.exec(
        select(Hesaplama).where(Hesaplama.olusturan_kullanici_adi == sam)
    ).all()

    taslaklar: list[Hesaplama] = []
    gonderilenler: list[Hesaplama] = []
    onaylananlar: list[Hesaplama] = []
    reddedilenler: list[Hesaplama] = []

    for h in tum:
        gorunen = hesaplama_gorunen_durum(h)
        if gorunen == "taslak":
            taslaklar.append(h)
        elif gorunen == "onay_bekliyor":
            gonderilenler.append(h)
        elif gorunen == "onaylandi":
            onaylananlar.append(h)
        elif gorunen == "reddedildi":
            reddedilenler.append(h)

    def _toplam(kayitlar: list[Hesaplama]) -> float:
        return round(sum(float(h.toplam_aylik_maliyet or 0) for h in kayitlar), 2)

    bekleyen_onay_sayisi = 0
    if kullanici_izinli_mi(kullanici, IZIN_ONAY_ISLEM):
        bekleyen_onay_sayisi = len(
            oturum.exec(
                select(Hesaplama)
                .where(Hesaplama.durum == DURUM_ONAY_BEKLIYOR)
                .where(Hesaplama.onay_hedefi == sam)
            ).all()
        )

    return render(
        request,
        "pano.html",
        {
            "kartlar": [
                {
                    "anahtar": "taslak",
                    "baslik_anahtar": "durum_taslak",
                    "adet": len(taslaklar),
                    "toplam": _toplam(taslaklar),
                    "kayitlar": _ozet_satirlari(taslaklar),
                    "rozet": "default",
                    "filtre": "taslak",
                },
                {
                    "anahtar": "gonderilen",
                    "baslik_anahtar": "durum_onay_bekliyor",
                    "adet": len(gonderilenler),
                    "toplam": _toplam(gonderilenler),
                    "kayitlar": _ozet_satirlari(gonderilenler),
                    "rozet": "info",
                    "filtre": "onay_bekliyor",
                },
                {
                    "anahtar": "onaylanan",
                    "baslik_anahtar": "durum_onaylandi",
                    "adet": len(onaylananlar),
                    "toplam": _toplam(onaylananlar),
                    "kayitlar": _ozet_satirlari(onaylananlar),
                    "rozet": "success",
                    "filtre": "onaylandi",
                },
                {
                    "anahtar": "reddedilen",
                    "baslik_anahtar": "durum_reddedildi",
                    "adet": len(reddedilenler),
                    "toplam": _toplam(reddedilenler),
                    "kayitlar": _ozet_satirlari(reddedilenler),
                    "rozet": "warning",
                    "filtre": "reddedildi",
                },
            ],
            "bekleyen_onay_sayisi": bekleyen_onay_sayisi,
            "toplam_kayit": len(tum),
        },
    )
