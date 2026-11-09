.PHONY: install api web test build

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
	cd frontend && npm install

api:
	cd backend && .venv/bin/uvicorn atlas.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build
