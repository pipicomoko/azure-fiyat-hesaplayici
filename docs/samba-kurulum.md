# Samba AD (smblds) — kurulum ve seed

Windows Server VM parkta; aktif dizin `docker compose` içindeki Samba
(`smblds/smblds`) servisidir. Protokol: **LDAPS :636**.

## Domain

- REALM: `SIRKET.LOCAL`
- DOMAIN (NetBIOS): `SIRKET`
- Hostname / LDAP host: `dc01.sirket.local`
- Search base: `DC=sirket,DC=local`

## OU ağacı (spesifikasyon 1.2)

```
OU=Kullanicilar,DC=sirket,DC=local
  OU=Yonetim
  OU=IT
    OU=Yonetim, OU=Altyapi, OU=Yazilim, OU=Guvenlik, OU=Helpdesk
  OU=Finans, OU=Muhasebe, OU=IK, OU=Lojistik
OU=BagimsizHesaplar
OU=Gruplar
OU=ServisHesaplari
```

## Gruplar

- Rol: `AFH-Calisanlar`, `AFH-Yoneticiler`, `AFH-Direktorler`, `AFH-Adminler`
- Departman: `DEPT-IT`, `DEPT-IT-Altyapi`, `DEPT-IT-Yazilim`, `DEPT-IT-Guvenlik`,
  `DEPT-IT-Helpdesk`, `DEPT-Finans`, `DEPT-Muhasebe`, `DEPT-IK`, `DEPT-Lojistik`
- Bağımsız: `SistemYoneticileri`

## Seed

`config/samba-seed/10-hiyerarsi.sh` idempotent olarak OU / grup / 37 kullanıcı
ve `manager` ilişkilerini oluşturur. Detay tablo:
`docs/afh-proje-spesifikasyonu.md` §1.3–1.6.

## CA

İlk ayağa kalkıştan sonra (Docker Desktop açık olmalı):

```bash
docker compose up -d samba
# seed: config/samba-seed/10-hiyerarsi.sh entrypoint.d ile çalışır
./scripts/samba-ca-export.sh
docker compose up -d app postgres
```

Smoke giriş: `kerem.acar` / `Sirket123!` (LDAPS). Docker daemon kapalıysa Samba
bu makinede ayağa kalkmaz — compose dosyası ve seed hazırdır.

`config/ad-ca.pem` uygulama konteynerine mount edilir (`CERT_REQUIRED`).
