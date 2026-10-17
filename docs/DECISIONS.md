# Architecture decisions

One line per decision. Details and reasoning are in the [design spec](superpowers/specs/2026-10-17-covora-design.md) (§3).

## Product owner's decisions

- Orchestration with LangGraph.
- React frontend; Python + FastAPI backend; PostgreSQL.
- NVIDIA Nemotron for all AI work: Nano for light tasks, Super for complex reasoning.
- Fixed routing first; NeMo Switchyard added once the rest works.
- No Google sign-in; one local workspace.
- Live You.com queries for company and people research.
- The AI decides who the right prospect is.
- User approves the first batch of each campaign; after that Covora sends automatically within the daily limit.
- NVIDIA and You.com keys live in `.env`.
- Interested sales-call leads rotate round-robin across reps; Covora replies with the rep's booking link and CCs them.
- Interested dealers go to the next rep; Covora never quotes prices.
- Consumer (B2C) selling is out of this version.
- A demo built on simulation: real research, simulated outreach to the team's test inbox.
- Gmail: owner creates a Google Cloud project and a second @gmail.com account as the test inbox.
- Campaign sizing: prospects needed = goal ÷ expected reply rate (e.g. 10 replies at 1% → 1,000 prospects).
- Agent memory follows CoALA: working, episodic, semantic, procedural.

## Designer's calls

- React + Vite + TypeScript + Tailwind SPA (no Next.js).
- Every prospect address rewritten in code to the test inbox; no code path sends to a real address.
- Reply simulator with hidden preference profiles (`realistic` 1%, `accelerated` 6%).
- Mock dataset only for evals and fast simulation.
- Guardrails in code: suppression list, no invented emails, only pick people actually found.
- One contact per company plus a backup.
- Learning experiments: concurrent A/B arms, stats in code, power-based sample sizes, AI claims downgraded when unsupported.
- One worker process with a Postgres job table; Server-Sent Events for live updates.
- No open or click tracking; positive replies and meetings are the metrics.
- Gmail up to the daily cap, in-app delivery beyond it.
- Long-term memory in Covora's own `memory_item` table with pgvector (not LangGraph's Store).

## Implementation decisions

- Docker Postgres on host port 5434 (5432 and 5433 are taken by other local Postgres servers); frontend dev server on 5180 (5173 is taken).
- The database image is built locally from the official `postgres:16` image plus `postgresql-16-pgvector` (`docker/db/Dockerfile`), because Docker Hub was unreachable for `pgvector/pgvector`.
- Memory search is an exact cosine scan with no ANN index: pgvector's HNSW index is limited to 2000 dimensions, and memory is small.
- Embedding dimension defaults to 2048 and the NVIDIA structured-output mode to `guided_json`. Both are unconfirmed until `scripts/smoke_nvidia.py` runs with a real key.
- Trace spans are written when they open (status `running`) and completed when they close, so child rows can reference them and the UI can show live progress.
- Memory never blocks a decision: if retrieval or an episode write fails, the step continues and the failure is recorded on its span.
- Frontend uses the Vite template's current versions (React 19, Vite 8, TypeScript 6).
- Ruff rules pinned in `backend/pyproject.toml` (FastAPI `Depends()` defaults and intentional en dashes are allowed).
