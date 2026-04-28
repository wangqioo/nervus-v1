#!/bin/bash
# Ping /health on all 16 app containers
# Usage: bash tests/test_apps.sh [BASE_URL]
# BASE_URL defaults to http://localhost:8900 (through Caddy)

BASE="${1:-http://localhost:8900}"
PASS=0; FAIL=0

declare -A APPS=(
  [calorie-tracker]=8001
  [meeting-notes]=8002
  [knowledge-base]=8003
  [life-memory]=8004
  [sense]=8005
  [photo-scanner]=8006
  [personal-notes]=8007
  [pdf-extractor]=8008
  [video-transcriber]=8009
  [rss-reader]=8010
  [calendar]=8011
  [reminder]=8012
  [status-sense]=8013
  [workflow-viewer]=8014
  [file-manager]=8015
  [model-manager]=8016
)

echo ""
echo "App health checks (via Caddy at $BASE)"
echo "────────────────────────────────────────────"

for app in "${!APPS[@]}"; do
  port="${APPS[$app]}"
  url="$BASE/api/$app/health"
  status=$(curl -sf -m 5 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
  if [ "$status" = "200" ]; then
    echo "  [PASS] $app (:$port)"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $app (:$port) → HTTP $status"
    FAIL=$((FAIL + 1))
  fi
done

echo "────────────────────────────────────────────"
echo "  $PASS passed / $FAIL failed"
echo ""

[ $FAIL -eq 0 ] && exit 0 || exit 1
