#!/bin/bash
set -e
cd "$(dirname "$0")"

log() { echo "[nervus] $(date '+%H:%M:%S') $*"; }

# Phase 1: Infrastructure
log "Starting infrastructure..."
docker compose up -d postgres redis nats

# Wait for postgres
for i in $(seq 1 30); do
  docker exec nervus-postgres pg_isready -U nervus -d nervus -q 2>/dev/null && break
  sleep 2
done
log "Postgres ready"

# Phase 2: Arbor Core
log "Starting Arbor Core..."
docker compose up -d arbor-core

# Wait for arbor
for i in $(seq 1 30); do
  curl -sf http://localhost:8090/health > /dev/null 2>&1 && break
  sleep 2
done
log "Arbor ready"

# Phase 3: Apps
log "Starting apps..."
docker compose up -d \
  app-calorie-tracker app-meeting-notes app-knowledge-base app-life-memory \
  app-sense app-photo-scanner app-personal-notes app-pdf-extractor \
  app-video-transcriber app-rss-reader app-calendar app-reminder \
  app-status-sense app-workflow-viewer app-file-manager app-model-manager

# Wait for apps to register
for i in $(seq 1 20); do
  count=$(curl -sf http://localhost:8090/apps 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("count", len(d.get("apps",[]))))' 2>/dev/null || echo 0)
  [ "$count" -ge 14 ] && break
  sleep 3
done
log "Apps registered: $count"
log "All services started. Run: cd nervus-cli && python app.py"
