"""Surec / bagimlilik saglik kontrolleri.

/canli yalnizca surecin ayakta oldugunu soyler (liveness).
/saglik veritabani SELECT 1 + LDAP TCP (bind yok) bakar (readiness).
"""

from __future__ import annotations

import socket

from sqlalchemy import text

from app.database import engine
from app.yetkilendirme import LDAP_PORT, LDAP_TLS_MODU, ldap_sunucu_hostlari


def veritabani_erisilebilir_mi(*, zaman_asimi_sn: float = 2.0) -> bool:
    try:
        with engine.connect() as baglanti:
            if engine.dialect.name == "postgresql":
                # SET parametre baglamaz; ms yalnizca int.
                ms = max(1, int(zaman_asimi_sn * 1000))
                baglanti.execute(text(f"SET statement_timeout = {ms}"))
            baglanti.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def ldap_tcp_erisilebilir_mi(*, zaman_asimi_sn: float = 2.0) -> bool:
    """Bind denemez; DC'yi yormamak icin yalnizca TCP."""
    hostlar = ldap_sunucu_hostlari()
    if not hostlar:
        return False
    if LDAP_TLS_MODU == "ldaps":
        port = LDAP_PORT or 636
    else:
        port = LDAP_PORT or 389
    for host in hostlar:
        try:
            with socket.create_connection((host, port), timeout=zaman_asimi_sn):
                return True
        except OSError:
            continue
    return False
