"""Liste sayfalarindaki baslangic/bitis tarih filtrelerinin ortak varsayilani.

Ilk ziyarette (parametre yok / ikisi de bos):
  bitis      = bugun (Europe/Istanbul takvim gunu)
  baslangic  = tam bir ay once (ay sonu tasmasi: 31 Mart → 28/29 Subat)

Kullanici acik tarih gonderirse degerler oldugu gibi korunur.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime

from app.zaman import YEREL_SAAT_DILIMI


def bugunun_tarihi() -> date:
    return datetime.now(YEREL_SAAT_DILIMI).date()


def bir_ay_once(gun: date) -> date:
    yil, ay = gun.year, gun.month - 1
    if ay == 0:
        yil, ay = yil - 1, 12
    return date(yil, ay, min(gun.day, monthrange(yil, ay)[1]))


def varsayilan_tarih_araligi(bugun: date | None = None) -> tuple[date, date]:
    bitis = bugun or bugunun_tarihi()
    return bir_ay_once(bitis), bitis


def varsayilan_tarih_iso(bugun: date | None = None) -> tuple[str, str]:
    baslangic, bitis = varsayilan_tarih_araligi(bugun)
    return baslangic.isoformat(), bitis.isoformat()


def tarih_coz(ham: str, varsayilan: date) -> tuple[date, bool]:
    """ISO tarihi cozer. Bos → varsayilan (ok=True); gecersiz → varsayilan (ok=False)."""
    metin = (ham or "").strip()
    if not metin:
        return varsayilan, True
    try:
        return date.fromisoformat(metin), True
    except ValueError:
        return varsayilan, False


def bos_tarihleri_doldur(
    baslangic: str, bitis: str, *, bugun: date | None = None
) -> tuple[str, str]:
    """Ikisi de bossa varsayilan araligi doldurur; aksi halde gelen degerleri korur."""
    bas = (baslangic or "").strip()
    bit = (bitis or "").strip()
    if bas or bit:
        return bas, bit
    return varsayilan_tarih_iso(bugun)


def donem_araligini_coz(
    baslangic_ham: str,
    bitis_ham: str,
    *,
    bugun: date | None = None,
) -> tuple[date, date, bool]:
    """Pano donem filtresi: bos → varsayilan; gecersiz/ters aralik → varsayilan + hata."""
    varsayilan_bas, varsayilan_bit = varsayilan_tarih_araligi(bugun)
    bas, bit = bos_tarihleri_doldur(baslangic_ham, bitis_ham, bugun=bugun)
    baslangic, bas_ok = tarih_coz(bas, varsayilan_bas)
    bitis, bit_ok = tarih_coz(bit, varsayilan_bit)
    hatali = not bas_ok or not bit_ok or baslangic > bitis
    if hatali:
        return varsayilan_bas, varsayilan_bit, True
    return baslangic, bitis, False
