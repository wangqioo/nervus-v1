# Nervus v1 — Developer Makefile
# Usage: make <target>

.PHONY: help up down restart logs status test test-api test-model reload-arbor reload-caddy reload-flows sync-orin

ORIN ?= nvidia@150.158.146.192
ORIN_PORT ?= 6000
SSH = ssh -p $(ORIN_PORT) -o StrictHostKeyChecking=no $(ORIN)
SCP = scp -P $(ORIN_PORT) -o StrictHostKeyChecking=no

help:
	@echo ""
	@echo "  Nervus v1 — Available commands"
	@echo ""
	@echo "  Stack"
	@echo "    make up              Start all services"
	@echo "    make down            Stop all services"
	@echo "    make restart         Restart all services"
	@echo "    make status          Show container status"
	@echo "    make logs svc=arbor  Tail logs for a service"
	@echo ""
	@echo "  Hot-reload (no rebuild)"
	@echo "    make reload-arbor    Restart Arbor to pick up code changes"
	@echo "    make reload-caddy    Reload Caddy config (zero-downtime)"
	@echo "    make reload-flows    Hot-reload Flow config"
	@echo ""
	@echo "  Testing"
	@echo "    make test            Run all local tests"
	@echo "    make test-api        Test all Arbor APIs (requires running stack)"
	@echo "    make test-model      Test local model inference"
	@echo ""
	@echo "  Deploy to Orin"
	@echo "    make sync-orin       Push code + restart Arbor on Orin"
	@echo "    make sync-frontend   Push frontend/index.html to Orin"
	@echo ""

# ── Stack ─────────────────────────────────────────────────────────────────────

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

status:
	docker compose ps

logs:
	docker compose logs -f --tail=50 $(svc)

# ── Hot-reload ────────────────────────────────────────────────────────────────

reload-arbor:
	docker compose restart arbor-core

reload-caddy:
	docker exec nervus-caddy caddy reload --config /etc/caddy/Caddyfile

reload-flows:
	curl -s -X POST http://localhost:8090/flows/reload | python3 -m json.tool

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	@cd tests && bash run_tests.sh

test-api:
	@echo "Testing Arbor API endpoints..."
	@curl -sf http://localhost:8090/health | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  health:", d["status"])'
	@curl -sf http://localhost:8090/status | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  status: apps="+str(d["apps_registered"])+" flows="+str(d["flows_loaded"]))'
	@curl -sf http://localhost:8090/models/status | python3 -c 'import sys,json; d=json.load(sys.stdin); online=[m["id"] for m in d["models"] if m["status"]=="online"]; print("  models online:", online)'
	@curl -sf 'http://localhost:8090/events/recent?limit=1' | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  events:", d["count"], "total")'
	@echo "  All endpoints OK"

test-model:
	@echo "Testing local model (Qwen3.5)..."
	@curl -sf -m 90 -X POST http://localhost:8090/models/qwen3.5/test \
		-H 'Content-Type: application/json' \
		-d '{"prompt":"用一句话打个招呼"}' | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  response:", d.get("content","")[:80]) if not d.get("error") else print("  ERROR:", d["error"])'

# ── Deploy to Orin ────────────────────────────────────────────────────────────

sync-orin:
	@echo "Syncing code to Orin..."
	$(SSH) "cd ~/nervus && git pull origin main 2>&1 | tail -3"
	@echo "Restarting Arbor on Orin..."
	$(SSH) "cd ~/nervus && docker compose restart arbor-core 2>&1 | tail -2"
	@echo "Done."

sync-frontend:
	@echo "Pushing frontend/index.html to Orin..."
	$(SCP) frontend/index.html $(ORIN):~/nervus/frontend/index.html
	@echo "Done (no restart needed)."
