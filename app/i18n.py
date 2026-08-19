"""Turkce/Ingilizce metin kaynaklari.

Tum menu, buton, alan etiketi, aciklama, dogrulama/hata mesaji ve Excel
disa aktarim basligi buradan gelir. Azure SKU adlari, teknik kimlikler ve
resmi urun adlari (orn. "Standard_D2s_v3", "Premium SSD v2") CEVRILMEZ.
"""

from typing import Literal

from fastapi import Request

Dil = Literal["tr", "en"]
VARSAYILAN_DIL: Dil = "tr"
DIL_COOKIE_ADI = "dil"
DESTEKLENEN_DILLER: tuple[Dil, ...] = ("tr", "en")

_METINLER: dict[str, dict[Dil, str]] = {
    # Genel / navigasyon
    "uygulama_adi": {"tr": "Pricing Calculator", "en": "Pricing Calculator"},
    "nav_ana_sayfa": {"tr": "Ana Sayfa", "en": "Home"},
    "nav_tahmin": {"tr": "Tahminim", "en": "Your Estimate"},
    "nav_gecmis": {"tr": "Gecmis", "en": "History"},
    "nav_yonetim": {"tr": "Yonetim", "en": "Administration"},
    "nav_cikis": {"tr": "Cikis Yap", "en": "Log out"},
    "nav_giris": {"tr": "Giris Yap", "en": "Log in"},
    "tema_degistir": {"tr": "Tema", "en": "Theme"},
    "tema_acik": {"tr": "Acik mod", "en": "Light mode"},
    "tema_koyu": {"tr": "Koyu mod", "en": "Dark mode"},
    "tema_pembe": {"tr": "Pembe mod", "en": "Pink mode"},
    # Giris ekrani
    "giris_baslik": {"tr": "Giris Yap", "en": "Sign in"},
    "giris_kullanici_adi": {"tr": "Kullanici adi", "en": "Username"},
    "giris_sifre": {"tr": "Sifre", "en": "Password"},
    "giris_buton": {"tr": "Giris Yap", "en": "Sign in"},
    "giris_hata": {
        "tr": "Kullanici adi veya sifre hatali.",
        "en": "Incorrect username or password.",
    },
    "giris_tls_hata": {
        "tr": "LDAP TLS baglantisi kurulamadi. Windows Server AD DC uzerinde LDAPS (636) veya StartTLS acik olmali.",
        "en": "LDAP TLS connection failed. Enable LDAPS (port 636) or StartTLS on the Windows Server AD DC.",
    },
    "giris_gerekli": {
        "tr": "Bu sayfayi goruntulemek icin giris yapmalisiniz.",
        "en": "You must sign in to view this page.",
    },
    "yetki_yok": {
        "tr": "Bu islem icin yetkiniz yok.",
        "en": "You do not have permission to perform this action.",
    },
    # Ana sayfa / urun kartlari
    "ana_sayfa_giris": {
        "tr": "Bir urun secip tahmininize ekleyin.",
        "en": "Choose a product and add it to your estimate.",
    },
    "ana_sayfa_alt_metin": {
        "tr": "Aylik ve yillik Azure maliyetlerini daha hizli toparlamak icin urun ekleyin, duzenleyin ve saklayin.",
        "en": "Add, edit, and save products to prepare monthly and annual Azure cost estimates faster.",
    },
    "urun_vm_ad": {"tr": "Sanal Makineler", "en": "Virtual Machines"},
    "urun_vm_aciklama": {
        "tr": "Saniyeler icinde Windows ve Linux sanal makineleri olusturun.",
        "en": "Provision Windows and Linux VMs in seconds.",
    },
    "urun_disk_ad": {"tr": "Yonetilen Diskler", "en": "Managed Disks"},
    "urun_disk_aciklama": {
        "tr": "Azure sanal makineleri icin kalici, guvenli disk depolama.",
        "en": "Persistent, secured disk storage for Azure virtual machines.",
    },
    "tahmine_ekle": {"tr": "Tahmine ekle", "en": "Add to estimate"},
    # Tahmin (estimate) alani
    "tahmin_baslik": {"tr": "Tahminim", "en": "Your Estimate"},
    "tahmin_bos": {
        "tr": "Tahmininiz bos. Yukaridan bir urun ekleyin.",
        "en": "Your estimate is empty. Add a product above.",
    },
    "tahmin_aylik_toplam": {"tr": "Tahmini aylik toplam", "en": "Estimated monthly total"},
    "tahmin_kaldir": {"tr": "Kaldir", "en": "Remove"},
    "tahmin_aylik_maliyet": {"tr": "Aylik maliyet", "en": "Monthly cost"},
    "para_birimi": {"tr": "Para birimi", "en": "Currency"},
    "dil_degistir": {"tr": "Dil", "en": "Language"},
    "disa_aktar": {"tr": "Excel'e aktar", "en": "Export to Excel"},
    "disa_aktar_bos_hata": {
        "tr": "Tahmininiz bos, disa aktarilacak bir sey yok.",
        "en": "Your estimate is empty, there is nothing to export.",
    },
    "fiyat_bulunamadi": {
        "tr": "Bu yapilandirma icin gecerli bir Azure fiyati bulunamadi. "
        "Lutfen secimlerinizi degistirip tekrar deneyin.",
        "en": "No valid Azure price was found for this configuration. "
        "Please change your selections and try again.",
    },
    "fiyat_servisi_erisilemez": {
        "tr": "Azure fiyat servisine su anda ulasilamiyor. Lutfen daha sonra tekrar deneyin.",
        "en": "The Azure pricing service is currently unavailable. Please try again later.",
    },
    "hesaplama_adi": {"tr": "Tahmin adi", "en": "Estimate name"},
    "kaydet": {"tr": "Kaydet", "en": "Save"},
    "kaydet_basarili": {"tr": "kaydedildi.", "en": "saved."},
    "kaydet_ad_gerekli": {
        "tr": "Lutfen tahmine bir ad verin.",
        "en": "Please give the estimate a name.",
    },
    "kaydet_bos_sepet": {
        "tr": "Tahmininiz bos, kaydedilecek bir sey yok.",
        "en": "Your estimate is empty, there is nothing to save.",
    },
    "gecmis_baslik": {"tr": "Gecmis Tahminler", "en": "Estimate History"},
    "gecmis_bos": {"tr": "Henuz kaydedilmis bir tahmin yok.", "en": "No saved estimates yet."},
    "gecmis_aciklama": {
        "tr": "Kaydedilen tahminleri inceleyin, detaylarini acin ve artik gerekmeyenleri kaldirin.",
        "en": "Review saved estimates, open their details, and remove entries you no longer need.",
    },
    "gecmis_karsilastir": {
        "tr": "Secilen 2 tahmini karsilastir",
        "en": "Compare the selected 2 estimates",
    },
    "gecmis_iki_secim_gerekli": {
        "tr": "Karsilastirma icin listeden tam olarak 2 tahmin secmelisiniz.",
        "en": "You must select exactly 2 estimates from the list to compare.",
    },
    "gecmis_bulunamadi": {
        "tr": "Secilen tahminlerden biri bulunamadi.",
        "en": "One of the selected estimates could not be found.",
    },
    "karsilastirma_baslik": {"tr": "Tahmin Karsilastirmasi", "en": "Estimate Comparison"},
    "karsilastirma_fark": {"tr": "Fark", "en": "Difference"},
    "karsilastirma_aciklama": {
        "tr": "Iki kayitli tahminin kalem ve toplam maliyet farklarini yan yana inceleyin.",
        "en": "Review itemized and total cost differences between two saved estimates side by side.",
    },
    "geri": {"tr": "Geri", "en": "Back"},
    "kayit": {"tr": "kayıt", "en": "records"},
    "kalem_sayisi": {"tr": "Kalem sayisi", "en": "Item count"},
    "tarih": {"tr": "Tarih", "en": "Date"},
    "ad": {"tr": "Ad", "en": "Name"},
    "toplam_aylik": {"tr": "Toplam (aylik)", "en": "Total (monthly)"},
    "toplam_yillik": {"tr": "Toplam (yillik)", "en": "Total (annual)"},
    "tahmin_yillik_maliyet": {"tr": "Tahmini yillik toplam", "en": "Estimated annual total"},
    "yillik_maliyet": {"tr": "Yillik maliyet", "en": "Annual cost"},
    "yeni_tahmin": {"tr": "Yeni tahmin", "en": "New estimate"},
    "olusturan": {"tr": "Olusturan", "en": "Created by"},
    "sil": {"tr": "Sil", "en": "Delete"},
    "sil_onay": {
        "tr": "Bu tahmini silmek istediginizden emin misiniz?",
        "en": "Are you sure you want to delete this estimate?",
    },
    "silindi": {"tr": "Tahmin silindi.", "en": "Estimate deleted."},
    "detay": {"tr": "Detay", "en": "Detail"},
    "gecmis_detay_baslik": {"tr": "Tahmin Detayi", "en": "Estimate Detail"},
    "gecmis_detay_aciklama": {
        "tr": "Kayitli tahminin kalemlerini ve fiyat bilesenlerini ayrintili olarak inceleyin.",
        "en": "Review the saved estimate items and pricing components in detail.",
    },
    "gecmis_yalnizca_sahibi_erisebilir": {
        "tr": "Bu tahmine sadece olusturan kisi veya yoneticiler erisebilir.",
        "en": "Only the creator or administrators can access this estimate.",
    },
    # Yonetim
    "yonetim_baslik": {"tr": "Yonetim Paneli", "en": "Administration"},
    "yonetim_ozet": {
        "tr": "Erisim modeli gorunumu",
        "en": "Access model overview",
    },
    "yonetim_aciklama": {
        "tr": "Bu sayfa, Active Directory gruplarinin uygulama izinlerine "
        "nasil eslendigini gosterir. Esleme {dosya} dosyasindan yuklenir.",
        "en": "This page shows how Active Directory groups map to application "
        "permissions. The mapping is loaded from {dosya}.",
    },
    "yonetim_grup": {"tr": "AD Grubu", "en": "AD Group"},
    "yonetim_izinler": {"tr": "Izinler", "en": "Permissions"},
    # Ortak alan etiketleri (VM + Disk formlarinda kullanilir)
    "alan_bolge": {"tr": "Bolge", "en": "Region"},
    "alan_kademe": {"tr": "Kademe", "en": "Tier"},
    "alan_yedeklilik": {"tr": "Yedeklilik", "en": "Redundancy"},
    "alan_disk_boyutu": {"tr": "Disk boyutu", "en": "Disk size"},
    "alan_iops": {"tr": "IOPS", "en": "IOPS"},
    "alan_throughput": {"tr": "Aktarim hizi (MB/s)", "en": "Throughput (MB/s)"},
    "alan_adet_disk": {"tr": "Disk sayisi", "en": "Number of disks"},
    "alan_islem_adet": {
        "tr": "Islem birimi (10.000 islem)",
        "en": "Transaction units (10,000 transactions)",
    },
    "alan_anlik_goruntu": {"tr": "Anlik goruntu ekle", "en": "Add snapshot"},
    "alan_gizli_sifreleme": {
        "tr": "Gizli isletim sistemi sifrelemesi",
        "en": "Enable Confidential OS Encryption",
    },
    "alan_patlama": {"tr": "Disk patlamasini (bursting) etkinlestir", "en": "Enable disk bursting"},
    "alan_fiyatlandirma_modeli": {"tr": "Fiyatlandirma secenegi", "en": "Savings option"},
    "alan_sure_birimi": {"tr": "Sure birimi", "en": "Duration unit"},
    "alan_sure_miktar": {"tr": "Sure", "en": "Duration"},
    "alan_bolge_kaynak": {"tr": "Kaynak bolge", "en": "Source region"},
    "alan_bolge_hedef": {"tr": "Hedef bolge", "en": "Destination region"},
    # Fiyat bileseni adlari (dokumler ve satir detaylarinda kullanilir)
    "disk_bilesen_depolama": {"tr": "Depolama", "en": "Storage"},
    "disk_bilesen_islemler": {"tr": "Depolama islemleri", "en": "Storage transactions"},
    "disk_bilesen_anlik_goruntu": {"tr": "Anlik goruntu", "en": "Snapshot"},
    "disk_bilesen_gizli_sifreleme": {
        "tr": "Gizli isletim sistemi sifrelemesi",
        "en": "Confidential OS Encryption",
    },
    "disk_bilesen_iops": {"tr": "Ek IOPS", "en": "Additional IOPS"},
    "disk_bilesen_throughput": {"tr": "Ek aktarim hizi", "en": "Additional throughput"},
    "vm_alan_isletim_sistemi": {"tr": "Isletim sistemi", "en": "Operating system"},
    "vm_alan_yazilim_tipi": {"tr": "Tip", "en": "Type"},
    "vm_alan_kademe": {"tr": "Kademe", "en": "Tier"},
    "vm_alan_kategori": {"tr": "Kategori", "en": "Category"},
    "vm_alan_seri": {"tr": "Instance Serisi", "en": "Instance Series"},
    "vm_alan_instance": {"tr": "Instance", "en": "Instance"},
    "vm_alan_adet": {"tr": "Sanal makine sayisi", "en": "Virtual machines"},
    "vm_alan_fiyatlandirma_modeli": {"tr": "Tasarruf secenekleri", "en": "Savings options"},
    "vm_alan_hibrit_fayda": {"tr": "Azure Hybrid Benefit", "en": "Azure Hybrid Benefit"},
    "vm_bolum_disk": {"tr": "Yonetilen Diskler (bu VM icin)", "en": "Managed Disks (for this VM)"},
    "vm_bolum_bant_genisligi": {"tr": "Bant genisligi", "en": "Bandwidth"},
    "vm_alan_veri_transfer_tipi": {"tr": "Veri transfer tipi", "en": "Data Transfer Type"},
    "vm_alan_cikis_gb": {"tr": "Giden veri transferi (GB)", "en": "Outbound Data Transfer (GB)"},
    "vm_bilesen_compute": {"tr": "Islem (Compute)", "en": "Compute"},
    "vm_bilesen_os": {"tr": "Isletim sistemi / yazilim", "en": "Operating system / software"},
    "vm_bilesen_bant_genisligi": {"tr": "Bant genisligi", "en": "Bandwidth"},
    # Excel disa aktarim basliklari
    "xlsx_sayfa_adi": {"tr": "Tahmin", "en": "Estimate"},
    "xlsx_urun": {"tr": "Urun", "en": "Product"},
    "xlsx_ozet": {"tr": "Yapilandirma", "en": "Configuration"},
    "xlsx_bolge": {"tr": "Bolge", "en": "Region"},
    "xlsx_miktar": {"tr": "Miktar", "en": "Quantity"},
    "xlsx_birim": {"tr": "Birim", "en": "Unit"},
    "xlsx_birim_fiyat": {"tr": "Birim Fiyat", "en": "Unit Price"},
    "xlsx_ara_toplam": {"tr": "Ara Toplam (Aylik)", "en": "Subtotal (Monthly)"},
    "xlsx_genel_toplam": {"tr": "Genel Toplam (Aylik)", "en": "Grand Total (Monthly)"},
    "xlsx_genel_toplam_yillik": {"tr": "Genel Toplam (Yillik)", "en": "Grand Total (Annual)"},
    "xlsx_para_birimi": {"tr": "Para Birimi", "en": "Currency"},
    "xlsx_olusturulma_tarihi": {"tr": "Olusturulma Tarihi", "en": "Generated On"},
}


def t(anahtar: str, dil: Dil = VARSAYILAN_DIL, **bicimlendirme) -> str:
    girdi = _METINLER.get(anahtar)
    if girdi is None:
        return f"[[{anahtar}]]"
    metin = girdi.get(dil) or girdi.get(VARSAYILAN_DIL, f"[[{anahtar}]]")
    if bicimlendirme:
        return metin.format(**bicimlendirme)
    return metin


def istekten_dil_al(request: Request) -> Dil:
    deger = request.cookies.get(DIL_COOKIE_ADI)
    if deger in DESTEKLENEN_DILLER:
        return deger  # type: ignore[return-value]
    return VARSAYILAN_DIL


def form_alanindan_dil_al(deger: str | None) -> Dil:
    if deger in DESTEKLENEN_DILLER:
        return deger  # type: ignore[return-value]
    return VARSAYILAN_DIL
