# Azure Fiyat Hesaplayıcı (AFH) — Onay Akışı ve Rol Bazlı Panel Spesifikasyonu

> Bu doküman bir planlama çıktısıdır, kod içermez. Cursor'da uygulamaya
> geçirilmek üzere hazırlanmıştır.

---

## 0. Kimlik doğrulama altyapısı — ÖNEMLİ

- **Dizin kaynağı: Samba AD DC (Docker container).** Windows Server VM
  DEĞİL — VM ayrı bir ortam olarak park edilmiş durumda, aktif geliştirme
  Samba üzerinden yapılacak.
- **Protokol: LDAPS (port 636, TLS).** Kullanıcı bunu teyit etti.
- **Açık nokta (henüz karar verilmedi):** Samba AD DC container'ı
  varsayılan olarak sadece düz LDAP (389) ile ayağa kalkar. LDAPS için
  container'a ayrıca TLS sertifikası tanımlanması gerekir — bu otomatik
  gelmez, ek bir kurulum adımıdır. Şu iki seçenekten biri netleşmeli:
  1. Samba container'ına LDAPS için sertifika kurulur (geliştirme
     ortamında da gerçek LDAPS kullanılır)
  2. Geliştirme ortamında düz LDAP kullanılır, LDAPS sadece gerçek
     şirket AD'sine bağlanırken devreye girer (`.env` ile seçilir)
  Bu karar netleşmeden Samba tarafının kurulumuna geçilmemeli.
- Domain: `sirket.local`
- UPN format: `kullanici.adi@sirket.local`
- VM'deki DC01 IP'si (referans, artık aktif kullanılmıyor):
  `192.168.56.10`

### 0.1 AD'de gerekli düzeltme (henüz uygulanmadı)

Bölüm 4.2'de açıklanan iptal görünürlüğü kuralının çalışabilmesi için
Genel Müdür'ün (Ahmet Yıldırım) yönetici/direktör tier'ına ait bir gruba
üye olması gerekiyor. Şu anki kurulumda sadece `AFH-Calisanlar`
grubunda. Şu komut DC01'de çalıştırılmalı:

```
Add-ADGroupMember -Identity "AFH-Direktorler" -Members "ahmet.yildirim"
```

---

## 1. Kullanıcı Hiyerarşisi (detaylı)

Toplam **37 kullanıcı**, 4 yetki kademesi.

### 1.1 Organizasyon şeması

```
Ahmet Yildirim — Genel Mudur
│
├── Serkan Aydemir — IT Direktoru
│   └── Baris Kocak — IT Grup Muduru
│       │
│       ├── Emre Turan — IT Bolum Muduru (Altyapi ve Sistemler)
│       │   ├── Onur Simsek — IT Yoneticisi (Sistem Yonetimi)
│       │   │   ├── Kerem Acar — Sistem Uzmani
│       │   │   └── Tuna Bozkurt — Sistem Uzmani
│       │   └── Gokhan Erdem — IT Yoneticisi (Ag Yonetimi)
│       │       └── Volkan Uysal — Ag Uzmani
│       │
│       ├── Deniz Kartal — IT Bolum Muduru (Yazilim Gelistirme)
│       │   └── Aylin Gunes — IT Yoneticisi (Yazilim Ekibi)
│       │       ├── Burcu Yalcin — Yazilim Uzmani
│       │       └── Mert Aksu — Yazilim Uzmani
│       │
│       ├── Ceyda Polat — IT Bolum Muduru (Bilgi Guvenligi)
│       │   ├── Yusuf Er — Guvenlik Uzmani
│       │   └── Nazli Korkmaz — Guvenlik Uzmani
│       │
│       └── Fatih Dogru — IT Bolum Muduru (Yardim Masasi)
│           ├── Irem Sari — Helpdesk Uzmani
│           └── Oguz Tekin — Helpdesk Uzmani
│
├── Murat Ozturk — Finans Direktoru
│   └── Sibel Arslan — Finans Muduru
│       └── Caner Bulut — Finans Yoneticisi
│           ├── Elif Aydin — Finans Uzmani
│           └── Kutay Sen — Finans Uzmani
│
├── Hande Aksoy — Muhasebe Muduru
│   └── Tolga Yavuz — Muhasebe Yoneticisi
│       ├── Pelin Cakir — Muhasebe Uzmani
│       └── Berkay Solmaz — Muhasebe Uzmani
│
├── Zehra Kaplan — IK Muduru
│   └── Ugur Bayrak — IK Yoneticisi
│       ├── Selin Dogan — IK Uzmani
│       └── Erhan Kilic — IK Uzmani
│
└── Cem Aktas — Lojistik Muduru
    └── Derya Celik — Lojistik Yoneticisi
        ├── Buse Karaca — Lojistik Uzmani
        └── Kaan Yildiz — Lojistik Uzmani

────────────────────────────────────
Asli Demirtas — Sistem Yoneticisi (bagimsiz, hicbir departmana bagli degil)
```

