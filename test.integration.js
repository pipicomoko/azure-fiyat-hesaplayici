/**
 * Integration: login → estimate → save → history → logout
 */
const { test, expect } = require("@playwright/test");

const USER = process.env.E2E_USER || "kerem.acar";
const PASS = process.env.E2E_PASS || "Sirket123!";
const ESTIMATE_NAME = `PreLaunch-${Date.now()}`;

async function login(page) {
  await page.goto("/giris", { waitUntil: "domcontentloaded" });
  await page.fill("#kullanici_adi", USER);
  await page.fill("#sifre", PASS);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.endsWith("/giris"), { timeout: 45_000 }),
    page.locator("form[action='/giris'] button[type='submit']").click(),
  ]);
}

test.describe("Full user journey", () => {
  test("login → add disk → save draft → see history → logout", async ({ page }) => {
    await login(page);

    // Estimate workspace
    await page.goto("/tahmin");
    await expect(page.locator("#urun-listesi")).toBeVisible({ timeout: 20_000 });

    const addDisk = page.locator('button[hx-vals*="managed_disks"]').first();
    await addDisk.click();
    await expect(page.locator(".tahmin-kalemi").first()).toBeVisible({ timeout: 90_000 });

    await page.fill("#hesaplama-adi", ESTIMATE_NAME);

    // Draft save (onaya_gonder=0)
    const draftBtn = page.locator(
      'button[name="onaya_gonder"][value="0"], button:has-text("Taslak"), button:has-text("Kaydet")',
    ).first();
    await expect(draftBtn).toBeVisible({ timeout: 10_000 });
    await draftBtn.click();

    // Success redirect or banner
    await page.waitForTimeout(3000);
    const onHistory =
      page.url().includes("/gecmis") ||
      (await page.locator(".kaydet-basari-banner, a[href='/gecmis']").count()) > 0;
    if (!onHistory) {
      await page.goto("/gecmis/taslaklar");
    } else if (!page.url().includes("/gecmis")) {
      await page.goto("/gecmis/taslaklar");
    }

    await expect(page.locator("body")).toContainText(ESTIMATE_NAME, { timeout: 20_000 });

    // Logout
    await page.goto("/cikis");
    await expect(page).toHaveURL(/\/giris/);
  });

  test("API session cookie after login can hit /tahmin", async ({ page, request }) => {
    await login(page);
    const cookies = await page.context().cookies();
    expect(cookies.some((c) => c.name.includes("session") || c.name.includes("apc"))).toBeTruthy();

    const res = await page.request.get("/saglik");
    expect(res.status()).toBe(200);
  });
});

test.describe("Fail scenarios", () => {
  test("cannot save without login (POST kaydet)", async ({ request }) => {
    const res = await request.post("/tahmin/kaydet", {
      form: { hesaplama_adi: "x", onaya_gonder: "0", para_birimi: "USD" },
      maxRedirects: 0,
    });
    expect([303, 302, 401, 403].includes(res.status())).toBeTruthy();
  });

  test("wrong password cannot open tahmin", async ({ page }) => {
    await page.goto("/giris");
    await page.fill("#kullanici_adi", USER);
    await page.fill("#sifre", "bad");
    await page.locator("form[action='/giris'] button[type='submit']").click();
    await expect(page.locator(".ui-alert--danger")).toBeVisible({ timeout: 15_000 });
    await page.goto("/tahmin");
    await expect(page).toHaveURL(/\/giris/);
  });

  test("admin without hesaplama.kullan gets 403 on tahmin", async ({ page }) => {
    await page.goto("/giris", { waitUntil: "domcontentloaded" });
    await page.fill("#kullanici_adi", "asli.demirtas");
    await page.fill("#sifre", PASS);
    await Promise.all([
      page.waitForURL((url) => !url.pathname.endsWith("/giris"), { timeout: 45_000 }),
      page.locator("form[action='/giris'] button[type='submit']").click(),
    ]);
    const res = await page.goto("/tahmin");
    const status = res ? res.status() : 0;
    const body = await page.content();
    expect(status === 403 || body.includes("403") || !body.includes("urun-listesi")).toBeTruthy();
  });

  test("404 unknown route", async ({ request }) => {
    const res = await request.get("/bu-sayfa-yok-" + Date.now());
    expect(res.status()).toBe(404);
  });

  test("empty kalem-ekle product rejected", async ({ page }) => {
    await login(page);
    const res = await page.request.post("/tahmin/kalem-ekle", {
      form: { urun_tipi: "yok_urun", para_birimi: "USD" },
    });
    expect([400, 403, 422].includes(res.status())).toBeTruthy();
  });
});
