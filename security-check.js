#!/usr/bin/env node
/**
 * Basic pre-launch security checks (no app code mutation).
 */
const fs = require("fs");
const path = require("path");
const http = require("http");

const ROOT = path.resolve(__dirname);
const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const findings = [];

function add(level, name, file, description) {
  findings.push({ level, name, file, description });
  const tag = level === "ERROR" ? "ERROR FOUND" : level;
  console.log(`${tag}: ${name} - ${file} - ${description}`);
}

const SECRET_PATTERNS = [
  { name: "AWS_KEY", re: /AKIA[0-9A-Z]{16}/ },
  { name: "GENERIC_API_KEY", re: /(?:api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,}['\"]/i },
  { name: "PRIVATE_KEY", re: /BEGIN (RSA |OPENSSH )?PRIVATE KEY/ },
  { name: "GITHUB_TOKEN", re: /ghp_[A-Za-z0-9]{36}/ },
];

const SKIP_DIRS = new Set([
  "node_modules",
  ".git",
  ".venv",
  "venv",
  "playwright-report",
  "test-results",
  "__pycache__",
  ".pytest_cache",
  "vendor",
]);

function walk(dir, out = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(ent.name)) continue;
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(p, out);
    else if (/\.(py|js|ts|html|env|yml|yaml|json|md|sh)$/i.test(ent.name) && !ent.name.endsWith(".example")) {
      out.push(p);
    }
  }
  return out;
}

function scanSecrets() {
  const files = walk(ROOT);
  for (const file of files) {
    if (file.endsWith(".env") || file.includes("ad-ca.pem")) {
      add("WARN", "LOCAL_SECRET_FILE", file, "Local secret/cert file present (should not be committed)");
      continue;
    }
    let text;
    try {
      text = fs.readFileSync(file, "utf8");
    } catch {
      continue;
    }
    for (const { name, re } of SECRET_PATTERNS) {
      if (re.test(text)) {
        add("ERROR", name, file, "Possible exposed secret pattern matched");
      }
    }
  }
}

function scanConsoleSensitive() {
  const jsFiles = walk(ROOT).filter(
    (f) =>
      f.endsWith(".js") &&
      !f.includes("node_modules") &&
      !f.includes(`${path.sep}vendor${path.sep}`) &&
      !f.endsWith(".min.js"),
  );
  for (const file of jsFiles) {
    const text = fs.readFileSync(file, "utf8");
    const lines = text.split("\n");
    lines.forEach((line, i) => {
      if (/console\.(log|debug|info)\(.*(?:password|sifre|token|secret|apiKey)/i.test(line)) {
        add("ERROR", "SENSITIVE_CONSOLE_LOG", `${file}:${i + 1}`, line.trim().slice(0, 120));
      }
    });
  }
}

function scanXssBasics() {
  const templates = walk(path.join(ROOT, "app/templates")).filter((f) => f.endsWith(".html"));
  for (const file of templates) {
    const text = fs.readFileSync(file, "utf8");
    if (/\|safe\b/.test(text) && /request\.|kullanici|form/.test(text)) {
      add("WARN", "JINJA_SAFE_FILTER", file, "Template uses |safe near user/request data — review XSS");
    }
    if (/innerHTML\s*=/.test(text)) {
      add("WARN", "INNER_HTML", file, "innerHTML assignment in template/script");
    }
  }
  const appJs = path.join(ROOT, "app/static/app.js");
  if (fs.existsSync(appJs)) {
    const text = fs.readFileSync(appJs, "utf8");
    if (text.includes("innerHTML")) {
      add("WARN", "INNER_HTML", "app/static/app.js", "innerHTML usage — verify sanitization");
    }
  }
}

function checkHttpHeaders() {
  return new Promise((resolve) => {
    const url = new URL(BASE);
    const req = http.request(
      {
        hostname: url.hostname,
        port: url.port || 80,
        path: "/saglik",
        method: "GET",
        timeout: 5000,
      },
      (res) => {
        const h = res.headers;
        if (url.protocol === "http:" && BASE.includes("localhost")) {
          add("INFO", "HTTP_LOCAL", BASE, "Local HTTP expected in development");
        }
        if (!h["x-content-type-options"]) {
          add("WARN", "MISSING_X_CONTENT_TYPE_OPTIONS", BASE, "Header X-Content-Type-Options not set");
        }
        if (!h["x-frame-options"] && !h["content-security-policy"]) {
          add("WARN", "MISSING_CLICKJACKING_HEADERS", BASE, "No X-Frame-Options / CSP observed");
        }
        if (!h["strict-transport-security"] && !BASE.includes("localhost") && !BASE.includes("127.0.0.1")) {
          add("WARN", "MISSING_HSTS", BASE, "HSTS missing on non-local URL");
        }
        resolve();
      },
    );
    req.on("error", (err) => {
      add("ERROR", "HEALTH_UNREACHABLE", BASE, err.message);
      resolve();
    });
    req.on("timeout", () => {
      add("ERROR", "HEALTH_TIMEOUT", BASE, "Timeout contacting /saglik");
      req.destroy();
      resolve();
    });
    req.end();
  });
}

function checkGitignore() {
  const gi = path.join(ROOT, ".gitignore");
  if (!fs.existsSync(gi)) {
    add("ERROR", "NO_GITIGNORE", ".gitignore", "Missing .gitignore");
    return;
  }
  const text = fs.readFileSync(gi, "utf8");
  for (const must of [".env", "node_modules", "config/ad-ca.pem"]) {
    if (!text.includes(must)) {
      add("WARN", "GITIGNORE_GAP", ".gitignore", `Consider ignoring ${must}`);
    }
  }
}

(async () => {
  console.log("=== security-check.js ===");
  scanSecrets();
  scanConsoleSensitive();
  scanXssBasics();
  checkGitignore();
  await checkHttpHeaders();

  const errors = findings.filter((f) => f.level === "ERROR");
  const warns = findings.filter((f) => f.level === "WARN");
  console.log(`\nSummary: ${errors.length} ERROR, ${warns.length} WARN, ${findings.length} total`);
  process.exit(errors.length > 0 ? 1 : 0);
})();