### 1.2 OU Ağacı

```
sirket.local
├─ OU=Kullanicilar
│   ├─ OU=Yonetim              (Ahmet Yildirim)
│   ├─ OU=IT
│   │   ├─ OU=Yonetim          (Serkan Aydemir, Baris Kocak)
│   │   ├─ OU=Altyapi
│   │   ├─ OU=Yazilim
│   │   ├─ OU=Guvenlik
│   │   └─ OU=Helpdesk
│   ├─ OU=Finans
│   ├─ OU=Muhasebe
│   ├─ OU=IK
│   └─ OU=Lojistik
├─ OU=BagimsizHesaplar          (Asli Demirtas)
├─ OU=Gruplar
└─ OU=ServisHesaplari
```

### 1.3 Tam kullanıcı tablosu (37 kişi)

| Ad Soyad | sAMAccountName | Unvan | Departman | Üst (Manager) |
|---|---|---|---|---|
| Ahmet Yildirim | ahmet.yildirim | Genel Mudur | Yonetim | *(bos)* |
| Serkan Aydemir | serkan.aydemir | IT Direktoru | IT | ahmet.yildirim |
| Baris Kocak | baris.kocak | IT Grup Muduru | IT | serkan.aydemir |
| Emre Turan | emre.turan | IT Bolum Muduru (Altyapi ve Sistemler) | IT | baris.kocak |
| Onur Simsek | onur.simsek | IT Yoneticisi (Sistem Yonetimi) | IT | emre.turan |
| Kerem Acar | kerem.acar | Sistem Uzmani | IT | onur.simsek |
| Tuna Bozkurt | tuna.bozkurt | Sistem Uzmani | IT | onur.simsek |
| Gokhan Erdem | gokhan.erdem | IT Yoneticisi (Ag Yonetimi) | IT | emre.turan |
| Volkan Uysal | volkan.uysal | Ag Uzmani | IT | gokhan.erdem |
| Deniz Kartal | deniz.kartal | IT Bolum Muduru (Yazilim Gelistirme) | IT | baris.kocak |
| Aylin Gunes | aylin.gunes | IT Yoneticisi (Yazilim Ekibi) | IT | deniz.kartal |
| Burcu Yalcin | burcu.yalcin | Yazilim Uzmani | IT | aylin.gunes |
| Mert Aksu | mert.aksu | Yazilim Uzmani | IT | aylin.gunes |
| Ceyda Polat | ceyda.polat | IT Bolum Muduru (Bilgi Guvenligi) | IT | baris.kocak |
| Yusuf Er | yusuf.er | Guvenlik Uzmani | IT | ceyda.polat |
| Nazli Korkmaz | nazli.korkmaz | Guvenlik Uzmani | IT | ceyda.polat |
| Fatih Dogru | fatih.dogru | IT Bolum Muduru (Yardim Masasi) | IT | baris.kocak |
| Irem Sari | irem.sari | Helpdesk Uzmani | IT | fatih.dogru |
| Oguz Tekin | oguz.tekin | Helpdesk Uzmani | IT | fatih.dogru |
| Murat Ozturk | murat.ozturk | Finans Direktoru | Finans | ahmet.yildirim |
| Sibel Arslan | sibel.arslan | Finans Muduru | Finans | murat.ozturk |
| Caner Bulut | caner.bulut | Finans Yoneticisi | Finans | sibel.arslan |
| Elif Aydin | elif.aydin | Finans Uzmani | Finans | caner.bulut |
| Kutay Sen | kutay.sen | Finans Uzmani | Finans | caner.bulut |
| Hande Aksoy | hande.aksoy | Muhasebe Muduru | Muhasebe | ahmet.yildirim |
| Tolga Yavuz | tolga.yavuz | Muhasebe Yoneticisi | Muhasebe | hande.aksoy |
| Pelin Cakir | pelin.cakir | Muhasebe Uzmani | Muhasebe | tolga.yavuz |
| Berkay Solmaz | berkay.solmaz | Muhasebe Uzmani | Muhasebe | tolga.yavuz |
| Zehra Kaplan | zehra.kaplan | IK Muduru | IK | ahmet.yildirim |
| Ugur Bayrak | ugur.bayrak | IK Yoneticisi | IK | zehra.kaplan |
| Selin Dogan | selin.dogan | IK Uzmani | IK | ugur.bayrak |
| Erhan Kilic | erhan.kilic | IK Uzmani | IK | ugur.bayrak |
| Cem Aktas | cem.aktas | Lojistik Muduru | Lojistik | ahmet.yildirim |
| Derya Celik | derya.celik | Lojistik Yoneticisi | Lojistik | cem.aktas |
| Buse Karaca | buse.karaca | Lojistik Uzmani | Lojistik | derya.celik |
| Kaan Yildiz | kaan.yildiz | Lojistik Uzmani | Lojistik | derya.celik |
| Asli Demirtas | asli.demirtas | Sistem Yoneticisi | *(bagimsiz)* | *(bos)* |

