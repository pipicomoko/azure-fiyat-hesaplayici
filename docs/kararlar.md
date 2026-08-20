# AFH — Onaylanan kararlar (Bölüm 10)

Bu dosya `docs/afh-proje-spesifikasyonu.md` Bölüm 10 açık noktalarının
yol haritası doğrultusunda kilitlenmiş halleridir. Uygulama ve seed
bu kararlara göre yazılır.

| # | Konu | Karar |
|---|---|---|
| 1 | Samba LDAPS | Geliştirmede de gerçek LDAPS (port 636). Düz LDAP geliştirme kaçışı yok. |
| 2 | Yöneticiler/direktörler kendi hesaplama yapar mı? | Evet. `AFH-Calisanlar` üyeliği ile hesaplama oluşturabilirler. |
| 3 | Admin taslakları görür mü? | Hayır. Admin yalnızca `onay_bekliyor` / `onaylandi` / `reddedildi` / `iptal_edildi` kayıtlarını görür. |
| 4 | İndirimli fiyat toplamda mı? | Evet. İndirim girilen kalemlerde indirimli tutar esas alınır. |
| 5 | İptal gerekçesi zorunlu mu? | Hayır (red ile tutarlı). UI gerekçeyi teşvik eder. |
| 6 | Admin ek yetkileri (Faz 1) | Salt okunur kullanıcı/rol görünümü + aktivite günlüğü (audit log). Rol override / acil iptal / iş kuralı yapılandırması sonraya bırakılır. |

## Cursor / build

Agent ve geliştirme: **Build locally**. Cloud / parallel bu fazda kullanılmaz.

## MCP

Şimdi kurulmaz. CI yeşilden sonra isteğe bağlı SonarQube/Refactoring;
dokümanlar oturunca Wikimind. Pars Core / Jira / Azure DevOps bu repoda
zorunlu değil (bkz. yol haritası §4).

Kurulum zamanı hatırlatması:
- CI yeşil + büyük yetki/onay PR’ları → Refactoring + SonarQube
- `docs/` oturunca → Wikimind
- Jira/ADO yalnızca gerçekten o araçlar kullanılıyorsa
