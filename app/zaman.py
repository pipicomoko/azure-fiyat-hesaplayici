"""Zaman damgalarini goruntuleme icin yerel saat dilimine cevirir.

Veritabaninda her zaman UTC saklanir (Hesaplama.olusturulma_tarihi); ekranda
sirketin bulundugu saat dilimine (Turkiye, UTC+3, DST yok) cevrilerek
gosterilir."""

from datetime import datetime
from zoneinfo import ZoneInfo

YEREL_SAAT_DILIMI = ZoneInfo("Europe/Istanbul")


def yerel_saate_cevir(deger: datetime) -> datetime:
    if deger.tzinfo is None:
        # SQLite gibi bazi veritabanlari saklarken tzinfo'yu dusurur; UTC
        # olarak kaydedildigini biliyoruz (bkz. models.py default_factory).
        from datetime import timezone

        deger = deger.replace(tzinfo=timezone.utc)
    return deger.astimezone(YEREL_SAAT_DILIMI)
