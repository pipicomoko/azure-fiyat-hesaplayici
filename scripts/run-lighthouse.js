#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const lighthouse = require("lighthouse");
const chromeLauncher = require("chrome-launcher");

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const URL = process.env.LIGHTHOUSE_URL || `${BASE}/giris`;
const OUT = path.join(__dirname, "..", "lighthouse-report.json");

const THRESHOLDS = {
  performance: 85,
  accessibility: 90,
  "best-practices": 90,
  seo: 85,
};

const runLighthouse = typeof lighthouse === "function" ? lighthouse : lighthouse.default;

(async () => {
  let chrome;
  try {
    chrome = await chromeLauncher.launch({ chromeFlags: ["--headless", "--no-sandbox"] });
    const result = await runLighthouse(URL, {
      port: chrome.port,
      output: "json",
      onlyCategories: ["performance", "accessibility", "best-practices", "seo"],
    });
    const report = typeof result.report === "string" ? result.report : JSON.stringify(result.lhr, null, 2);
    fs.writeFileSync(OUT, report);
    const cats = result.lhr.categories;
    let failed = 0;
    console.log("=== Lighthouse ===");
    console.log("URL:", URL);
    for (const [key, min] of Object.entries(THRESHOLDS)) {
      const score = Math.round((cats[key]?.score || 0) * 100);
      const ok = score >= min;
      console.log(`${ok ? "OK" : "FAIL"} ${key}: ${score} (threshold ${min})`);
      if (!ok) {
        failed += 1;
        console.log(
          `ERROR FOUND: LIGHTHOUSE_${key.toUpperCase()} - lighthouse-report.json - score ${score} < ${min}`,
        );
      }
    }
    process.exit(failed ? 1 : 0);
  } catch (err) {
    console.log(`ERROR FOUND: LIGHTHOUSE_RUN - scripts/run-lighthouse.js - ${err.message}`);
    process.exit(1);
  } finally {
    if (chrome) await chrome.kill();
  }
})();
