# Nervus — Developer Makefile (单进程模式)

.PHONY: help run test test-api reload-flows

help:
	@echo ""
	@echo "  Nervus — Available commands"
	@echo ""
	@echo "  Run"
	@echo "    make run             Start Arbor Core (python core/arbor/main.py)"
	@echo ""
	@echo "  Testing"
	@echo "    make test            Run all tests"
	@echo "    make test-api        Test all Arbor APIs"
	@echo ""
	@echo "  Hot-reload"
	@echo "    make reload-flows    Hot-reload Flow config"
	@echo ""

# ── Run ──────────────────────────────────────────────────────────────────

run:
	python core/arbor/main.py

# ── Hot-reload ─────────────────────────────────────────────────────────────

reload-flows:
	curl -s -X POST http://localhost:8090/flows/reload | python3 -m json.tool

# ── Testing ────────────────────────────────────────────────────────────────

test:
	@cd tests && bash run_tests.sh

test-api:
	@echo "Testing Arbor API endpoints..."
	@curl -sf http://localhost:8090/health | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  health:", d["status"])'
	@curl -sf http://localhost:8090/status | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  status: apps="+str(d["apps_registered"])+" flows="+str(d["flows_loaded"]))'
	@curl -sf http://localhost:8090/models/status | python3 -c 'import sys,json; d=json.load(sys.stdin); online=[m["id"] for m in d["models"]]; print("  models:", len(online))'
	@echo "  All endpoints OK"
