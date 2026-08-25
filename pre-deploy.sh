#!/usr/bin/env bash
# Pre-deploy checklist for Azure Fiyat Hesaplayici
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
export BASE_URL

PASS=0
FAIL=0
SKIP=0
REPORT=()

log() { echo -e "$*"; }
ok() { PASS=$((PASS + 1)); REPORT+=("PASS: $1"); log "✅ PASS: $1"; }
bad() { FAIL=$((FAIL + 1)); REPORT+=("FAIL: $1 — $2"); log "❌ FAIL: $1 — $2"; }
skip() { SKIP=$((SKIP + 1)); REPORT+=("SKIP: $1 — $2"); log "⏭  SKIP: $1 — $2"; }

log "=== PRE-DEPLOY START ($(date -u +%Y-%m-%dT%H:%M:%SZ)) ==="
log "BASE_URL=$BASE_URL"
log ""

# 0) App reachable
if curl -sf "$BASE_URL/saglik" >/dev/null; then
  ok "App health /saglik"
else
  bad "App health /saglik" "Cannot reach $BASE_URL/saglik — start docker compose first"
fi

# 1) Build / Python tests (existing suite)
log "\n--- Build / pytest ---"
if python3 -m pytest -q; then
  ok "pytest unit/integration suite"
else
  bad "pytest" "See pytest output above"
fi

# 2) npm install if needed
log "\n--- npm dependencies ---"
if [[ ! -d node_modules ]]; then
  if npm install; then
    ok "npm install"
  else
    bad "npm install" "dependency install failed"
  fi
else
  ok "npm install (node_modules present)"
fi

# 3) Jest
log "\n--- Jest unit ---"
if npm run test:unit; then
  ok "Jest unit tests"
else
  bad "Jest unit tests" "npm run test:unit failed"
fi

# 4) Playwright browsers
log "\n--- Playwright install browsers ---"
if npx playwright install chromium webkit >/tmp/pw-install.log 2>&1; then
  ok "Playwright browsers"
else
  skip "Playwright browsers" "install failed — see /tmp/pw-install.log"
fi

# 5) Playwright E2E
log "\n--- Playwright E2E ---"
if npm run test:e2e -- --project=chromium; then
  ok "Playwright E2E (chromium)"
else
  bad "Playwright E2E" "npm run test:e2e failed"
fi

# 6) Playwright integration
log "\n--- Playwright integration ---"
if npm run test:integration -- --project=chromium; then
  ok "Playwright integration"
else
  bad "Playwright integration" "npm run test:integration failed"
fi

# 7) Lighthouse
log "\n--- Lighthouse ---"
if npm run lighthouse; then
  ok "Lighthouse thresholds"
else
  bad "Lighthouse" "thresholds not met or chrome missing"
fi

# 8) Security
log "\n--- Security check ---"
if node security-check.js; then
  ok "security-check.js (no ERROR)"
else
  bad "security-check.js" "ERROR-level findings present"
fi

# Summary
log "\n=== PRE-LAUNCH TEST REPORT ==="
log "Base URL: $BASE_URL"
log "Passed: $PASS | Failed: $FAIL | Skipped: $SKIP"
log "---"
for line in "${REPORT[@]}"; do
  log "$line"
done
log "---"
if [[ "$FAIL" -eq 0 ]]; then
  log "RESULT: READY FOR MANUAL QA / DEPLOY CANDIDATE"
  exit 0
else
  log "RESULT: NOT READY — fix failures above"
  exit 1
fi
