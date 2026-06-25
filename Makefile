# Makefile for rod-hockey-robot.
#
#   make setup                      # install uv (if needed) + all deps into .venv (Linux/macOS)
#   make start-annotation-server    # launch the annotation/visualization server in the background
#   make stop-annotation-server     # stop it
#   make restart-annotation-server  # stop then start
#   make annotation-server-status   # is it running?
#
# Pass extra server flags via ARGS, e.g.:
#   make start-annotation-server ARGS="--scale 4 --port 8800"

PY  := .venv/bin/python
PID := .annotation-server.pid
LOG := /tmp/annotation-server.log
URL := http://127.0.0.1:8765/
ARGS ?=

.PHONY: help setup check-puck start-annotation-server stop-annotation-server restart-annotation-server annotation-server-status

help:
	@echo "Targets:"
	@echo "  make setup                      install uv (if needed) + dependencies into .venv"
	@echo "  make check-puck                 detect the puck and print its player/zone (read-only)"
	@echo "  make start-annotation-server    start the annotation server ($(URL))"
	@echo "  make stop-annotation-server     stop it"
	@echo "  make restart-annotation-server  restart it"
	@echo "  make annotation-server-status   show whether it is running"

# Install uv (Linux/macOS) if it isn't already, then sync the project: uv
# downloads the right Python (3.13) and every dependency into .venv.
setup:
	@command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
	@export PATH="$$HOME/.local/bin:$$HOME/.cargo/bin:$$PATH"; uv sync
	@echo "Setup complete — dependencies installed into .venv (Python managed by uv)."

# Read-only: detect the puck and report which player/zone it's in. Moves nothing.
check-puck:
	@$(PY) tools/check_puck.py

start-annotation-server:
	@if [ -f $(PID) ] && kill -0 $$(cat $(PID)) 2>/dev/null; then \
		echo "Annotation server already running (PID $$(cat $(PID))) -> $(URL)"; \
	else \
		nohup $(PY) tools/annotate_zones.py $(ARGS) > $(LOG) 2>&1 & echo $$! > $(PID); \
		echo "Annotation server started (PID $$(cat $(PID))) -> $(URL)"; \
		echo "Logs: $(LOG)"; \
	fi

stop-annotation-server:
	@if [ -f $(PID) ] && kill $$(cat $(PID)) 2>/dev/null; then \
		echo "Annotation server stopped (PID $$(cat $(PID)))."; \
	else \
		pkill -f "tools/annotate_zones.py" 2>/dev/null && echo "Annotation server stopped." || echo "No annotation server running."; \
	fi
	@rm -f $(PID)

restart-annotation-server: stop-annotation-server start-annotation-server

annotation-server-status:
	@if [ -f $(PID) ] && kill -0 $$(cat $(PID)) 2>/dev/null; then \
		echo "running (PID $$(cat $(PID))) -> $(URL)"; \
	else \
		echo "not running"; \
	fi
