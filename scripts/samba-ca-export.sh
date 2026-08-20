#!/bin/bash
# Samba konteynerindeki CA'yi config/ad-ca.pem olarak disari aktarir.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/config/ad-ca.pem"
SRC_CANDIDATES=(
  /var/lib/samba/private/tls/ca.pem
  /var/lib/samba/private/tls/cert.pem
)

cd "$ROOT"
cid="$(docker compose ps -q samba 2>/dev/null || true)"
if [[ -z "$cid" ]]; then
  echo "samba konteyneri calismiyor; once: docker compose up -d samba" >&2
  exit 1
fi

for src in "${SRC_CANDIDATES[@]}"; do
  if docker compose exec -T samba test -f "$src" 2>/dev/null; then
    docker compose exec -T samba cat "$src" >"$OUT"
    echo "Yazildi: $OUT (kaynak: $src)"
    openssl x509 -in "$OUT" -noout -subject -issuer -dates 2>/dev/null || true
    exit 0
  fi
done

echo "CA dosyasi konteynerde bulunamadi." >&2
exit 1
