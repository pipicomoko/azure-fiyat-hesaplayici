# Manual Testing Checklist — Azure Fiyat Hesaplayici

Base URL: `http://localhost:8000` (Docker Compose)  
Seed password: `Sirket123!`

## Functional checklist

- [ ] Login as `kerem.acar` → lands on usable workspace (`/` or `/tahmin`)
- [ ] Login as `asli.demirtas` → admin area (not full tahmin if no `hesaplama.kullan`)
- [ ] Wrong password shows error (no stack trace)
- [ ] Add **Virtual Machines** product → form renders, price appears (or clear warning)
- [ ] Windows + **SQL Server Standard** → price shows Compute + OS + Software (no “fiyat bulunamadı”)
- [ ] Add **Managed Disks** → price updates
- [ ] Change region/instance → HTMX recalculates without full page crash
- [ ] Save draft with name → appears under `/gecmis/taslaklar`
- [ ] Save without name → validation message
- [ ] Submit for approval with manager selected → `/gecmis/gonderilenler`
- [ ] Manager (`onur.simsek`) can approve/reject in `/onay-kuyrugu`
- [ ] Export Excel from estimate / history
- [ ] Language toggle TR/EN keeps estimate items
- [ ] Logout → `/giris`; `/tahmin` redirects to login

## Cross-browser

| Browser | Login | Estimate | Save | History | Notes |
|---------|-------|----------|------|---------|-------|
| Chrome  | [ ]   | [ ]      | [ ]  | [ ]     |       |
| Firefox | [ ]   | [ ]      | [ ]  | [ ]     |       |
| Safari  | [ ]   | [ ]      | [ ]  | [ ]     |       |
| Edge    | [ ]   | [ ]      | [ ]  | [ ]     |       |

## Mobile manual checks

- [ ] iPhone width (~390px): login form usable, buttons tappable
- [ ] Product list scroll works
- [ ] VM combo dropdown usable (or acceptable fallback)
- [ ] No horizontal overflow on `/tahmin`
- [ ] Sidebar/rail stacks without covering CTA

## Performance manual checks

- [ ] First load `/giris` < 3s on LAN
- [ ] Adding a VM returns price within ~10–15s (Retail API)
- [ ] No endless spinner after failed price
- [ ] Run `npm run lighthouse` — Performance ≥85, A11y ≥90, BP ≥90, SEO ≥85

## Security manual checks

- [ ] `.env` and `config/ad-ca.pem` not in git
- [ ] Passwords never appear in page HTML/source after login
- [ ] Session cookie `HttpOnly` (DevTools → Application)
- [ ] Direct `/tahmin/kaydet` without login rejected
- [ ] XSS: put `<script>alert(1)</script>` in estimate name — not executed
- [ ] HTTPS only in production (Cloudflare tunnel / reverse proxy)

## Error scenario checks

- [ ] Samba/LDAP down → clear TLS/login error (not blank 500)
- [ ] Stop network mid-price → recoverable UI
- [ ] Invalid product POST `/tahmin/kalem-ekle` → 400
- [ ] Unknown URL → 404
- [ ] Rejected estimate editable as draft
- [ ] Empty estimate export blocked

## Sign-off

| Role | Name | Date | Result |
|------|------|------|--------|
| Dev  |      |      | Pass / Fail |
| QA   |      |      | Pass / Fail |
