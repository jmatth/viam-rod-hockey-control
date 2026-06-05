# Makefile for the rod-hockey-robot annotation/visualization server.
#
#   make start-annotation-server    # launch in the background
#   make stop-annotation-server     # stop it
#   make restart-annotation-server  # stop then start
#   make annotation-server-status   # is it running?
#
# Pass extra flags via ARGS, e.g.:
#   make start-annotation-server ARGS="--scale 4 --port 8800"

PY  := .venv/bin/python
PID := .annotation-server.pid
LOG := /tmp/annotation-server.log
URL := http://127.0.0.1:8765/
ARGS ?=

.PHONY: start-annotation-server stop-annotation-server restart-annotation-server annotation-server-status

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
