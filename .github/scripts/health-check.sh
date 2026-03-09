#!/bin/bash
# Health check with retries
# Usage: ./health-check.sh <url> [max-attempts] [sleep-seconds]
set -euo pipefail

URL="${1:?URL required}"
MAX_ATTEMPTS="${2:-5}"
SLEEP_SECONDS="${3:-10}"

echo "Health checking: $URL"

for i in $(seq 1 "$MAX_ATTEMPTS"); do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    echo "Health check passed (attempt $i)"
    exit 0
  fi
  echo "Attempt $i/$MAX_ATTEMPTS: HTTP $HTTP_CODE, retrying in ${SLEEP_SECONDS}s..."
  sleep "$SLEEP_SECONDS"
done

echo "Health check failed after $MAX_ATTEMPTS attempts"
exit 1
