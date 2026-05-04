# Nervus — Developer Makefile

.PHONY: help up down restart logs status test test-api test-apps reload-arbor reload-flows new-app

H618 ?= root@nervus.local
SSH  = ssh -o StrictHostKeyChecking=no $(H618)
SCP  = scp -o StrictHostKeyChecking=no

help:
	@echo ""
	@echo "  Nervus — Available commands"
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
	@echo "    make reload-flows    Hot-reload Flow config"
	@echo ""
	@echo "  Testing"
	@echo "    make test            Run all tests"
	@echo "    make test-api        Test all Arbor APIs"
	@echo "    make test-apps       Ping /health on all app containers"
	@echo ""
	@echo "  Scaffolding"
	@echo "    make new-app name=habit-tracker port=8017"
	@echo ""
	@echo "  Deploy to H618 device"
	@echo "    make sync-h618       Push code + restart Arbor on device"
	@echo ""

# ── Stack ──────────────────────────────────────────────────────────────────

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

# ── Hot-reload ─────────────────────────────────────────────────────────────

reload-arbor:
	docker compose restart arbor-core

reload-flows:
	curl -s -X POST http://localhost:8090/flows/reload | python3 -m json.tool

# ── Testing ────────────────────────────────────────────────────────────────

test:
	@cd tests && bash run_tests.sh

test-api:
	@echo "Testing Arbor API endpoints..."
	@curl -sf http://localhost:8090/health | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  health:", d["status"])'
	@curl -sf http://localhost:8090/status | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  status: apps="+str(d["apps_registered"])+" flows="+str(d["flows_loaded"]))'
	@curl -sf http://localhost:8090/models/status | python3 -c 'import sys,json; d=json.load(sys.stdin); online=[m["id"] for m in d["models"] if m["status"]=="online"]; print("  models online:", online)'
	@echo "  All endpoints OK"

test-apps:
	@echo "Testing all app /health endpoints..."
	@bash tests/test_apps.sh

# ── Scaffolding ────────────────────────────────────────────────────────────

new-app:
	@[ -n "$(name)" ] || (echo "Usage: make new-app name=<app-id> port=<port>"; exit 1)
	@[ -n "$(port)" ] || (echo "Usage: make new-app name=<app-id> port=<port>"; exit 1)
	@bash scripts/new-app.sh "$(name)" "$(port)"

# ── Deploy to H618 device ──────────────────────────────────────────────────

sync-h618:
	@echo "Syncing code to H618 device ($(H618))..."
	$(SSH) "cd ~/nervus && git pull origin main 2>&1 | tail -3"
	@echo "Restarting Arbor on device..."
	$(SSH) "cd ~/nervus && docker compose restart arbor-core 2>&1 | tail -2"
	@echo "Done."
