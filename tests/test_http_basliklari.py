"""BUG-01 / BUG-11: Content-Disposition (Turkce + header injection)."""

from urllib.parse import unquote

import pytest

from app.fiyat_api import onbellek_temizle
from app.http_basliklari import dosya_adi_guvenli, ek_dosya_basligi
from app.models import Hesaplama

_S4_KAYITLARI = [
    {
        "meterName": "S4 LRS Disk",
        "skuName": "S4 LRS",
        "retailPrice": 1.536,
        "unitOfMeasure": "1/Month",
        "type": "Consumption",
        "productName": "Standard HDD Managed Disks",
        "effectiveStartDate": "2020-01-01",
    },
    {
        "meterName": "S4 LRS Disk Operations",
        "skuName": "S4 LRS",
        "retailPrice": 0.0005,
        "unitOfMeasure": "10K",
        "type": "Consumption",
        "productName": "Standard HDD Managed Disks",
        "effectiveStartDate": "2020-01-01",
    },
]


async def _sahte_disk_kayitlari(filtre, para_birimi="USD", onbellek_kullan=True):
    if "Standard HDD Managed Disks" in filtre:
        return _S4_KAYITLARI
    return []


@pytest.fixture(autouse=True)
def _fiyat_api_sahte(monkeypatch):
    onbellek_temizle()
    monkeypatch.setattr(
        "app.products.managed_disks.fiyatlama.kayitlari_getir", _sahte_disk_kayitlari
    )
    yield
    onbellek_temizle()


def test_ek_dosya_basligi_turkce_latin1_guvenli():
    baslik = ek_dosya_basligi("Şirket Ölçüm İşi.xlsx")
    baslik.encode("latin-1")
    assert 'filename="' in baslik
    assert "filename*=UTF-8''" in baslik
    utf8_kisi = baslik.split("filename*=UTF-8''", 1)[1]
    assert unquote(utf8_kisi) == "Şirket Ölçüm İşi.xlsx"
    assert "Şirket" in unquote(utf8_kisi)


def test_bug11_crlf_header_injection_engellenir():
    """ad = 'evil\";\\r\\nX-Injected: yes' → baslikta CRLF / ikinci header yok."""
    ham = 'evil";\r\nX-Injected: yes.xlsx'
    baslik = ek_dosya_basligi(ham)
    assert "\r" not in baslik and "\n" not in baslik
    # Tek Content-Disposition satiri; yeni header satiri uretilemez
    assert (
        baslik.count(":") == 0 or "UTF-8" in baslik
    )  # colon sadece UTF-8 etiketi yok; scrubbed
    ascii_deger = baslik.split('filename="', 1)[1].split('"', 1)[0]
    assert ";" not in ascii_deger
    assert '"' not in ascii_deger
    assert ":" not in ascii_deger
    assert baslik.count("filename=") == 1
    assert baslik.count("filename*=") == 1
    # uvicorn latin-1 encode etmeden once hata vermemeli
    baslik.encode("latin-1")


def test_bug11_filename_spoof_engellenir():
    """ad = 'a\"; filename=\"pwn.exe' → ikinci filename= uretilemez."""
    ham = 'a"; filename="pwn.exe.xlsx'
    baslik = ek_dosya_basligi(ham)
    assert baslik.count("filename=") == 1
    assert baslik.count('filename="') == 1
    ascii_deger = baslik.split('filename="', 1)[1].split('"', 1)[0]
    assert "pwn.exe" in ascii_deger or "pwn" in ascii_deger
    # Spoof denemesi tirnak/parametre olarak kalmamis
    assert 'filename="pwn' not in baslik
    assert "; filename=" not in baslik.replace("attachment; filename=", "", 1)
    baslik.encode("latin-1")


def test_dosya_adi_guvenli_null_ve_path():
    assert "\x00" not in dosya_adi_guvenli("a\x00b.xlsx")
    assert ".." not in dosya_adi_guvenli("../../etc/passwd.xlsx")
    assert ";" not in dosya_adi_guvenli("a;b.xlsx")
    assert '"' not in dosya_adi_guvenli('a"b.xlsx')


def test_gecmis_excel_injection_adi_200_ve_guvenli_baslik(client, veritabani):
    """BUG-11 entegrasyon: kotu tahmin adi Excel indirmeyi cokertmez / enjekte etmez."""
    from tests.test_tahmin import _kaydet

    kotu_ad = 'a"; filename="pwn.exe'
    kaydet = _kaydet(client, kotu_ad)
    assert kaydet.status_code == 200, kaydet.text[:300]

    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        kayit = oturum.exec(select(Hesaplama).where(Hesaplama.ad == kotu_ad)).one()
        kayit_id = kayit.id

    yanit = client.get(f"/gecmis/{kayit_id}/excel")
    assert yanit.status_code == 200, yanit.text[:500]
    cd = yanit.headers.get("content-disposition", "")
    assert "\r" not in cd and "\n" not in cd
    assert cd.count("filename=") == 1
    assert 'filename="pwn' not in cd
    assert "azure-tahmin-" not in cd
    cd.encode("latin-1")
    assert len(yanit.content) > 100


def test_gecmis_excel_turkce_ad_500_vermez(client, veritabani):
    from tests.test_tahmin import _kaydet

    kaydet = _kaydet(client, "Şirket Ölçüm İşi")
    assert kaydet.status_code == 200, kaydet.text[:300]

    with __import__("sqlmodel").Session(veritabani) as oturum:
        from sqlmodel import select

        kayit = oturum.exec(select(Hesaplama)).one()
        assert kayit.ad == "Şirket Ölçüm İşi"
        kayit_id = kayit.id

    yanit = client.get(f"/gecmis/{kayit_id}/excel")
    assert yanit.status_code == 200, yanit.text[:500]
    cd = yanit.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "filename*=UTF-8''" in cd
    cd.encode("latin-1")
    utf8_adi = unquote(cd.split("filename*=UTF-8''", 1)[1])
    assert utf8_adi == "Şirket Ölçüm İşi.xlsx"
    assert "azure-tahmin-" not in utf8_adi
    assert yanit.headers.get("content-type", "").startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(yanit.content) > 100
