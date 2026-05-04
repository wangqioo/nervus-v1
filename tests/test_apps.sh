#!/bin/bash
# Ping /health on all app containers (direct port)
PASS=0; FAIL=0

declare -A PORTS=(
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

for app in "${!PORTS[@]}"; do
  port="${PORTS[$app]}"
  url="http://localhost:${port}/health"
  if curl -sf --max-time 3 "$url" > /dev/null 2>&1; then
    echo "  ✓ $app (:$port)"
    ((PASS++))
  else
    echo "  ✗ $app (:$port) — FAIL"
    ((FAIL++))
  fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
