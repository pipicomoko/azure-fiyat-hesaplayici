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

Uygulama http://localhost:8000 adresinde acilir (giris ekranina yonlendirir). Saglik kontrolu:
http://localhost:8000/saglik

## Ortam degiskenleri

`.env.example` dosyasina bakin. Onemli olanlar:

- `LDAP_SUNUCU`, `LDAP_DOMAIN`, `LDAP_ARAMA_TABANI`: sirketin AD DS sunucu bilgileri.
- `LDAP_TLS_MODU`: `starttls` (varsayilan) | `ldaps` | `kapali`. `APP_ENV=production` iken
  `kapali` kabul edilmez.
- `YETKI_HARITASI_DOSYASI`: varsayilan `config/yetki_haritasi.json` yerine baska bir dosya
  belirtmek icin (AD grubu -> izin eslemesini kod degistirmeden yapilandirmak icin).

## Gelistirme (Docker'siz, opsiyonel)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
ruff check .
```

Testler gercek bir AD/LDAP sunucusuna veya Azure Retail Prices API'sine ihtiyac duymaz (LDAP
baglantisi ve fiyat API'si testlerde mocklanir); fiyatlama testleri, Azure Retail Prices
API'sinden CANLI dogrulanmis sabit veriler kullanir.

## Genisletilebilirlik

Her Azure urunu (`app/products/virtual_machines`, `app/products/managed_disks`), ortak bir
sozlesmeyi (`app/products/base.py`) uygulayan bagimsiz bir modul olarak yazilmistir. Yeni bir
urun eklemek, bu sozlesmeyi uygulayip `app/products/__init__.py`'deki kayit defterine eklemek
anlamina gelir; tahmin motoru, disa aktarim ve arayuz sablonlari degismez. Bu surumde SADECE
Sanal Makineler ve Yonetilen Diskler etkindir.