### 1.4 Yetki kademeleri (AD grubu → uygulama rolü)

| AD Grubu | Uygulama Rolü | Üyeler |
|---|---|---|
| `AFH-Calisanlar` | `calisan` | Adminler hariç herkes (36 kişi) |
| `AFH-Yoneticiler` | `yonetici` | onur.simsek, gokhan.erdem, aylin.gunes, caner.bulut, tolga.yavuz, ugur.bayrak, derya.celik, emre.turan, deniz.kartal, ceyda.polat, fatih.dogru (11 kişi) |
| `AFH-Direktorler` | `direktor` | serkan.aydemir, baris.kocak, murat.ozturk, sibel.arslan, hande.aksoy, zehra.kaplan, cem.aktas (7 kişi) + **ahmet.yildirim eklenmeli (bkz. 0.1)** |
| `AFH-Adminler` | `admin` | asli.demirtas (tek üye) |

Rol belirlenirken **en yüksek yetkiden aşağıya doğru** kontrol edilmeli:
önce admin mi, değilse direktör mü, değilse yönetici mü, değilse
çalışan mı.

### 1.5 Departman grupları (raporlama kırılımı için, DEPT- önekli)

```
DEPT-IT              (18 kişi, tüm IT alt birimleri dahil)
DEPT-IT-Altyapi
DEPT-IT-Yazilim
DEPT-IT-Guvenlik
DEPT-IT-Helpdesk
DEPT-Finans
DEPT-Muhasebe
DEPT-IK
DEPT-Lojistik
```

### 1.6 Bağımsız grup

```
SistemYoneticileri
  └─ Asli Demirtas   (hicbir DEPT- grubuna uye degil)
```

### 1.7 "Departman başı" kavramı (rol grubundan bağımsız)

