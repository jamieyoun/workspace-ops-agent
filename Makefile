.PHONY: dev dev-backend dev-frontend seed test install demo docker-up docker-down

install:
	@cd backend && (command -v uv >/dev/null && uv sync || (python3 -m venv .venv && .venv/bin/pip install ".[dev]"))
	cd frontend && npm install
	npm install

dev:
	npm run dev

dev-backend:
	@cd backend && (command -v uv >/dev/null && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 || .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000)

dev-frontend:
	cd frontend && npm run dev

seed:
	@cd backend && (command -v uv >/dev/null && uv run python scripts/seed.py || .venv/bin/python scripts/seed.py)

test:
	@cd backend && (command -v uv >/dev/null && uv run pytest -v || .venv/bin/python -m pytest -v)

demo:
	@API_URL=http://localhost:8000 bash scripts/demo.sh

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
