"""BUG-09: sablonlar CDN yerine yerel static vendor kullanmali."""

from pathlib import Path

_TABAN = Path("app/templates/taban.html").read_text(encoding="utf-8")
_VENDOR = Path("app/static/vendor")


def test_taban_cdn_kullanmaz():
    yasaklar = (
        "cdn.jsdelivr.net",
        "unpkg.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "cdnjs.cloudflare.com",
    )
    for yasak in yasaklar:
        assert yasak not in _TABAN, f"taban.html hala CDN kullanıyor: {yasak}"


def test_taban_yerel_vendor_yollari():
    assert "/static/vendor/bootstrap/bootstrap.min.css" in _TABAN
    assert "/static/vendor/bootstrap/bootstrap.bundle.min.js" in _TABAN
    assert "/static/vendor/htmx/htmx.min.js" in _TABAN


def test_vendor_dosyalari_mevcut_ve_bos_degil():
    dosyalar = [
        _VENDOR / "bootstrap" / "bootstrap.min.css",
        _VENDOR / "bootstrap" / "bootstrap.bundle.min.js",
        _VENDOR / "htmx" / "htmx.min.js",
    ]
    for yol in dosyalar:
        assert yol.is_file(), f"eksik vendor: {yol}"
        assert yol.stat().st_size > 1000, f"vendor dosyasi cok kucuk: {yol}"


def test_giris_sayfasi_yerel_vendor_sunar(client):
    yanit = client.get("/giris")
    assert yanit.status_code == 200
    assert "/static/vendor/htmx/htmx.min.js" in yanit.text
    assert "unpkg.com" not in yanit.text
    css = client.get("/static/vendor/bootstrap/bootstrap.min.css")
    assert css.status_code == 200
    assert b"Bootstrap" in css.content[:200]
    htmx = client.get("/static/vendor/htmx/htmx.min.js")
    assert htmx.status_code == 200
    assert len(htmx.content) > 1000
