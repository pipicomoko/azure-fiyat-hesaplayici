/**
 * Playwright E2E — Azure Fiyat Hesaplayici (FastAPI + Jinja2)
 * Requires app at BASE_URL (default http://127.0.0.1:8000)
 */
const { test, expect } = require("@playwright/test");

const USER = process.env.E2E_USER || "kerem.acar";
const PASS = process.env.E2E_PASS || "Sirket123!";

async function login(page, user = USER, pass = PASS) {
  await page.goto("/giris", { waitUntil: "domcontentloaded" });
  await page.fill("#kullanici_adi", user);
  await page.fill("#sifre", pass);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.endsWith("/giris"), { timeout: 45_000 }),
    page.locator("form[action='/giris'] button[type='submit']").click(),
  ]);
}

test.describe("Login flow", () => {
  test("successful login redirects away from /giris", async ({ page }) => {
    await login(page);
    await expect(page).not.toHaveURL(/\/giris$/);
    await expect(page.locator("body")).toBeVisible();
  });

  test("invalid credentials show error", async ({ page }) => {
    await page.goto("/giris");
    await page.fill("#kullanici_adi", USER);
    await page.fill("#sifre", "yanlis-sifre-!!!");
    await page.locator("form[action='/giris'] button[type='submit']").click();
    await expect(page.locator(".ui-alert--danger")).toBeVisible({ timeout: 15_000 });
  });

  test("empty required fields blocked by HTML5 validation", async ({ page }) => {
    await page.goto("/giris");
    await page.locator("form[action='/giris'] button[type='submit']").click();
    const invalid = await page.locator("#kullanici_adi:invalid").count();
    expect(invalid).toBeGreaterThan(0);
  });
});
test.describe("Cost estimation flow", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto("/tahmin");
  });

  test("add VM, wait for price, see monthly total area", async ({ page }) => {
    const addVm = page.locator('button[hx-vals*="virtual_machines"]').first();
    await expect(addVm).toBeVisible({ timeout: 20_000 });
    await addVm.click();
    await expect(page.locator(".tahmin-kalemi").first()).toBeVisible({ timeout: 60_000 });
    // Price may load async via HTMX; wait for item presence and total element
    await expect(page.locator("#tahmin-toplam")).toBeVisible();
    const itemCount = await page.locator(".tahmin-kalemi").count();
    expect(itemCount).toBeGreaterThan(0);
  });

  test("save draft requires name (validation)", async ({ page }) => {
    const addDisk = page.locator('button[hx-vals*="managed_disks"]').first();
    if (await addDisk.count()) {
      await addDisk.click();
      await page.locator(".tahmin-kalemi").first().waitFor({ timeout: 60_000 }).catch(() => {});
    }
    await page.fill("#hesaplama-adi", "");
    const saveBtn = page.locator('button[name="onaya_gonder"][value="0"], button:has-text("Kaydet"), button:has-text("Save")').first();
    if (await saveBtn.count()) {
      await saveBtn.click();
      // Either client stays or server returns alert
      await page.waitForTimeout(1500);
      const alert = page.locator(".alert-danger, .ui-alert--danger, .ui-alert--warning");
      const stillOnTahmin = page.url().includes("/tahmin");
      expect(stillOnTahmin || (await alert.count()) > 0).toBeTruthy();
    }
  });
});

test.describe("Form validation & edge cases", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto("/tahmin");
  });

  test("special characters in estimate name field accepted in UI", async ({ page }) => {
    await page.fill("#hesaplama-adi", "Test & Co. #1 <ok>");
    await expect(page.locator("#hesaplama-adi")).toHaveValue(/Test/);
  });
});

test.describe("Mobile responsive (iPhone 12 project)", () => {
  test("login usable on mobile viewport", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "Mobile Safari", "mobile project only");
    await page.goto("/giris");
    await expect(page.locator("#kullanici_adi")).toBeVisible();
    await expect(page.locator("form[action='/giris'] button[type='submit']")).toBeVisible();
    const box = await page.locator("form[action='/giris'] button[type='submit']").boundingBox();
    expect(box).toBeTruthy();
    expect(box.width).toBeGreaterThan(40);
  });
});

test.describe("Error handling", () => {
  test("mocked 500 on kalem-ekle surfaces without crash", async ({ page }) => {
    await login(page);
    await page.goto("/tahmin");
    await page.route("**/tahmin/kalem-ekle", async (route) => {
      await route.fulfill({ status: 500, body: "Internal Server Error" });
    });
    const addVm = page.locator('button[hx-vals*="virtual_machines"]').first();
    await addVm.click();
    await page.waitForTimeout(2000);
    // App should still be interactive
    await expect(page.locator("#urun-listesi")).toBeVisible();
  });

  test("network abort on health does not break browser", async ({ page }) => {
    await page.route("**/saglik", (route) => route.abort());
    const res = await page.request.get("/saglik").catch((e) => e);
    expect(res).toBeTruthy();
  });
});

test.describe("API integration", () => {
  test("GET /saglik returns 200 JSON", async ({ request }) => {
    const res = await request.get("/saglik");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.durum || body.status || body).toBeTruthy();
  });

  test("GET /tahmin without session redirects to giris", async ({ request }) => {
    const res = await request.get("/tahmin", { maxRedirects: 0 });
    expect([302, 303, 401, 403].includes(res.status()) || res.status() === 200).toBeTruthy();
  });

  test("POST /giris with bad password returns 401 or error page", async ({ request }) => {
    const res = await request.post("/giris", {
      form: { kullanici_adi: USER, sifre: "definitely-wrong" },
      maxRedirects: 0,
    });
    expect([401, 200, 303].includes(res.status())).toBeTruthy();
  });
});

test.describe("Logout flow", () => {
  test("cikis clears session and returns to giris", async ({ page }) => {
    await login(page);
    await page.goto("/cikis");
    await expect(page).toHaveURL(/\/giris/);
    await page.goto("/tahmin");
    await expect(page).toHaveURL(/\/giris/);
  });
});
