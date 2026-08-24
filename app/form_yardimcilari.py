"""Coklu-kalemli tahmin formlarini ayristirma yardimcilari.

Tahmin calisma alanindaki her kalem (VM/Disk satiri) kendi alanlarini
`{kalem_id}.{alan_yolu}` bicimindeki isimlerle tasir (orn.
`3fa8.disk.kademe`). Bu sayede:
- Tek bir kalemin yeniden hesaplanmasi (bir alan degistiginde) sadece o
  kalemin alanlarini + genel ayarlari (dil, para birimi) gonderir,
- Dil degisimi, kaydetme ve disa aktarim gibi TOPLU islemler ayni
  ayristiriciyla TUM kalemleri tek istekte toplayabilir (nokta icermeyen
  alanlar genel ayar, nokta icerenler ilgili kalemin alanidir).
"""

from __future__ import annotations

from starlette.datastructures import FormData

_DOGRU_DEGERLER = {"on", "true", "1", "evet", "yes"}


def coklu_kalem_formunu_ayir(form: FormData) -> tuple[dict[str, str], dict[str, dict]]:
    """Donen: (genel_alanlar, {kalem_id: ic_ice_yapilandirma}).

    Ayni isimde birden fazla deger varsa (checkbox + gizli varsayilan
    ikilisi gibi) SON deger kazanir -- DOM sirasina gore checkbox isaretli
    degilse sadece gizli "false" degeri, isaretliyse ikisi de gelir ve
    checkbox degeri (sonraki) kazanir.
    """
    duz: dict[str, str] = {}
    for anahtar, deger in form.multi_items():
        duz[anahtar] = deger

    genel: dict[str, str] = {}
    kalemler_duz: dict[str, dict[str, str]] = {}
    for anahtar, deger in duz.items():
        if "." not in anahtar:
            genel[anahtar] = deger
            continue
        kalem_id, kalan = anahtar.split(".", 1)
        kalemler_duz.setdefault(kalem_id, {})[kalan] = deger

    kalemler: dict[str, dict] = {}
    for kalem_id, alanlar in kalemler_duz.items():
        ic_ice: dict = {}
        for yol, deger in alanlar.items():
            parcalar = yol.split(".")
            hedef = ic_ice
            for parca in parcalar[:-1]:
                hedef = hedef.setdefault(parca, {})
            hedef[parcalar[-1]] = deger
        kalemler[kalem_id] = ic_ice

    return genel, kalemler


def bos_degerleri_temizle(sozluk: dict) -> None:
    """Bos string degerleri siler ki urun modulleri kendi varsayilanlarini
    (yapilandirma.get(anahtar, varsayilan)) kullanabilsin."""
    for anahtar in list(sozluk.keys()):
        deger = sozluk[anahtar]
        if isinstance(deger, dict):
            bos_degerleri_temizle(deger)
        elif deger == "":
            del sozluk[anahtar]


_BOOLEAN_ALANLARI = {
    "anlik_goruntu",
    "gizli_sifreleme",
    "patlama_etkin",
    "hibrit_fayda",
}


def boolean_alanlarini_normallestir(sozluk: dict) -> None:
    for anahtar in list(sozluk.keys()):
        deger = sozluk[anahtar]
        if isinstance(deger, dict):
            boolean_alanlarini_normallestir(deger)
        elif anahtar in _BOOLEAN_ALANLARI:
            sozluk[anahtar] = str(deger).lower() in _DOGRU_DEGERLER
