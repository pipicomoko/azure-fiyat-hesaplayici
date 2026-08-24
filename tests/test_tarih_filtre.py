"""Varsayilan baslangic/bitis tarih araligi (bugun ve tam bir ay once)."""

from datetime import date, timedelta

from app.tarih_filtre import (
    bir_ay_once,
    bos_tarihleri_doldur,
    donem_araligini_coz,
    tarih_coz,
    varsayilan_tarih_araligi,
    varsayilan_tarih_iso,
)


def test_bir_ay_once_ay_sonu_tasmasini_kisar():
    assert bir_ay_once(date(2026, 3, 31)) == date(2026, 2, 28)
    assert bir_ay_once(date(2024, 3, 31)) == date(2024, 2, 29)
    assert bir_ay_once(date(2026, 5, 31)) == date(2026, 4, 30)


def test_bir_ay_once_yil_basi():
    assert bir_ay_once(date(2026, 1, 15)) == date(2025, 12, 15)


def test_varsayilan_aralik_bitis_bugun_baslangic_bir_ay_once():
    bugun = date(2026, 8, 24)
    baslangic, bitis = varsayilan_tarih_araligi(bugun)
    assert bitis == bugun
    assert baslangic == date(2026, 7, 24)


def test_bos_tarihleri_doldur_ikisi_bosken_varsayilani_yazar():
    bugun = date(2026, 8, 24)
    bas, bit = bos_tarihleri_doldur("", "", bugun=bugun)
    assert (bas, bit) == varsayilan_tarih_iso(bugun)


def test_bos_tarihleri_doldur_acik_degerleri_korur():
    assert bos_tarihleri_doldur("2025-01-02", "2025-02-03") == (
        "2025-01-02",
        "2025-02-03",
    )
    assert bos_tarihleri_doldur("2025-01-02", "") == ("2025-01-02", "")
    assert bos_tarihleri_doldur("", "2025-02-03") == ("", "2025-02-03")


def test_tarih_coz_bos_ve_gecersiz():
    varsayilan = date(2026, 1, 1)
    assert tarih_coz("", varsayilan) == (varsayilan, True)
    assert tarih_coz("2026-04-15", varsayilan) == (date(2026, 4, 15), True)
    assert tarih_coz("not-a-date", varsayilan) == (varsayilan, False)


def test_donem_araligini_coz_bos_ve_ters_aralik():
    bugun = date(2026, 8, 24)
    bas, bit, hata = donem_araligini_coz("", "", bugun=bugun)
    assert (bas, bit, hata) == (date(2026, 7, 24), bugun, False)

    bas, bit, hata = donem_araligini_coz("2026-12-31", "2026-01-01", bugun=bugun)
    assert hata is True
    assert (bas, bit) == (date(2026, 7, 24), bugun)

    bas, bit, hata = donem_araligini_coz("2026-01-01", "2026-01-31", bugun=bugun)
    assert hata is False
    assert (bas, bit) == (date(2026, 1, 1), date(2026, 1, 31))


def test_varsayilan_aralik_bir_ay_30_31_gun():
    # 24 Agustos → 24 Temmuz: 31 gunluk pencere degil, takvim ayi
    bas, bit = varsayilan_tarih_araligi(date(2026, 8, 24))
    assert (bit - bas) == timedelta(days=31)
    bas, bit = varsayilan_tarih_araligi(date(2026, 3, 15))
    assert (bit - bas) == timedelta(days=28)
