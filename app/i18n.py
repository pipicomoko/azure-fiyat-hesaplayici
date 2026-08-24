"""Turkce/Ingilizce metin kaynaklari.

Tum menu, buton, alan etiketi, aciklama, dogrulama/hata mesaji ve Excel
disa aktarim basligi buradan gelir. Azure SKU adlari, teknik kimlikler ve
resmi urun adlari (orn. "Virtual Machines", "Managed Disks",
"Standard_D2s_v3", "Premium SSD v2") CEVRILMEZ — dil TR olsa bile sabit EN kalir.
"""

from typing import Literal

from fastapi import Request

Dil = Literal["tr", "en"]
VARSAYILAN_DIL: Dil = "tr"
DIL_COOKIE_ADI = "dil"
DESTEKLENEN_DILLER: tuple[Dil, ...] = ("tr", "en")

_METINLER: dict[str, dict[Dil, str]] = {
    # Genel / navigasyon
    "uygulama_adi": {"tr": "Azure Maliyet Tahmini", "en": "Azure Cost Estimate"},
    "nav_ana_sayfa": {"tr": "Ana sayfa", "en": "Home"},
    "nav_tahmin": {"tr": "Tahminim", "en": "Estimate"},
    "nav_gecmis": {"tr": "Geçmiş", "en": "History"},
    "nav_taslaklar": {"tr": "Taslaklar", "en": "Drafts"},
    "nav_tahmin_gecmisi": {"tr": "Tahmin geçmişi", "en": "Estimate History"},
    "nav_gonderilenler": {"tr": "Onaya gönderilenler", "en": "Submitted"},
    "nav_arama": {"tr": "Arama", "en": "Search"},
    "nav_sirket_kayitlari": {"tr": "Şirket Kayıtları", "en": "Company Records"},
    "nav_departman_kayitlari": {
        "tr": "Departman Kayıtları",
        "en": "Department Records",
    },
    "nav_birim_kayitlari": {"tr": "Birim Kayıtları", "en": "Unit Records"},
    "bs_etiket": {"tr": "Birim Yönetimi", "en": "Unit Management"},
    "bs_baslik": {"tr": "Birim Yönetim Özeti", "en": "Unit Management Overview"},
    "bs_aciklama": {
        "tr": "Sorumlu olduğunuz organizasyonun maliyetlerini, ekip katkısını ve bekleyen onayları izleyin.",
        "en": "Track costs, team contribution, and pending approvals for your organization.",
    },
    "bs_onayli_maliyet": {"tr": "Birim onaylı maliyeti", "en": "Unit approved cost"},
    "bs_trend": {"tr": "Birim 12 Aylık Trendi", "en": "Unit 12-Month Trend"},
    "bs_ekip_ozeti": {"tr": "Birim Ekip Özeti", "en": "Unit Team Summary"},
    "bs_bana_bekleyen": {"tr": "Onayımı Bekleyenler", "en": "Waiting for My Approval"},
    "bs_son_kayitlar": {"tr": "Son Birim Kayıtları", "en": "Recent Unit Records"},
    "db_etiket": {"tr": "Departman Yönetimi", "en": "Department Management"},
    "db_baslik": {"tr": "Yönetim Özeti", "en": "Management Overview"},
    "db_aciklama": {
        "tr": "Departmanınızın onaylı maliyetlerini, ekip katkısını ve bekleyen kararları izleyin.",
        "en": "Track your department's approved costs, team contribution, and pending decisions.",
    },
    "db_onayli_maliyet": {
        "tr": "Departman onaylı maliyeti",
        "en": "Department approved cost",
    },
    "db_aktif_calisan": {"tr": "Aktif çalışan", "en": "Active employees"},
    "db_hesaplama_yapan": {
        "tr": "Dönemde onaylı kaydı olan",
        "en": "With approved records in period",
    },
    "db_trend": {"tr": "Departman 12 Aylık Trendi", "en": "Department 12-Month Trend"},
    "db_ekip_ozeti": {"tr": "Ekip Maliyet Özeti", "en": "Team Cost Summary"},
    "db_bana_bekleyen": {"tr": "Onayımı Bekleyenler", "en": "Waiting for My Approval"},
    "db_son_kayitlar": {
        "tr": "Son Departman Kayıtları",
        "en": "Recent Department Records",
    },
    "gm_etiket": {"tr": "Genel Müdür", "en": "General Manager"},
    "gm_baslik": {"tr": "Şirket Maliyet Özeti", "en": "Company Cost Overview"},
    "gm_aciklama": {
        "tr": "Onaylı Azure maliyetlerini, departmanları ve bekleyen kararları tek ekrandan izleyin.",
        "en": "Track approved Azure costs, departments, and pending decisions in one place.",
    },
    "gm_donem_filtre": {"tr": "Rapor dönemi", "en": "Reporting period"},
    "gm_departman_filtre": {"tr": "Departman", "en": "Department"},
    "gm_alt_birim_filtre": {"tr": "Alt birim", "en": "Sub-unit"},
    "gm_tum_alt_birimler": {"tr": "Tüm alt birimler", "en": "All sub-units"},
    "gm_tarih_hatasi": {
        "tr": "Tarih aralığı geçersizdi; içinde bulunulan ay gösteriliyor.",
        "en": "The date range was invalid; the current month is shown.",
    },
    "gm_onayli_maliyet": {"tr": "Onaylı aylık maliyet", "en": "Approved monthly cost"},
    "gm_bekleyen": {
        "tr": "Bekleyen potansiyel maliyet",
        "en": "Pending potential cost",
    },
    "gm_kayit_adedi": {"tr": "{adet} kayıt", "en": "{adet} records"},
    "gm_donem_icinde": {
        "tr": "Seçilen dönem içinde",
        "en": "Within the selected period",
    },
    "gm_trend": {"tr": "12 Aylık Maliyet Trendi", "en": "12-Month Cost Trend"},
    "gm_trend_aciklama": {
        "tr": "Onay tarihine göre aylık maliyet; para birimleri ayrı gösterilir.",
        "en": "Monthly cost by approval date; currencies are shown separately.",
    },
    "gm_tabloyu_goster": {"tr": "Veri tablosunu göster", "en": "Show data table"},
    "gm_departmanlar": {
        "tr": "Departman Karşılaştırması",
        "en": "Department Comparison",
    },
    "gm_bana_bekleyen": {"tr": "Kararımı Bekleyenler", "en": "Waiting for My Decision"},
    "gm_en_yuksek": {
        "tr": "En Yüksek Maliyetli Kayıtlar",
        "en": "Highest-Cost Records",
    },
    "gm_son_kayitlar": {"tr": "Son Şirket Kayıtları", "en": "Recent Company Records"},
    "gm_veri_yok": {"tr": "Bu görünümde kayıt yok.", "en": "No records in this view."},
    "baslangic": {"tr": "Başlangıç", "en": "Start"},
    "bitis": {"tr": "Bitiş", "en": "End"},
    "filtrele": {"tr": "Filtrele", "en": "Filter"},
    "donem": {"tr": "Dönem", "en": "Period"},
    "tumunu_gor": {"tr": "Tümünü gör", "en": "View all"},
    "pano_baslik": {"tr": "Pano", "en": "Dashboard"},
    "pano_aciklama": {
        "tr": "Taslak, gönderilen, onaylanan ve reddedilen hesaplamalarınızın özeti.",
        "en": "Summary of your draft, submitted, approved, and rejected estimates.",
    },
    "pano_bos_grup": {
        "tr": "Bu durumda kayıt yok.",
        "en": "No records in this status.",
    },
    "pano_bekleyen_onay": {
        "tr": "Onay kuyruğunuzda {adet} bekleyen hesaplama var.",
        "en": "You have {adet} estimates waiting in your approval queue.",
    },
    "nav_onay": {"tr": "Onay Kuyruğu", "en": "Approval Queue"},
    "nav_raporlar": {"tr": "Raporlar", "en": "Reports"},
    "nav_aktivite": {"tr": "Aktivite", "en": "Activity"},
    "nav_giris_gunlugu": {"tr": "Giriş günlüğü", "en": "Sign-in log"},
    "giris_gunlugu_baslik": {"tr": "Giriş günlüğü", "en": "Sign-in log"},
    "giris_gunlugu_aciklama": {
        "tr": "Başarılı ve başarısız giriş denemeleri (şifre kaydedilmez). 90 gün saklanır.",
        "en": "Successful and failed sign-in attempts (passwords are never stored). Kept for 90 days.",
    },
    "giris_gunlugu_bos": {
        "tr": "Henüz giriş kaydı yok.",
        "en": "No sign-in records yet.",
    },
    "giris_sonuc_basarili": {"tr": "Başarılı", "en": "Success"},
    "giris_sonuc_basarisiz": {"tr": "Başarısız", "en": "Failed"},
    "giris_sonuc_kilitli": {"tr": "Hız sınırı", "en": "Rate limited"},
    "sonuc": {"tr": "Sonuç", "en": "Result"},
    "hata_tipi": {"tr": "Hata tipi", "en": "Error type"},
    "kullanici_adi": {"tr": "Kullanıcı adı", "en": "Username"},
    "nav_yonetim": {"tr": "Yönetim", "en": "Administration"},
    "nav_cikis": {"tr": "Çıkış yap", "en": "Log out"},
    "nav_giris": {"tr": "Giriş Yap", "en": "Log in"},
    "tema_degistir": {"tr": "Tema", "en": "Theme"},
    "tema_acik": {"tr": "Açık mod", "en": "Light mode"},
    "tema_koyu": {"tr": "Koyu mod", "en": "Dark mode"},
    "tema_pembe": {"tr": "Pembe mod", "en": "Pink mode"},
    # Giris ekrani
    "giris_baslik": {"tr": "Giriş Yap", "en": "Sign in"},
    "giris_kullanici_adi": {"tr": "Kullanıcı adı", "en": "Username"},
    "giris_sifre": {"tr": "Şifre", "en": "Password"},
    "giris_buton": {"tr": "Giriş Yap", "en": "Sign in"},
    "giris_hata": {
        "tr": "Kullanıcı adı veya şifre hatalı.",
        "en": "Incorrect username or password.",
    },
    "giris_tls_hata": {
        "tr": "LDAP TLS bağlantısı kurulamadı. Windows Server AD DC üzerinde LDAPS (636) veya StartTLS açık olmalı.",
        "en": "LDAP TLS connection failed. Enable LDAPS (port 636) or StartTLS on the Windows Server AD DC.",
    },
    "giris_gerekli": {
        "tr": "Bu sayfayı görüntülemek için giriş yapmalısınız.",
        "en": "You must sign in to view this page.",
    },
    "yetki_yok": {
        "tr": "Bu işlem için yetkiniz yok.",
        "en": "You do not have permission to perform this action.",
    },
    # Ana sayfa / urun kartlari
    "ana_sayfa_giris": {
        "tr": "Bir ürün seçip tahmininize ekleyin.",
        "en": "Choose a product and add it to your estimate.",
    },
    "ana_sayfa_alt_metin": {
        "tr": "Aylık ve yıllık Azure maliyetlerini daha hızlı toparlamak için ürün ekleyin, düzenleyin ve saklayın.",
        "en": "Add, edit, and save products to prepare monthly and annual Azure cost estimates faster.",
    },
    # Azure urun adlari dil bagimsiz (TR arayuzde de orijinal EN kalir)
    "urun_vm_ad": {"tr": "Virtual Machines", "en": "Virtual Machines"},
    "urun_vm_aciklama": {
        "tr": "Saniyeler içinde Windows ve Linux sanal makineleri oluşturun.",
        "en": "Provision Windows and Linux VMs in seconds.",
    },
    "urun_disk_ad": {"tr": "Managed Disks", "en": "Managed Disks"},
    "urun_disk_aciklama": {
        "tr": "Azure sanal makineleri için kalıcı, güvenli disk depolama.",
        "en": "Persistent, secured disk storage for Azure virtual machines.",
    },
    "tahmine_ekle": {"tr": "Tahmine ekle", "en": "Add to estimate"},
    "urun_ekle_baslik": {"tr": "Ürün ekle", "en": "Add product"},
    "urun_ara": {"tr": "Ürün ara...", "en": "Search products..."},
    "ekle": {"tr": "Ekle", "en": "Add"},
    "tahmin_kalemleri": {"tr": "Tahmin ürünleri", "en": "Estimate products"},
    "ozet_baslik": {"tr": "Özet", "en": "Summary"},
    "adet_kisa": {"tr": "Adet", "en": "Qty"},
    # Tahmin (estimate) alani
    "tahmin_baslik": {"tr": "Tahminim", "en": "Your Estimate"},
    "tahmin_bos": {
        "tr": "Henüz ürün eklemediniz. Yukarıdan bir ürün ekleyin.",
        "en": "No products yet. Add a product above.",
    },
    "tahmin_aylik_toplam": {
        "tr": "Tahmini aylık toplam",
        "en": "Estimated monthly total",
    },
    "tahmin_kaldir": {"tr": "Kaldır", "en": "Remove"},
    "tahmin_aylik_maliyet": {"tr": "Aylık maliyet", "en": "Monthly cost"},
    "para_birimi": {"tr": "Para birimi", "en": "Currency"},
    "dil_degistir": {"tr": "Dil", "en": "Language"},
    "disa_aktar": {"tr": "Excel'e aktar", "en": "Export to Excel"},
    "excel_aktar": {"tr": "Excel'e aktar", "en": "Export to Excel"},
    "excel_aktar_tumu": {"tr": "Tümünü Excel'e aktar", "en": "Export all to Excel"},
    "disa_aktar_bos_hata": {
        "tr": "Tahmininiz boş, dışa aktarılacak bir şey yok.",
        "en": "Your estimate is empty, there is nothing to export.",
    },
    "fiyat_bulunamadi": {
        "tr": "Bu yapılandırma için geçerli bir Azure fiyatı bulunamadı. "
        "Lütfen seçimlerinizi değiştirip tekrar deneyin.",
        "en": "No valid Azure price was found for this configuration. "
        "Please change your selections and try again.",
    },
    "gecersiz_yapilandirma": {
        "tr": "Geçersiz yapılandırma. Lütfen listeden geçerli bir seçim yapın; tahmini fiyat gösterilmez.",
        "en": "Invalid configuration. Choose a valid option from the list; estimated prices are never shown.",
    },
    "giris_hiz_siniri": {
        "tr": "Çok fazla başarısız giriş denemesi. Lütfen bir dakika sonra tekrar deneyin.",
        "en": "Too many failed sign-in attempts. Please try again in a minute.",
    },
    "sayfalama": {"tr": "Sayfalama", "en": "Pagination"},
    "fiyat_servisi_erisilemez": {
        "tr": "Azure fiyat servisine şu anda ulaşılamıyor. Lütfen daha sonra tekrar deneyin.",
        "en": "The Azure pricing service is currently unavailable. Please try again later.",
    },
    "hesaplama_adi": {"tr": "Tahmin adı", "en": "Estimate name"},
    "kaydet": {"tr": "Kaydet", "en": "Save"},
    "taslak_kaydet": {"tr": "Taslak kaydet", "en": "Save draft"},
    "tahmin_kaydet": {"tr": "Kaydet", "en": "Save"},
    "tahmin_kaydedildi": {"tr": "kaydedildi.", "en": "saved."},
    "onaya_gonder": {"tr": "Onaya gönder", "en": "Submit for approval"},
    "onay_hedefi": {"tr": "Onaylayacak yönetici", "en": "Approver"},
    "onay_hedefi_sec": {"tr": "Seçiniz", "en": "Select"},
    "onay_hedefi_gerekli": {
        "tr": "Onaya göndermek için listeden bir yönetici seçin.",
        "en": "Select an approver from the list before submitting.",
    },
    "onay_hedefi_kendisi_olamaz": {
        "tr": "Onaylayacak yönetici kendiniz olamaz.",
        "en": "You cannot select yourself as the approver.",
    },
    "onay_hedefi_zincirde_yok": {
        "tr": "Seçilen onaycı yönetici zincirinizde değil.",
        "en": "The selected approver is not in your manager chain.",
    },
    "onay_kendi_kayit_yasak": {
        "tr": "Kendi oluşturduğunuz kaydı onaylayamaz veya reddedemezsiniz.",
        "en": "You cannot approve or reject an estimate you created.",
    },
    "onay_zincir_yok": {
        "tr": "Yönetici zinciriniz bulunamadı; şu an yalnızca taslak kaydedebilirsiniz. Çıkış yapıp tekrar giriş deneyin.",
        "en": "Your manager chain was not found; you can only save drafts for now. Sign out and sign in again.",
    },
    "ustu_olmayan_kayit_bilgi": {
        "tr": "Bu kayıtlar yalnızca sizin tahmin geçmişinizde tutulur; onay akışına gönderilmez.",
        "en": "These estimates stay in your private history and are not submitted for approval.",
    },
    "gecmis_tahmin_gecmisi": {"tr": "Tahmin geçmişi", "en": "Estimate History"},
    "gecmis_tahmin_gecmisi_bos": {
        "tr": "Henüz kayıtlı tahmin yok.",
        "en": "No saved estimates yet.",
    },
    "indirim_yuzdesi": {"tr": "İndirim %", "en": "Discount %"},
    "durum": {"tr": "Durum", "en": "Status"},
    "durum_taslak": {"tr": "Taslak", "en": "Draft"},
    "durum_onay_bekliyor": {"tr": "Onay bekliyor", "en": "Pending approval"},
    "durum_onaylandi": {"tr": "Onaylandı", "en": "Approved"},
    "durum_reddedildi": {"tr": "Reddedildi", "en": "Rejected"},
    "durum_iptal_edildi": {"tr": "İptal edildi", "en": "Cancelled"},
    "duzenle": {"tr": "Düzenle", "en": "Edit"},
    "duzenle_tekrar_gonder": {
        "tr": "Düzenle ve tekrar gönder",
        "en": "Edit and resubmit",
    },
    "gecmis_taslaklar": {"tr": "Taslaklar", "en": "Drafts"},
    "gecmis_gonderilenler": {
        "tr": "Onaya gönderilenler",
        "en": "Submitted for approval",
    },
    "gecmis_taslak_bos": {"tr": "Henüz taslak yok.", "en": "No drafts yet."},
    "gecmis_gonderilen_bos": {
        "tr": "Henüz onaya gönderilmiş kayıt yok.",
        "en": "No submitted estimates yet.",
    },
    "gecmis_tum_durumlar": {"tr": "Tüm durumlar", "en": "All statuses"},
    "onayla": {"tr": "Onayla", "en": "Approve"},
    "reddet": {"tr": "Reddet", "en": "Reject"},
    "gerekce": {"tr": "Gerekçe (opsiyonel)", "en": "Reason (optional)"},
    "iptal_et": {"tr": "İptal et", "en": "Cancel estimate"},
    "red_gerekce": {"tr": "Red gerekçesi", "en": "Rejection reason"},
    "iptal_gerekce": {"tr": "İptal gerekçesi", "en": "Cancellation reason"},
    "onay_baslik": {"tr": "Onay Kuyruğu", "en": "Approval Queue"},
    "onay_aciklama": {
        "tr": "Size yöneltilen onay bekleyen hesaplamalar.",
        "en": "Estimates waiting for your approval.",
    },
    "onay_bos": {"tr": "Bekleyen onay yok.", "en": "No pending approvals."},
    "aktivite_baslik": {"tr": "Aktivite Günlüğü", "en": "Activity Log"},
    "aktivite_aciklama": {
        "tr": "Onay, red ve iptal işlemlerinin kaydı.",
        "en": "Log of approve, reject, and cancel actions.",
    },
    "aktivite_bos": {"tr": "Henüz kayıt yok.", "en": "No activity yet."},
    "aktor": {"tr": "Aktör", "en": "Actor"},
    "islem": {"tr": "İşlem", "en": "Action"},
    "rapor_baslik": {"tr": "Raporlar", "en": "Reports"},
    "rapor_aciklama": {
        "tr": "Yalnızca onaylanmış kayıtlar (USD).",
        "en": "Approved estimates only (USD).",
    },
    "rapor_bos": {
        "tr": "Filtreye uyan onaylanmış kayıt yok.",
        "en": "No matching approved estimates.",
    },
    "rapor_hepsini_export": {
        "tr": "Hepsini export et",
        "en": "Export all",
    },
    "rapor_export_secilen": {
        "tr": "Export seçilen ({n})",
        "en": "Export selected ({n})",
    },
    "rapor_sec": {"tr": "Seç", "en": "Select"},
    "rapor_secilen_yok": {
        "tr": "Önce en az bir kayıt seçin.",
        "en": "Select at least one estimate first.",
    },
    "birim": {"tr": "Birim", "en": "Unit"},
    "onaylayan": {"tr": "Onaylayan", "en": "Approved by"},
    "onay_tarihi": {"tr": "Onay tarihi", "en": "Approval date"},
    "onay_beklenen": {"tr": "Onay beklenen", "en": "Awaiting approval from"},
    "kaydet_basarili": {"tr": "taslak olarak kaydedildi.", "en": "saved as draft."},
    "onaya_gonderildi": {"tr": "onaya gönderildi.", "en": "submitted for approval."},
    "kaydet_ad_gerekli": {
        "tr": "Lütfen tahmine bir ad verin.",
        "en": "Please give the estimate a name.",
    },
    "kaydet_bos_sepet": {
        "tr": "Tahmininiz boş, kaydedilecek bir şey yok.",
        "en": "Your estimate is empty, there is nothing to save.",
    },
    "gecmis_baslik": {"tr": "Geçmiş Tahminler", "en": "Estimate History"},
    "gecmis_bos": {
        "tr": "Henüz kaydedilmiş bir tahmin yok.",
        "en": "No saved estimates yet.",
    },
    "gecmis_aciklama": {
        "tr": "Kaydedilen tahminleri inceleyin, detaylarını açın ve artık gerekmeyenleri kaldırın.",
        "en": "Review saved estimates, open their details, and remove entries you no longer need.",
    },
    "gecmis_karsilastir": {
        "tr": "Seçilen 2 tahmini karşılaştır",
        "en": "Compare the selected 2 estimates",
    },
    "gecmis_iki_secim_gerekli": {
        "tr": "Karşılaştırma için listeden tam olarak 2 tahmin seçmelisiniz.",
        "en": "You must select exactly 2 estimates from the list to compare.",
    },
    "gecmis_bulunamadi": {
        "tr": "Seçilen tahminlerden biri bulunamadı.",
        "en": "One of the selected estimates could not be found.",
    },
    "karsilastirma_baslik": {
        "tr": "Tahmin Karşılaştırması",
        "en": "Estimate Comparison",
    },
    "karsilastirma_fark": {"tr": "Fark", "en": "Difference"},
    "karsilastirma_aciklama": {
        "tr": "İki kayıtlı tahminin ürün ve toplam maliyet farklarını yan yana inceleyin.",
        "en": "Review product and total cost differences between two saved estimates side by side.",
    },
    "geri": {"tr": "Geri", "en": "Back"},
    "kayit": {"tr": "kayıt", "en": "records"},
    "kalem_sayisi": {"tr": "Ürün sayısı", "en": "Product count"},
    "tarih": {"tr": "Tarih", "en": "Date"},
    "ad": {"tr": "Ad", "en": "Name"},
    "toplam_aylik": {"tr": "Toplam (aylık)", "en": "Total (monthly)"},
    "toplam_yillik": {"tr": "Toplam (yıllık)", "en": "Total (annual)"},
    "tahmin_yillik_maliyet": {
        "tr": "Tahmini yıllık toplam",
        "en": "Estimated annual total",
    },
    "yillik_maliyet": {"tr": "Yıllık maliyet", "en": "Annual cost"},
    "yeni_tahmin": {"tr": "Yeni tahmin", "en": "New estimate"},
    "olusturan": {"tr": "Oluşturan", "en": "Created by"},
    "kopyala": {"tr": "Kopyala", "en": "Copy"},
    "sil": {"tr": "Sil", "en": "Delete"},
    "sil_onay": {
        "tr": "Bu tahmini silmek istediğinizden emin misiniz?",
        "en": "Are you sure you want to delete this estimate?",
    },
    "silindi": {"tr": "Tahmin silindi.", "en": "Estimate deleted."},
    "detay": {"tr": "Detay", "en": "Detail"},
    "gecmis_detay_baslik": {"tr": "Tahmin Detayı", "en": "Estimate Detail"},
    "gecmis_detay_aciklama": {
        "tr": "Kayıtlı tahminin ürünlerini ve fiyat bileşenlerini ayrıntılı olarak inceleyin.",
        "en": "Review the saved estimate products and pricing components in detail.",
    },
    "gecmis_yalnizca_sahibi_erisebilir": {
        "tr": "Bu tahmine sadece oluşturan kişi veya yöneticiler erişebilir.",
        "en": "Only the creator or administrators can access this estimate.",
    },
    "gecmis_personal": {"tr": "Kişisel", "en": "Personal"},
    "gecmis_arama": {"tr": "Arama", "en": "Search"},
    "gecmis_departman_sec": {"tr": "Departman seçin", "en": "Select department"},
    "gecmis_isim_ara": {"tr": "İsim ara...", "en": "Search by name..."},
    "ara": {"tr": "Ara", "en": "Search"},
    "gecmis_unvan": {"tr": "Ünvan", "en": "Title"},
    "gecmis_tum_departmanlar": {"tr": "Tüm departmanlar", "en": "All departments"},
    "gecmis_tarih_baslangic": {"tr": "Başlangıç", "en": "From"},
    "gecmis_tarih_bitis": {"tr": "Bitiş", "en": "To"},
    "gecmis_filtre_temizle": {"tr": "Temizle", "en": "Clear"},
    "gecmis_filtre_sonuc_yok": {
        "tr": "Seçilen filtrelere uygun kayıt yok.",
        "en": "No records match the selected filters.",
    },
    # Yonetim
    "yonetim_baslik": {"tr": "Yönetim Paneli", "en": "Administration"},
    "yonetim_ozet": {
        "tr": "Erişim modeli görünümü",
        "en": "Access model overview",
    },
    "yonetim_aciklama": {
        "tr": "Bu sayfa, Active Directory gruplarının uygulama izinlerine "
        "nasıl eşlendiğini gösterir. Eşleme {dosya} dosyasından yüklenir.",
        "en": "This page shows how Active Directory groups map to application "
        "permissions. The mapping is loaded from {dosya}.",
    },
    "yonetim_grup": {"tr": "AD Grubu", "en": "AD Group"},
    "yonetim_izinler": {"tr": "İzinler", "en": "Permissions"},
    # Ortak alan etiketleri (VM + Disk formlarinda kullanilir)
    "alan_bolge": {"tr": "Bölge", "en": "Region"},
    "alan_kademe": {"tr": "Kademe", "en": "Tier"},
    "alan_yedeklilik": {"tr": "Yedeklilik", "en": "Redundancy"},
    "alan_disk_boyutu": {"tr": "Disk boyutu", "en": "Disk size"},
    "alan_iops": {"tr": "IOPS", "en": "IOPS"},
    "alan_throughput": {"tr": "Aktarım hızı (MB/s)", "en": "Throughput (MB/s)"},
    "alan_adet_disk": {"tr": "Disk sayısı", "en": "Number of disks"},
    "alan_islem_adet": {
        "tr": "İşlem birimi (10.000 işlem)",
        "en": "Transaction units (10,000 transactions)",
    },
    "alan_anlik_goruntu": {"tr": "Anlık görüntü ekle", "en": "Add snapshot"},
    "alan_gizli_sifreleme": {
        "tr": "Gizli işletim sistemi şifrelemesi",
        "en": "Enable Confidential OS Encryption",
    },
    "alan_patlama": {
        "tr": "Disk patlamasını (bursting) etkinleştir",
        "en": "Enable disk bursting",
    },
    "alan_fiyatlandirma_modeli": {
        "tr": "Fiyatlandırma seçeneği",
        "en": "Savings option",
    },
    "alan_sure_birimi": {"tr": "Süre birimi", "en": "Duration unit"},
    "alan_sure_miktar": {"tr": "Süre", "en": "Duration"},
    "alan_bolge_kaynak": {"tr": "Kaynak bölge", "en": "Source region"},
    "alan_bolge_hedef": {"tr": "Hedef bölge", "en": "Destination region"},
    # Fiyat bileseni adlari (dokumler ve satir detaylarinda kullanilir)
    "disk_bilesen_depolama": {"tr": "Depolama", "en": "Storage"},
    "disk_bilesen_islemler": {"tr": "Depolama işlemleri", "en": "Storage transactions"},
    "disk_bilesen_anlik_goruntu": {"tr": "Anlık görüntü", "en": "Snapshot"},
    "disk_bilesen_gizli_sifreleme": {
        "tr": "Gizli işletim sistemi şifrelemesi",
        "en": "Confidential OS Encryption",
    },
    "disk_bilesen_iops": {"tr": "Ek IOPS", "en": "Additional IOPS"},
    "disk_bilesen_throughput": {"tr": "Ek aktarım hızı", "en": "Additional throughput"},
    "vm_alan_isletim_sistemi": {"tr": "İşletim sistemi", "en": "Operating system"},
    "vm_alan_yazilim_tipi": {"tr": "Tip", "en": "Type"},
    "vm_alan_kademe": {"tr": "Kademe", "en": "Tier"},
    "vm_alan_kategori": {"tr": "Kategori", "en": "Category"},
    "vm_alan_seri": {"tr": "Instance Serisi", "en": "Instance Series"},
    "vm_alan_instance": {"tr": "Instance", "en": "Instance"},
    "vm_alan_adet": {"tr": "Sanal makine sayısı", "en": "Virtual machines"},
    "vm_alan_fiyatlandirma_modeli": {
        "tr": "Tasarruf seçenekleri",
        "en": "Savings options",
    },
    "vm_alan_hibrit_fayda": {
        "tr": "Azure Hybrid Benefit",
        "en": "Azure Hybrid Benefit",
    },
    "vm_bolum_disk": {
        "tr": "Managed Disks (bu VM için)",
        "en": "Managed Disks (for this VM)",
    },
    "vm_bolum_bant_genisligi": {"tr": "Bant genişliği", "en": "Bandwidth"},
    "vm_alan_veri_transfer_tipi": {
        "tr": "Veri transfer tipi",
        "en": "Data Transfer Type",
    },
    "vm_alan_cikis_gb": {
        "tr": "Giden veri transferi (GB)",
        "en": "Outbound Data Transfer (GB)",
    },
    "vm_bilesen_compute": {"tr": "İşlem (Compute)", "en": "Compute"},
    "vm_bilesen_os": {
        "tr": "İşletim sistemi (Windows)",
        "en": "Operating system (Windows)",
    },
    "vm_bilesen_yazilim": {"tr": "Yazılım lisansı", "en": "Software license"},
    "vm_bilesen_bant_genisligi": {"tr": "Bant genişliği", "en": "Bandwidth"},
    # Excel disa aktarim basliklari
    "xlsx_sayfa_adi": {"tr": "Tahmin", "en": "Estimate"},
    "xlsx_baslik_satiri": {"tr": "Azure Fiyat Tahmini", "en": "Azure Pricing Estimate"},
    "xlsx_servis_tipi": {"tr": "Servis Tipi", "en": "Service type"},
    "xlsx_aciklama": {"tr": "Açıklama", "en": "Description"},
    "xlsx_tahmini_aylik_maliyet": {
        "tr": "Tahmini Aylık Maliyet",
        "en": "Estimated monthly cost",
    },
    "xlsx_urun": {"tr": "Ürün", "en": "Product"},
    "xlsx_ozet": {"tr": "Yapılandırma", "en": "Configuration"},
    "xlsx_bolge": {"tr": "Bölge", "en": "Region"},
    "xlsx_miktar": {"tr": "Miktar", "en": "Quantity"},
    "xlsx_birim": {"tr": "Birim", "en": "Unit"},
    "xlsx_birim_fiyat": {"tr": "Birim Fiyat", "en": "Unit Price"},
    "xlsx_ara_toplam": {"tr": "Ara Toplam (Aylık)", "en": "Subtotal (Monthly)"},
    "xlsx_genel_toplam": {"tr": "Genel Toplam (Aylık)", "en": "Grand Total (Monthly)"},
    "xlsx_genel_toplam_yillik": {
        "tr": "Genel Toplam (Yıllık)",
        "en": "Grand Total (Annual)",
    },
    "xlsx_para_birimi": {"tr": "Para Birimi", "en": "Currency"},
    "xlsx_olusturulma_tarihi": {"tr": "Oluşturulma Tarihi", "en": "Generated On"},
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
