# Azure Fiyat Hesaplayici

Sirket ici kullanim icin, resmi [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/)'i
baz alan bir web uygulamasi. Bu surumde **sadece iki urun** desteklenir:

- **Sanal Makineler** (Virtual Machines)
- **Yonetilen Diskler** (Managed Disks)

Her ikisi de resmi hesaplayicida gorunen alan/bagimlilik kumesini uygular (bolge, isletim
sistemi/yazilim tipi, kademe, kategori/seri/instance, kullanim suresi, tasarruf plani/rezervasyon
secenekleri, Azure Hybrid Benefit, gomulu disk/islem/bant genisligi bilesenleri; disk tarafinda
kademe, yedeklilik, disk boyutu/IOPS/throughput, anlik goruntu, gizli sifreleme, patlama). Fiyatlar
HER ZAMAN [Azure Retail Prices API](https://prices.azure.com/api/retail/prices)'sinden canli
cekilir; hicbir sayisal fiyat kodda sabit degildir.

## Ozellikler

- **Kimlik dogrulama**: Sirket Active Directory'sine LDAP (uretimde LDAPS/StartTLS ile) baglanir.
  Kullanici adi/sifre veritabanina veya loglara YAZILMAZ.
- **Yetkilendirme**: AD grup uyelikleri, `config/yetki_haritasi.json` dosyasindaki (kod
  degistirmeden duzenlenebilir) esleme ile uygulama izinlerine cevrilir. Ayni kontrol hem
  sayfalarda (buton/menu gorunurlugu) hem de her API ucunda uygulanir.
- **Tahmin calisma alani**: Ayni urunden birden fazla kalem eklenebilir, her kalem kendi
  alanlariyla anlik olarak yeniden hesaplanir, kaldirilabilir; genel toplam aninda guncellenir.
- **Excel'e aktarma**: Doldurulmus bir tahmin, `.xlsx` olarak indirilebilir (bos tahmin
  aktarilamaz).
- **TR/EN**: Arayuz, menu, hata mesajlari ve Excel basliklari Turkce/Ingilizce arasinda, mevcut
  tahmini kaybetmeden degistirilebilir.
- **Gecmis**: Adlandirilmis tahminler kaydedilip daha sonra 2'li karsilastirilabilir (kullanici
  kimligi kaydedilmez).

## Calistirma

```bash
cp .env.example .env
docker compose up --build
```

Uygulama http://localhost:8000 adresinde acilir (giris ekranina yonlendirir).
Surec ayakta mi: http://localhost:8000/canli
Readiness (Postgres + LDAP TCP): http://localhost:8000/saglik

Ayni agdaki baska bir bilgisayar icin Mac'in LAN IP'sini kullanin, ornek:
`http://10.22.251.190:8000` (IP `ipconfig getifaddr en0` ile gorulur).

## Domain ile internete acmak (Cloudflare Tunnel)

Router portu acmadan, satin alinan bir domain'i bu makinedeki Docker uygulamaya baglamak
icin Cloudflare Tunnel kullanin. Bu yol HTTPS verir ve 8000/5432 portlarini internete
acmaz.

1. [Cloudflare](https://dash.cloudflare.com/sign-up) hesabi acin.
2. Domain satin alin (Cloudflare Registrar, Namecheap, Google/Squarespace vb.).
3. Domain'i Cloudflare'a ekleyin. Cloudflare disinda aldiysaniz nameserver'lari
   Cloudflare'in verdigi NS kayitlariyla degistirin (DNS Cloudflare uzerinden yonetilsin).
4. Zero Trust > Networks > Tunnels > Create a tunnel. Public hostname olarak
   kok domain kullanabilirsiniz: `sirketiniz.com` -> `http://app:8000`
   (`www.sirketiniz.com` da ayni hedefe eklenebilir. Alt alan adi sart degil.)
5. Tunnel token'i kopyalayip `.env` icine `CLOUDFLARE_TUNNEL_TOKEN=...` yazin.
6. Uygulama ayaktayken:

```bash
docker compose --profile tunnel up -d
```

Bundan sonra baska bir bilgisayar `https://sirketiniz.com` adresinden acar.
Mac uykuya gecerse veya `docker compose down` yapilirsa tunel de durur.

Bu kurulum hala gelistirme ortamidir: varsayilan `SECRET_KEY` kullanmayin, LDAP'i
uretimde `ldaps` veya `starttls` yapin, veritabani portu yalnizca localhost'ta dinler.

## Ortam degiskenleri

`.env.example` dosyasina bakin. Onemli olanlar:

- `LDAP_SUNUCU`, `LDAP_DOMAIN`, `LDAP_ARAMA_TABANI`: sirketin AD DS sunucu bilgileri.
  `LDAP_SUNUCU` virgulle birden fazla DC alabilir (`dc01.sirket.local,dc02.sirket.local`);
  baglanti ilk ulasilabilir sunucuya gecer.
- `LDAP_TLS_MODU`: `ldaps` (varsayilan) | `starttls` | `kapali`. `APP_ENV=production` iken
  `kapali` kabul edilmez. LDAPS icin AD DC'de sunucu sertifikasi olmali (port 636).
- `LDAP_CA_SERTIFIKA_DOSYASI`: DC/CA sertifikasinin PEM yolu, varsayilan `config/ad-ca.pem`.

Windows Server AD DC uzerinde LDAPS acmak (kisaca): Domain Controller sertifikasini
(Server Authentication) Local Computer > Personal deposuna koyun, NTDS'i veya sunucuyu
yeniden baslatin, CA sertifikasini Base-64 olarak export edip `config/ad-ca.pem` olarak
kaydedin. 636 uzerinde TLS el sikismasi olmadan uygulama giris yapamaz.

- `YETKI_HARITASI_DOSYASI`: varsayilan `config/yetki_haritasi.json` yerine baska bir dosya
  belirtmek icin (AD grubu -> izin eslemesini kod degistirmeden yapilandirmak icin).

Gunluk veritabani dump'i (opsiyonel): `docker compose --profile backup up -d` —
ayrintilar `docs/yedekleme.md`. Postgres baglanti havuzu `DB_POOL_SIZE` /
`DB_MAX_OVERFLOW` ile ayarlanir.

Admin giris denemelerini `/admin/giris-gunlugu` altinda gorur (`audit.gor`); sifre
yazilmaz, kayitlar 90 gun saklanir.

## Gelistirme (Docker'siz, opsiyonel)

Python **3.12** kullanin (CI, Dockerfile ve `.python-version` ile ayni). Sisteminizde
baska bir surum varsa `python3.12 -m venv .venv` tercih edin.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
ruff check .
ruff format --check .
```

`uvicorn app.main:app` calistirirken kok dizindeki `.env` otomatik yuklenir (`load_dotenv`).

Testler gercek bir AD/LDAP sunucusuna veya Azure Retail Prices API'sine ihtiyac duymaz (LDAP
baglantisi ve fiyat API'si testlerde mocklanir); fiyatlama testleri, Azure Retail Prices
API'sinden CANLI dogrulanmis sabit veriler kullanir.

## Genisletilebilirlik

Her Azure urunu (`app/products/virtual_machines`, `app/products/managed_disks`), ortak bir
sozlesmeyi (`app/products/base.py`) uygulayan bagimsiz bir modul olarak yazilmistir. Yeni bir
urun eklemek, bu sozlesmeyi uygulayip `app/products/__init__.py`'deki kayit defterine eklemek
anlamina gelir; tahmin motoru, disa aktarim ve arayuz sablonlari degismez. Bu surumde SADECE
Sanal Makineler ve Yonetilen Diskler etkindir.