Bir kişinin "departmanın en üstü" olması, `AFH-Direktorler` grubunda
olmasıyla aynı şey değildir — bazı departmanlarda birden fazla kişi bu
grupta olabilir (örn. IT'de hem Serkan Aydemir hem Barış Koçak).
"Departman başı", **AD'deki `manager` zincirinde doğrudan Genel
Müdür'e (Ahmet Yıldırım) bağlı olan tek kişidir.** Şu anki 37 kişilik
yapıda bu tam olarak 5 kişi:

| Departman | Departman Başı |
|---|---|
| IT | Serkan Aydemir (IT Direktörü) |
| Finans | Murat Öztürk (Finans Direktörü) |
| Muhasebe | Hande Aksoy (Muhasebe Müdürü) |
| İK | Zehra Kaplan (İK Müdürü) |
| Lojistik | Cem Aktaş (Lojistik Müdürü) |

Bu, sabit bir liste olarak kodlanmamalı — uygulama, kullanıcının
`manager` alanının `ahmet.yildirim` olup olmadığını dinamik olarak
kontrol ederek bu kişiyi bulmalı. Böylece AD'de departman başı
değişirse (örn. Serkan Aydemir ayrılırsa) kodda değişiklik gerekmez.

---

## 2. Hesaplama Durum Akışı

```
TASLAK ──(onaya gonder)──> ONAY_BEKLIYOR ──(onayla)──> ONAYLANDI ──(departman basi iptal eder)──> IPTAL_EDILDI
                                 │
                                 └──(reddet)──> TASLAK (otomatik geri doner)
```

### Kurallar

- **Taslak**, doğrudan `onay_bekliyor` durumuna geçer — ayrı bir kopya
  oluşturulmaz, aynı kayıt üzerinde durum değişir.
- **Onay bekliyor** durumundaki kayıt sahibi tarafından düzenlenemez
  (donmuş).
- **Reddedilirse**, kayıt otomatik olarak `taslak` durumuna döner.
  - Red gerekçesi alanı vardır ama **zorunlu değildir**.
  - Reddedilen eski hal **silinmez**, revizyon geçmişi olarak saklanır.
- Çalışan revize edip tekrar gönderdiğinde **revizyon numarası artar**
  (v1 reddedildi → v2 gönderildi gibi kayıtta görünür).
- **Onaylandı** durumu düzenlenemez, raporlara dahil olur, ama tamamen
  kalıcı değildir — bkz. aşağıdaki iptal kuralı.
- **İptal edildi** — terminal bir durum (bkz. 2.1).
- Tutar eşiği YOK — kim seçilirse o kişi tek başına karar verir.

### 2.1 Onaylanmış kaydın iptali

- Bir `onaylandı` durumundaki kayıt, **sadece o kaydın ait olduğu
  departmanın başı tarafından** iptal edilebilir (bkz. Bölüm 1.7).
- Kayıt `iptal_edildi` durumuna geçer, **silinmez** — geçmişte görünür
  kalır.
- İptal gerekçesi zorunlu değil (red'deki opsiyonel gerekçe mantığıyla
  tutarlı tutuldu).
- **İptal edilen kayıtlar rapor toplamlarına dahil edilmez.**
- **Görünürlük:** İptal eden departman başının **kendi üstü de bu
  iptali görebilmeli.** Ayrı bir ekran gerekmiyor — Bölüm 4'teki
  "manager zincirindeki herkesin kayıtlarını görme" kuralı bunu zaten
  kapsıyor, yeter ki ilgili kişi doğru AD grubuna üye olsun (bkz.
  Bölüm 0.1).

---

## 3. Onay Hedefi Seçimi

- Çalışan, hesaplamayı onaya gönderirken **sadece kendi biriminin yukarı
  zincirinden (kendi `manager` zinciri)** birini seçebilir.
- Başka departman/birimdeki birine gönderilemez.
- Örnek: Kerem Acar (IT-Altyapı) şu kişilerden birini seçebilir:
  Onur Şimşek, Emre Turan, Barış Koçak, Serkan Aydemir, Ahmet Yıldırım.
- Seçim ekranında her kişinin unvanı da gösterilir.

---

## 4. Görünürlük Kuralları

- **Çalışan**: sadece kendi hesaplamalarını görür.
- **Yönetici / Direktör**: kendi altındaki (manager zincirinde bulunan)
  **herkesin onaylanmış (ve iptal edilmiş) kayıtlarını** görebilir.
- **Varsayım (netleştirilmedi):** Yönetici ve direktörler de kendi
  hesaplamalarını oluşturabilir (`AFH-Calisanlar` grubuna da üyeler).
- **Admin (`AFH-Adminler`)**: departman/birim sınırı olmadan tüm
  kayıtları görebilir.
  - **Varsayım (netleştirilmedi):** Admin, henüz onay sürecine girmemiş
    **taslakları görmez** — sadece onay_bekliyor / onaylandı /
    reddedildi / iptal_edildi durumundaki kayıtlar admin görünümünde
    yer alır.

---

## 5. İndirim (Discount) Alanı

- Hesaplama oluşturulurken, **her hizmet/kalem için ayrı ayrı** bir
  indirim yüzdesi girilebilir. **Zorunlu değil.**
- Boş bırakılan kalemler indirimsiz fiyatla hesaba katılır.
- **Toplam maliyet hesaplaması (varsayım, netleştirilmedi):** Sepet
  toplamı, onay ekranı ve raporlar — indirim girilen kalemlerde
  **indirimli fiyat** üzerinden hesaplanır.

---

## 6. Excel Export Formatları

İki farklı export senaryosu var, **birbirine karıştırılmamalı:**

### 6.1 Export Türü A — Tek Hesaplama Exportu

Bu, kullanıcının paylaştığı orijinal Microsoft Azure Pricing Calculator
export dosyasının (`NorthPacificJPN.xlsx`) **birebir aynı yapısı**,
sadece ek sütun/alanlarla genişletilmiş hali. Bir hesaplamadaki her
kalem (VM, disk vb.) bir satır olur.

**Üst bilgi bloğu** (orijinalde "Microsoft Azure Estimate" başlığı
vardı, YENİ olarak eklenenler):

| Alan | Kaynak |
|---|---|
| Microsoft Azure Estimate (başlık) | Orijinal |
| Senaryo/Hesaplama Adı | Orijinal |
| **Oluşturan Çalışan** | YENİ |
| **Birim** | YENİ |
| **Oluşturulma Tarihi** | YENİ |
| **Durum, Revizyon No** | YENİ |
| **Onaylayan, Onay Tarihi** (varsa) | YENİ |

**Tablo sütunları** (orijinal sütunlar BİREBİR korunur, indirim
sütunları eklenir):

| Service category | Service type | Custom name | Region | Description | Estimated monthly cost | İndirim Yüzdesi *(YENİ)* | İndirimli Aylık Maliyet *(YENİ)* | Estimated upfront cost | Yıllık Tahmini Maliyet *(YENİ)* |
|---|---|---|---|---|---|---|---|---|---|

- `İndirim Yüzdesi` ve `İndirimli Aylık Maliyet` sadece o kalemde
  indirim girilmişse doludur, yoksa boş/tire (`—`).
- `Yıllık Tahmini Maliyet` = (İndirimli Aylık Maliyet varsa o, yoksa
  Estimated monthly cost) × 12.

**Alt kısım** (orijinalden birebir korunur):

- `Support` satırı
- `Licensing Program` / `Billing Account` / `Billing Profile` alanları
- `Total` satırı — **YENİ:** yıllık toplam da bu satıra eklenir
- Disclaimer metni ("All prices shown are in United States – Dollar...")
- Oluşturulma zaman damgası

### 6.2 Export Türü B — Dönemsel Toplu Rapor

Bu, Türü A'dan **tamamen farklı bir format** — Microsoft'un
satır-bazlı (kalem kalem) yapısını taklit etmez. Burada her satır bir
**hesaplamanın özeti**dir, kalem detayına inmez:

```
Tarih | Calisan | Birim | Hizmet | Kalem Sayisi | Toplam Tutar | Onaylayan | Onay Tarihi
```

- Sadece **onaylanmış** kayıtlar (Bölüm 7) bu rapora girer.
- `Toplam Tutar`, indirim varsa indirimli tutarı yansıtır (Bölüm 5).

---

## 7. Raporlama

- Kapsam: **sadece onaylanmış** kayıtlar (taslak, onay bekleyen,
  reddedilen, iptal edilen kayıtlar dahil değil).
- Görünürlük: kullanıcının manager zincirindeki herkesin onaylanmış
  kayıtları (bkz. Bölüm 4).
- Filtreler: gün / ay / yıl, kişi, birim.
- **Para birimi: USD.** Azure Retail Prices API zaten USD döndürüyor,
  uygulama boyunca (onay ekranı, dashboard, raporlar, export) hiçbir
  kur çevrimi yapılmaz.
- Export formatı: bkz. Bölüm 6.2 (Export Türü B).

---

## 8. Rol Bazlı Panel Yapısı (4 kademe)

> **Not:** Bu panel yapısı ilk sürüm içindir, **kapalı/final değildir.**
> İleride yeni ekranlar, yeni roller veya mevcut ekranlara yeni
> alanlar eklenmesi öngörülmelidir — mimari buna izin verecek şekilde
> (rol bazlı menü render'ı, merkezi yetki kontrolü) kurulmalı, sabit/
> donuk bir menü listesi olarak kodlanmamalı.

Ortak iskelet: sol sabit menü (role göre değişir) + sağ üstte bildirim
zili, kullanıcı adı/unvan/rol rozeti.

### 8.1 Çalışan Paneli (`calisan`)

```
├─ Ana Sayfa           (kişisel özet: taslak sayısı, bekleyen, reddedilen)
├─ Yeni Hesaplama       (mevcut hesaplama ekranı + kalem başına opsiyonel
│                          indirim % alanı + Taslak Kaydet / Onaya Gönder)
├─ Hesaplamalarım       (durum filtreli liste, reddedilende "Düzenle ve Tekrar Gönder")
└─ Profilim             (AD'den gelen bilgi, salt okunur)
```

### 8.2 Yönetici Paneli (`yonetici`)

Çalışan panelindeki her şeye ek olarak:

```
├─ Ana Sayfa            (+ onay bekleyen sayısı, bu ay özet)
├─ Onay Kuyruğu (N)     (bekleyen talepler; detayda kalem kalem liste + Onayla/Reddet)
├─ Ekibim               (manager zincirindeki herkesin onaylanmış/iptal edilmiş geçmişi)
├─ Raporlar             (Bölüm 7)
├─ Yeni Hesaplama
├─ Hesaplamalarım
└─ Profilim
```

### 8.3 Direktör Paneli (`direktor`)

Yönetici panelindeki her şeye ek olarak:

```
├─ Ana Sayfa
├─ Onay Kuyruğu (N)
├─ Departman Görünümü   (altındaki her bölüm müdürünün ayrı ayrı özeti)
├─ Ekibim
├─ Raporlar
├─ Yeni Hesaplama
├─ Hesaplamalarım
└─ Profilim
```

**İptal Et yetkisi:** Bir hesaplamanın detay ekranında "İptal Et"
butonu sadece şu koşulda görünür: giriş yapan kişi, o kaydın
departmanının "departman başı"ysa (bkz. Bölüm 1.7). Bu, rol bazlı değil
**kayıt bazlı** bir kontrol — `direktor` rolündeki herkes bu butonu
görmez, sadece ilgili departmanın başı olan kişi görür.

### 8.4 Admin Paneli (`admin`)

Baseline (kesin) ekranlar:

```
├─ Ana Sayfa
├─ Tüm Kayıtlar             (departman/kişi sınırı olmadan tüm hesaplamalar)
├─ Kullanıcı ve Rol Görünümü (AD'den senkronize, SALT OKUNUR)
├─ Raporlar (Şirket Geneli)
└─ Sistem Durumu             (LDAP/LDAPS bağlantı durumu, son senkronizasyon)
```

Admin'de "Yeni Hesaplama" ve "Hesaplamalarım" YOK — Aslı Demirtaş
hiçbir departmana bağlı değil.

**Ek admin yetkileri henüz kararlaştırılmadı — bkz. Bölüm 9.**

---

## 9. Admin Yetkisi — Seçenekler (karar bekliyor)

Gerçek şirketlerde bir "sistem admini" rolü genelde şu dört kategoride
yetkiye sahiptir. Baseline (Bölüm 8.4) zaten en temel gözetim
yetkilerini içeriyor. Aşağıdakiler **eklenebilecek** yetkiler —
hiçbiri zorunlu değil, seçmen gereken bir menü:

### A) Kullanıcı / Rol Yönetimi

| Seçenek | Ne yapar | Risk / Not |
|---|---|---|
| Sadece görüntüleme (mevcut baseline) | AD'den gelen rolü izler, değiştiremez | En güvenli, kaynak tek (AD) |
| Uygulama içi geçici rol override | Admin, AD'ye dokunmadan bir kullanıcının uygulama rolünü geçici değiştirebilir (örn. biri izinliyken vekaleten yönetici yapmak) | Kullanışlı ama **iki kaynak** oluşur (AD + uygulama), senkron karmaşası yaratabilir |
| Kullanıcıyı uygulamadan geçici men etme | AD'de hesap aktif olsa bile uygulamaya girişi admin kapatabilir | Biri ayrıldığında AD güncellenene kadar geçici önlem olarak faydalı |

### B) İş Kuralı Yapılandırması

| Seçenek | Ne yapar |
|---|---|
| Maksimum indirim yüzdesi sınırı | Admin, "hiçbir kalemde %30'dan fazla indirim girilemez" gibi bir üst sınır koyabilir |
| Departman başı listesini manuel override | Normalde AD'den otomatik gelir (Bölüm 1.7); admin istisnai durumda elle değiştirebilir |

### C) Denetim / Aktivite Günlüğü

| Seçenek | Ne yapar |
|---|---|
| İşlem geçmişi (audit log) | Kim ne zaman onayladı/reddetti/iptal etti — Sistem Durumu ekranına eklenebilecek bir "Aktivite Günlüğü" alt sekmesi |
| Sadece son N gün | Log'un ne kadar geriye gideceği sınırlandırılabilir (depolama için) |

### D) Acil Müdahale Yetkisi

| Seçenek | Ne yapar | Risk / Not |
|---|---|---|
| Admin her zaman iptal edebilir | Bölüm 2.1'deki "sadece departman başı iptal eder" kuralına admin için istisna tanınır | Bu, Bölüm 2.1'deki kararla **çelişir** — bilinçli bir istisna olarak eklenmeli, sessizce değil |
| Kilitli/donmuş bir kaydı serbest bırakma | Örn. onay_bekliyor durumunda takılı kalmış bir kaydı admin taslağa geri döndürebilir | Nadiren gerekir ama gerçek sistemlerde "kurtarma valfi" olarak bulunur |

### Önerim

Faz 1 için **A'nın ilk seçeneği (sadece görüntüleme) + C (aktivite
günlüğü)** yeterli ve düşük risklidir — mevcut baseline'a sadece
aktivite günlüğü eklemek, admin'i gerçek bir "gözetim" rolüne
kavuşturur ama iki kaynaklı veri riskine girmez. B ve D, gerçek
ihtiyaç ortaya çıktıkça (örn. bir kayıt "acil iptal" gerektirdiğinde)
Faz 2'de eklenebilir.

---

## 10. Netleştirilmesi gereken açık noktalar

1. **Samba AD DC'de LDAPS kurulumu** — bkz. Bölüm 0.
2. **Yöneticiler/direktörler kendi hesaplamasını oluşturabiliyor mu?**
   (Bölüm 4'te "evet" varsayıldı, teyit gerekiyor.)
3. **Admin taslakları görebiliyor mu?** (Bölüm 4'te "hayır" varsayıldı,
   teyit gerekiyor.)
4. **İndirimli fiyatların toplam maliyet hesaplarına yansıması** —
   Bölüm 5'te "evet, indirimli fiyat esas alınır" varsayıldı, teyit
   gerekiyor.
5. **İptal gerekçesi zorunlu olsun mu?** Şu an opsiyonel bırakıldı,
   teyit gerekiyor.
6. **Admin'in ek yetkileri** — Bölüm 9'daki seçeneklerden hangisi/
   hangileri dahil edilecek, henüz seçilmedi.

---

## 11. Önerilen Ek Özellikler

Zorunlu değil, ama gerçek şirket ortamında kullanılan uygulamalarda
genelde bulunan eklemeler. Öncelik sırasına göre:

### 11.1 Bildirim tetikleyicileri (yüksek öncelik)

- Çalışana: "talebiniz onaylandı" / "reddedildi (gerekçe: ...)" /
  "iptal edildi"
- Yöneticiye/direktöre: "yeni bir onay talebi geldi"
- Departman başının üstüne: "X departmanında bir kayıt iptal edildi"

### 11.2 Arama ve filtreleme (yüksek öncelik)

- **Ekibim** — kişi adına göre arama
- **Onay Kuyruğu** — birim/tarih aralığına göre filtre
- **Admin → Tüm Kayıtlar** — departman, durum, tarih aralığı, çalışan
  adına göre filtre

### 11.3 Boş durum (empty state) mesajları (orta öncelik)

Onay Kuyruğu'nda hiç bekleyen talep yoksa boş tablo yerine "Şu an
bekleyen talebiniz yok" gibi bir mesaj; Hesaplamalarım'da hiç taslak
yoksa "İlk hesaplamanızı oluşturun" + buton.

### 11.4 Vekalet / devir sistemi (düşük öncelik, Faz 2 önerisi)

Yönetici izinliyken onay talepleri kimin üzerine gidecek? İlk sürümde
olmasa da olur, ama gerçek kullanımda ortaya çıkması muhtemel bir
ihtiyaç.

### 11.5 Sayfalama (pagination) (orta öncelik)

Ekibim, Onay Kuyruğu, Tüm Kayıtlar gibi listeler zamanla uzayacak;
baştan sayfalı (örn. 20 kayıt/sayfa) tasarlanması önerilir.

Uygulandı: Onay kuyruğu, raporlar, aktivite/giriş günlüğü ve geçmiş arama
20 kayıt/sayfa (geçmiş kişisel listeler 50). Filtreler query parametresi
ile sunucuda uygulanır.
