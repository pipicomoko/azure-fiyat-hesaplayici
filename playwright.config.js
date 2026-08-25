// @ts-check
const { defineConfig, devices } = require("@playwright/test");
require("dotenv").config();

const BASE_URL = process.env.BASE_URL || "http://127.0.0.1:8000";

module.exports = defineConfig({
  testDir: ".",
  testMatch: ["test.spec.js", "test.integration.js"],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    {
      name: "Mobile Safari",
      use: { ...devices["iPhone 12"] },
      testMatch: /test\.spec\.js/,
    },
  ],
});
