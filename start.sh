#!/bin/bash
set -e
cd /home/nvidia/nervus

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

# Phase 2: Core services (llama, whisper, arbor)
log "Starting core services..."
docker compose up -d llama-cpp whisper arbor-core

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
  app-status-sense app-workflow-viewer

# Wait for apps to register (check count reaches expected)
for i in $(seq 1 20); do
  count=$(curl -sf http://localhost:8090/apps/list 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["count"])' 2>/dev/null || echo 0)
  [ "$count" -ge 14 ] && break
  sleep 3
done
log "Apps registered: $count/14"

# Phase 4: Caddy (frontend)
log "Starting Caddy..."
docker compose up -d caddy
log "All services started"
