# Covora

Covora is an autonomous AI sales agent for B2B companies. You describe the customers you want in plain language, and Covora's agents — powered by NVIDIA Nemotron — find matching companies, pick the right decision-maker, write personalized emails, read the replies, and learn from the results.

This version is a hackathon demo built on simulation: research is real, outreach goes only to the team's own test inbox. See the [design spec](docs/superpowers/specs/2026-10-17-covora-design.md), [progress](docs/PROGRESS.md), and [decisions](docs/DECISIONS.md).

## Prerequisites

- Docker (for Postgres 16 + pgvector)
- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you)
- Node 20
- An NVIDIA API key from build.nvidia.com

## Setup

```bash
cp .env.example .env            # then fill in NVIDIA_API_KEY (and YDC_API_KEY)
docker compose up -d db         # builds Postgres 16 + pgvector on first run; listens on localhost:5434
cd backend && uv sync && uv run alembic upgrade head
uv run python scripts/smoke_nvidia.py   # live check: model IDs, JSON mode, embedding dimension
uv run python scripts/smoke_youcom.py   # live check: You.com search + contents (~$0.02)
cd ../frontend && npm install
```

If the smoke check prints an embedding dimension other than 2048, set `NEMOTRON_EMBED_DIM` in `.env` before running migrations (or re-run them: `uv run alembic downgrade base && uv run alembic upgrade head` on a fresh database).

## Run

Three processes:

```bash
# API on http://localhost:8000
cd backend && uv run uvicorn covora.api.app:app --reload --port 8000

# Worker: runs campaigns in the background
cd backend && uv run python -m covora.worker

# Web app on http://localhost:5180
cd frontend && npm run dev
```

Set `RESEARCH_PROVIDER=mock` (in `.env` or the shell, for both the API and the worker) to research a small fixture web of six fictional companies instead of You.com. Nothing is spent, and everything found is labeled synthetic.

## Test

```bash
cd backend && uv run pytest        # needs the db container running
cd frontend && npm test
```
