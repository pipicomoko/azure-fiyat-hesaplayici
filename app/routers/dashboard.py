"""Ana sayfa panosu: kullanicinin hesaplama durum ozeti."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session, select

from app.database import oturum_al
from app.models import (
    DURUM_ONAY_BEKLIYOR,
    DURUM_ONAYLANDI,
    DURUM_TASLAK,
    AktiviteKaydi,
    Hesaplama,
)
from app.sablonlar import render
from app.yetkilendirme import (
    IZIN_HESAPLAMA_KULLAN,
    IZIN_ONAY_ISLEM,
    departman_basi_alt_kademe_mi,
    departman_basi_mi,
    departman_etiketi,
    hesaplama_gorunen_durum,
    genel_mudur_mu,
    kullanici_izinli_mi,
    yetki_gerekli,
)

router = APIRouter()

ANA_DEPARTMANLAR = {
    "it": "IT",
    "finans": "Finans",
    "muhasebe": "Muhasebe",
    "ik": "İK",
    "lojistik": "Lojistik",
}


def _tarih_coz(ham: str, varsayilan: date) -> tuple[date, bool]:
    if not ham:
        return varsayilan, True
    try:
        return date.fromisoformat(ham), True
    except ValueError:
        return varsayilan, False


def _kayit_tarihi(hesaplama: Hesaplama) -> date:
    zaman = (
        hesaplama.onay_tarihi
        if hesaplama.durum == DURUM_ONAYLANDI
        else hesaplama.olusturulma_tarihi
    )
    return (zaman or datetime.min).date()


def _ana_departman(anahtar: str | None) -> str | None:
    if not anahtar:
        return None
    return "it" if anahtar == "it" or anahtar.startswith("it-") else anahtar


def _genel_mudur_kapsaminda(kullanici: dict, hesaplama: Hesaplama) -> bool:
    sam = (kullanici.get("kullanici_adi") or "").lower()
    if (hesaplama.olusturan_kullanici_adi or "").lower() == sam:
        return True
    zincir = {str(x).lower() for x in (hesaplama.olusturan_manager_zinciri or [])}
    return sam in zincir


def _ay_baslangici(tarih: date, geri: int = 0) -> date:
    toplam = tarih.year * 12 + tarih.month - 1 - geri
    return date(toplam // 12, toplam % 12 + 1, 1)


def _genel_mudur_baglami(
    tum: list[Hesaplama],
    aktiviteler: list[AktiviteKaydi],
    kullanici: dict,
    baslangic_ham: str,
    bitis_ham: str,
) -> dict:
    bugun = date.today()
    ay_ilk = bugun.replace(day=1)
    ay_son = bugun.replace(day=monthrange(bugun.year, bugun.month)[1])
    baslangic, bas_ok = _tarih_coz(baslangic_ham, ay_ilk)
    bitis, bit_ok = _tarih_coz(bitis_ham, ay_son)
    tarih_hatasi = not bas_ok or not bit_ok or baslangic > bitis
    if tarih_hatasi:
        baslangic, bitis = ay_ilk, ay_son

    kapsam = [h for h in tum if _genel_mudur_kapsaminda(kullanici, h)]
    donem = [h for h in kapsam if baslangic <= _kayit_tarihi(h) <= bitis]
    onayli = [h for h in donem if h.durum == DURUM_ONAYLANDI]
    bekleyen = [h for h in donem if h.durum == DURUM_ONAY_BEKLIYOR]
    kapsam_idleri = {h.id for h in kapsam if h.id is not None}
    donem_aktiviteleri = [
        a
        for a in aktiviteler
        if a.hesaplama_id in kapsam_idleri
        and baslangic <= (a.olusturulma_tarihi or datetime.min).date() <= bitis
    ]
    reddedilen_adet = sum(a.islem == "reddedildi" for a in donem_aktiviteleri)
    iptal_adet = sum(a.islem == "iptal_edildi" for a in donem_aktiviteleri)

    def para_toplamlari(kayitlar: list[Hesaplama]) -> list[dict]:
        toplamlar: dict[str, float] = defaultdict(float)
        for h in kayitlar:
            toplamlar[h.para_birimi or "USD"] += float(h.toplam_aylik_maliyet or 0)
        return [
            {"para_birimi": p, "toplam": round(v, 2)}
            for p, v in sorted(toplamlar.items())
        ]

    departmanlar = []
    for anahtar, etiket in ANA_DEPARTMANLAR.items():
        kayitlar = [
            h for h in onayli if _ana_departman(h.olusturan_departman) == anahtar
        ]
        sorgu = urlencode(
            {
                "birim": anahtar,
                "baslangic": baslangic.isoformat(),
                "bitis": bitis.isoformat(),
            }
        )
        departmanlar.append(
            {
                "anahtar": anahtar,
                "etiket": etiket,
                "adet": len(kayitlar),
                "toplamlar": para_toplamlari(kayitlar),
                "rapor_url": f"/raporlar?{sorgu}",
            }
        )

    aylar = [_ay_baslangici(bugun, geri) for geri in reversed(range(12))]
    para_birimleri = sorted(
        {h.para_birimi or "USD" for h in kapsam if h.durum == DURUM_ONAYLANDI}
    )
    trendler = []
    for para in para_birimleri:
        degerler = []
        for ay in aylar:
            sonraki = _ay_baslangici(ay, -1)
            degerler.append(
                round(
                    sum(
                        float(h.toplam_aylik_maliyet or 0)
                        for h in kapsam
                        if h.durum == DURUM_ONAYLANDI
                        and (h.para_birimi or "USD") == para
                        and ay <= _kayit_tarihi(h) < sonraki
                    ),
                    2,
                )
            )
        en_yuksek = max(degerler, default=0) or 1
        noktalar_liste = [
            {"x": 20 + i * 50, "y": round(170 - (deger / en_yuksek * 140), 1)}
            for i, deger in enumerate(degerler)
        ]
        trendler.append(
            {
                "para_birimi": para,
                "noktalar": " ".join(f"{n['x']},{n['y']}" for n in noktalar_liste),
                "noktalar_liste": noktalar_liste,
                "aylar": [
                    {"etiket": ay.strftime("%m.%Y"), "toplam": deger}
                    for ay, deger in zip(aylar, degerler)
                ],
            }
        )

    sam = (kullanici.get("kullanici_adi") or "").lower()
    dogrudan_bekleyen = sorted(
        [
            h
            for h in kapsam
            if h.durum == DURUM_ONAY_BEKLIYOR and (h.onay_hedefi or "").lower() == sam
        ],
        key=lambda h: h.olusturulma_tarihi or datetime.min,
        reverse=True,
    )
    sirali_onayli = sorted(
        onayli, key=lambda h: float(h.toplam_aylik_maliyet or 0), reverse=True
    )
    son_kayitlar = sorted(
        [h for h in kapsam if h.durum != DURUM_TASLAK],
        key=lambda h: h.onay_tarihi or h.olusturulma_tarihi or datetime.min,
        reverse=True,
    )
    return {
        "baslangic": baslangic.isoformat(),
        "bitis": bitis.isoformat(),
        "tarih_hatasi": tarih_hatasi,
        "onayli_adet": len(onayli),
        "onayli_toplamlar": para_toplamlari(onayli),
        "bekleyen_adet": len(bekleyen),
        "bekleyen_toplamlar": para_toplamlari(bekleyen),
        "reddedilen_adet": reddedilen_adet,
        "iptal_adet": iptal_adet,
        "departmanlar": departmanlar,
        "trendler": trendler,
        "dogrudan_bekleyenler": dogrudan_bekleyen[:5],
        "en_yuksek_kayitlar": sirali_onayli[:5],
        "son_kayitlar": son_kayitlar[:8],
    }


def _departman_basi_baglami(
    tum: list[Hesaplama],
    aktiviteler: list[AktiviteKaydi],
    kullanici: dict,
    baslangic_ham: str,
    bitis_ham: str,
) -> dict:
    bugun = date.today()
    ay_ilk = bugun.replace(day=1)
    ay_son = bugun.replace(day=monthrange(bugun.year, bugun.month)[1])
    baslangic, bas_ok = _tarih_coz(baslangic_ham, ay_ilk)
    bitis, bit_ok = _tarih_coz(bitis_ham, ay_son)
    tarih_hatasi = not bas_ok or not bit_ok or baslangic > bitis
    if tarih_hatasi:
        baslangic, bitis = ay_ilk, ay_son

    kapsam = [h for h in tum if _genel_mudur_kapsaminda(kullanici, h)]
    donem = [h for h in kapsam if baslangic <= _kayit_tarihi(h) <= bitis]
    onayli = [h for h in donem if h.durum == DURUM_ONAYLANDI]
    bekleyen = [h for h in donem if h.durum == DURUM_ONAY_BEKLIYOR]

    def para_toplamlari(kayitlar: list[Hesaplama]) -> list[dict]:
        toplamlar: dict[str, float] = defaultdict(float)
        for h in kayitlar:
            toplamlar[h.para_birimi or "USD"] += float(h.toplam_aylik_maliyet or 0)
        return [
            {"para_birimi": para, "toplam": round(toplam, 2)}
            for para, toplam in sorted(toplamlar.items())
        ]

    kapsam_idleri = {h.id for h in kapsam if h.id is not None}
    donem_aktiviteleri = [
        a
        for a in aktiviteler
        if a.hesaplama_id in kapsam_idleri
        and baslangic <= (a.olusturulma_tarihi or datetime.min).date() <= bitis
    ]

    aylar = [_ay_baslangici(bugun, geri) for geri in reversed(range(12))]
    para_birimleri = sorted(
        {h.para_birimi or "USD" for h in kapsam if h.durum == DURUM_ONAYLANDI}
    )
    trendler = []
    for para in para_birimleri:
        degerler = []
        for ay in aylar:
            sonraki = _ay_baslangici(ay, -1)
            degerler.append(
                round(
                    sum(
                        float(h.toplam_aylik_maliyet or 0)
                        for h in kapsam
                        if h.durum == DURUM_ONAYLANDI
                        and (h.para_birimi or "USD") == para
                        and ay <= _kayit_tarihi(h) < sonraki
                    ),
                    2,
                )
            )
        en_yuksek = max(degerler, default=0) or 1
        noktalar_liste = [
            {"x": 20 + i * 50, "y": round(170 - (deger / en_yuksek * 140), 1)}
            for i, deger in enumerate(degerler)
        ]
        trendler.append(
            {
                "para_birimi": para,
                "noktalar": " ".join(f"{n['x']},{n['y']}" for n in noktalar_liste),
                "noktalar_liste": noktalar_liste,
                "aylar": [
                    {"etiket": ay.strftime("%m.%Y"), "toplam": deger}
                    for ay, deger in zip(aylar, degerler)
                ],
            }
        )

    kisi_kayitlari: dict[str, list[Hesaplama]] = defaultdict(list)
    kisi_adlari: dict[str, str] = {}
    for h in onayli:
        sam = (h.olusturan_kullanici_adi or "").lower()
        if not sam:
            continue
        kisi_kayitlari[sam].append(h)
        kisi_adlari[sam] = h.olusturan_ad_soyad or sam
    ekip_ozeti = [
        {
            "kullanici_adi": sam,
            "ad_soyad": kisi_adlari[sam],
            "adet": len(kayitlar),
            "toplamlar": para_toplamlari(kayitlar),
        }
        for sam, kayitlar in kisi_kayitlari.items()
    ]
    ekip_ozeti.sort(
        key=lambda kisi: sum(t["toplam"] for t in kisi["toplamlar"]), reverse=True
    )

    sam = (kullanici.get("kullanici_adi") or "").lower()
    dogrudan_bekleyenler = sorted(
        [
            h
            for h in kapsam
            if h.durum == DURUM_ONAY_BEKLIYOR and (h.onay_hedefi or "").lower() == sam
        ],
        key=lambda h: h.olusturulma_tarihi or datetime.min,
        reverse=True,
    )
    son_kayitlar = sorted(
        [h for h in kapsam if h.durum != DURUM_TASLAK],
        key=lambda h: h.onay_tarihi or h.olusturulma_tarihi or datetime.min,
        reverse=True,
    )
    departman = kullanici.get("departman") or "diger"
    return {
        "departman_etiketi": departman_etiketi(departman),
        "baslangic": baslangic.isoformat(),
        "bitis": bitis.isoformat(),
        "tarih_hatasi": tarih_hatasi,
        "onayli_adet": len(onayli),
        "onayli_toplamlar": para_toplamlari(onayli),
        "bekleyen_adet": len(bekleyen),
        "bekleyen_toplamlar": para_toplamlari(bekleyen),
        "reddedilen_adet": sum(a.islem == "reddedildi" for a in donem_aktiviteleri),
        "iptal_adet": sum(a.islem == "iptal_edildi" for a in donem_aktiviteleri),
        "aktif_calisan_sayisi": len(kisi_kayitlari),
        "trendler": trendler,
        "ekip_ozeti": ekip_ozeti[:10],
        "dogrudan_bekleyenler": dogrudan_bekleyenler[:5],
        "son_kayitlar": son_kayitlar[:8],
        "panel_etiket_anahtari": "db_etiket",
        "panel_baslik_anahtari": "db_baslik",
        "panel_aciklama_anahtari": "db_aciklama",
        "panel_maliyet_anahtari": "db_onayli_maliyet",
        "panel_trend_anahtari": "db_trend",
        "panel_ekip_anahtari": "db_ekip_ozeti",
        "panel_bekleyen_anahtari": "db_bana_bekleyen",
        "panel_son_kayitlar_anahtari": "db_son_kayitlar",
    }


def _ozet_satirlari(kayitlar: list[Hesaplama], limit: int = 5) -> list[Hesaplama]:
    return sorted(kayitlar, key=lambda h: h.olusturulma_tarihi or h.id, reverse=True)[
        :limit
    ]


@router.get("/")
async def pano(
    request: Request,
    oturum: Session = Depends(oturum_al),
    kullanici: dict = Depends(yetki_gerekli(IZIN_HESAPLAMA_KULLAN)),
    baslangic: str = Query(""),
    bitis: str = Query(""),
):
    sam = (kullanici.get("kullanici_adi") or "").lower()
    if genel_mudur_mu(kullanici):
        tum_sirket = list(oturum.exec(select(Hesaplama)).all())
        aktiviteler = list(oturum.exec(select(AktiviteKaydi)).all())
        return render(
            request,
            "genel_mudur_pano.html",
            _genel_mudur_baglami(tum_sirket, aktiviteler, kullanici, baslangic, bitis),
        )
    if departman_basi_mi(kullanici):
        tum_departman = list(oturum.exec(select(Hesaplama)).all())
        aktiviteler = list(oturum.exec(select(AktiviteKaydi)).all())
        return render(
            request,
            "departman_basi_pano.html",
            _departman_basi_baglami(
                tum_departman, aktiviteler, kullanici, baslangic, bitis
            ),
        )
    if departman_basi_alt_kademe_mi(kullanici):
        tum_birim = list(oturum.exec(select(Hesaplama)).all())
        aktiviteler = list(oturum.exec(select(AktiviteKaydi)).all())
        baglam = _departman_basi_baglami(
            tum_birim, aktiviteler, kullanici, baslangic, bitis
        )
        baglam.update(
            {
                "panel_etiket_anahtari": "bs_etiket",
                "panel_baslik_anahtari": "bs_baslik",
                "panel_aciklama_anahtari": "bs_aciklama",
                "panel_maliyet_anahtari": "bs_onayli_maliyet",
                "panel_trend_anahtari": "bs_trend",
                "panel_ekip_anahtari": "bs_ekip_ozeti",
                "panel_bekleyen_anahtari": "bs_bana_bekleyen",
                "panel_son_kayitlar_anahtari": "bs_son_kayitlar",
            }
        )
        return render(request, "departman_basi_pano.html", baglam)

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
