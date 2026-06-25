# Convenience shortcuts for the split backend/ + frontend/ layout.
# Run `make help` to list targets.

PY ?= python3

.PHONY: help install install-dev backend frontend test e2e clean

help:
	@echo "Targets:"
	@echo "  make install      Install backend runtime deps"
	@echo "  make install-dev  Install backend test deps"
	@echo "  make backend      Run the Flask API on http://localhost:5001"
	@echo "  make frontend     Run the Vite dev server on http://localhost:5173"
	@echo "  make test         Run backend unit + API + flow tests"
	@echo "  make e2e          Run browser end-to-end tests"
	@echo "  make clean        Remove caches and the local SQLite db"

install:
	cd backend && $(PY) -m pip install -r requirements.txt

install-dev:
	cd backend && $(PY) -m pip install -r requirements-dev.txt

backend:
	cd backend && $(PY) app.py

frontend:
	cd frontend && npm run dev

test:
	cd backend && $(PY) -m pytest

e2e:
	cd backend && $(PY) -m pytest -m e2e

clean:
	rm -rf backend/__pycache__ backend/.pytest_cache backend/tests/__pycache__
	rm -f backend/data.db
