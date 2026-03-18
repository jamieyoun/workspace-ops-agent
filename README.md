# Workspace Ops Agent

Monorepo with FastAPI backend and Next.js frontend for a Notion-like workspace with analysis, recommendations, and guardrails.

## Why This Exists

Workspace Ops Agent helps teams keep their knowledge bases healthy. Notion-like workspaces grow organically and often accumulate stale pages, missing owners, oversized documents, and duplicate content. This tool analyzes workspace structure and content, surfaces issues, and suggests actionable recommendations—from archiving stale pages to splitting oversized ones—with optional AI-powered explanations and one-click apply.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────────────────────────────────────┐
│   Next.js       │     │   FastAPI Backend                                 │
│   Frontend      │────▶│   ├── Analysis pipeline (metrics, heuristics)     │
│   (Dashboard,   │     │   ├── Ops Agent (OpenAI or heuristic fallback)   │
│   Page detail)  │     │   ├── Apply handlers (summarize, archive, etc.)  │
└─────────────────┘     │   └── SQLite + in-memory cache (5 min TTL)       │
                         └──────────────────────────────────────────────────┘
```

- **Backend**: FastAPI with SQLAlchemy (SQLite). Analysis pipeline computes page metrics (word count, blocks, embeds), detects issues via heuristics (stale pages, missing owners, huge pages, duplicates), and scores workspace health. The Ops Agent turns issues into recommendations; apply handlers execute changes.
- **Frontend**: Next.js App Router, Tailwind, react-markdown. Dashboard shows health score, issues, recommendations (Explain/Approve/Apply/Dismiss), and audit log.
- **Observability**: Structured request logging (request id, route, latency), rate limiting on generate (5 req/min per workspace), analysis result caching (5 min TTL), and `/metrics` endpoint for counts and last-run timestamps.

## Setup

1. **Prerequisites**: Python 3.9+, Node.js 18+, [uv](https://docs.astral.sh/uv/) (or pip), npm

   Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`

2. **Install dependencies**:
   ```bash
   make install
   ```

3. **Copy environment file**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add `OPENAI_API_KEY` if needed.

4. **Seed demo data** (optional):
   ```bash
   make seed
   ```

## Development

```bash
make dev
```

Starts both services:
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:3000 (or 3001 if 3000 is in use)

## Commands

| Command       | Description                                      |
|---------------|--------------------------------------------------|
| `make dev`    | Start backend + frontend                         |
| `make seed`   | Seed demo workspace data                         |
| `make test`   | Run backend pytest tests                         |
| `make demo`   | Docker: build, start, seed, analyze, generate    |
| `make docker-up`   | Start containers (with hot reload)               |
| `make docker-down` | Stop containers                                 |

## Docker

```bash
docker compose up --build
```

- **Backend**: Uvicorn with `--reload`, volume mounts for `app/` and `scripts/` (hot reload).
- **Frontend**: Next.js dev server (`next dev`), volume mounts for source (hot reload). Uses `Dockerfile.dev`. For production builds, use `Dockerfile` and `next start`.
- **Database**: SQLite in `backend_data` volume.

## Demo (one command)

```bash
make demo
```

Builds images, starts backend + frontend, waits for backend, seeds data, runs analysis, generates recommendations. Open http://localhost:3000 when done.

## Project Structure

```
├── backend/           # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── routes/    # API routes (health, metrics, workspaces, pages, recommendations)
│   │   ├── agents/    # Ops Agent, apply handlers, prompts
│   │   ├── analysis/  # Pipeline, heuristics, scoring
│   │   ├── observability.py   # Request logging middleware
│   │   ├── rate_limit.py     # In-memory rate limiter
│   │   ├── analysis_cache.py # Per-workspace cache (5 min TTL)
│   │   ├── metrics_store.py  # Request counts, latency, last-run
│   │   ├── db.py, models.py, schemas.py
│   └── scripts/seed.py
├── frontend/          # Next.js App Router + Tailwind
│   └── src/
│       ├── app/      # Dashboard, page detail
│       ├── components/ # DiffPreview, etc.
│       └── lib/      # API client
└── docker-compose.yml
```

## Testing

- **Unit/integration**: `make test` runs pytest (analysis, guardrails, heuristics, scoring).
- **E2E**: `tests/test_e2e.py` seeds data, runs analysis, generates recommendations, approves and applies one, verifies audit log entries.

## Deterministic Seed

The seed script uses `random.seed(42)` so output is consistent across runs for screenshots and demos.

## Enterprise Considerations

If this were productionized:

- **Document-level access control** would be enforced pre-retrieval
- **Retrieval logs** would support auditability
- **Chunk metadata** enables future analytics (coverage gaps, stale docs)
- **System** supports gradual rollout across teams

## Future Work

- **Notion/Confluence sync**: Connect to real Notion or Confluence APIs instead of seeded data.
- **Guardrails**: Prevent applying recommendations that conflict with org policies (e.g. block archiving certain pages).
- **Distributed rate limiting**: Replace in-memory limiter with Redis for multi-instance deployments.
- **Persistent metrics**: Store `/metrics` data in DB or export to Prometheus for long-term observability.
- **Batch apply**: Apply multiple recommendations at once with rollback support.
- **Webhooks**: Notify external systems when recommendations are applied or issues are detected.
