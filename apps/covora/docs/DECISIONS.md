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
- Verified against the live NVIDIA API (2026-10-17):
  - The light tier uses `nvidia/nemotron-3.5-lightning-30b-a3b`, because `nemotron-nano-3-30b-a3b` isn't served to this account.
  - Super is `nvidia/nemotron-3-super-120b-a12b`.
  - Embeddings are `nvidia/nemotron-3-embed-1b`, with 2048 dimensions.
  - Structured output uses `response_format`; `guided_json` is rejected.
- Schemas sent to the model have their `$ref`s inlined and every property required, because hosted structured decoding skipped `$ref`'d and optional fields.
- Model reasoning is off by default for both tiers, with a per-task opt-in (`REASONING_TASKS`). On ICP parsing it made Super about 4× slower with no quality gain.
- You.com honors `site:` filters (live check, 2026-10-17), so people searches use `site:linkedin.com/in` first.
- Model strings in the ICP are cleaned of stray leading punctuation (e.g. `/owner`, `.Operations Manager`), a decoding artifact.
- Trace spans are written when they open (status `running`) and completed when they close, so child rows can reference them and the UI can show live progress.
- Memory never blocks a decision: if retrieval or an episode write fails, the step continues and the failure is recorded on its span.
- Frontend uses the Vite template's current versions (React 19, Vite 8, TypeScript 6).
- Ruff rules pinned in `backend/pyproject.toml` (FastAPI `Depends()` defaults and intentional en dashes are allowed).

## Plan 2 decisions

- Campaigns run in a separate worker process (`python -m covora.worker`) that claims jobs from a Postgres `job` table (`FOR UPDATE SKIP LOCKED`). Job handlers live in `covora.jobs.registry`.
- The campaign pipeline is a LangGraph `StateGraph`, checkpointed with `AsyncPostgresSaver` in its own `langgraph` schema. Its tables are created once at worker start, because `setup()` uses `CREATE INDEX CONCURRENTLY`, which waits on any open transaction.
- Campaign jobs are never auto-retried. **Retry** resumes from the last checkpoint, so discovery isn't paid for twice.
- Fit rules are stricter than the spec's baseline: a stated soft criterion that isn't met (e.g. company size) caps the score at 50, below the qualifying bar of 60.
- Fact extraction uses one slot per fact type (value or null). Numbers are kept only with a verbatim quote, and facts with no value are dropped.
- Emails are located on any of a company's sources. One counts as verified when the person's name appears on the same page.
- An individual contributor is never picked as the backup contact.
- Each discovery wave scores about twice the companies still needed, capped by `MAX_CANDIDATES_PER_WAVE`.
- Fact extraction only sees the company's own pages plus search results that name it.
- Live updates use polling; the spec's Server-Sent Events are deferred to Plan 6.
- `RESEARCH_PROVIDER=mock` switches research to a fixture web of six fictional `.test` companies, labeled synthetic.
- Every ORM model is imported in every process (`covora.db.all_models`), so foreign keys always resolve.
