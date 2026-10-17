# Progress

The build is split into six plans; each ends in working, tested software. Plans live in [docs/superpowers/plans/](superpowers/plans/).

| # | Plan | Status |
|---|---|---|
| 1 | Foundation + ICP Studio | Done (live model check pending a key) |
| 2 | Discovery & qualification | Not started |
| 3 | Drafts, approval & sending | Not started |
| 4 | Replies & simulation | Not started |
| 5 | Learning | Not started |
| 6 | Evals, Switchyard & polish | Not started |

## Plan 1: what works

- **Backend:** settings from `.env`; Postgres 16 + pgvector on port 5434; migrations; one local workspace.
- **Tracing:** every run, step, model call, and memory read/write is a span; secrets and model reasoning are redacted or dropped.
- **Model gateway:** Nano/Super fixed routing, JSON validation with one repair retry, fallback to the other tier, retries with backoff, an `llm_call` row per call, embeddings.
- **CoALA memory:** episodic and semantic memory with pgvector similarity, scope isolation (real vs mock), append-only outcomes, superseding, prompt versions as procedural memory.
- **Decision cycle (`run_step`):** retrieve → working memory (with token budgets) → reason → learn. Memory failures degrade to "no memories" instead of failing the step.
- **ICP planning agent:** vibe prompt → structured ICP with stated/inferred origins and a buyer map; the user's edits are remembered and shown to the agent next time.
- **API:** health, workspace, ICP parse/save/list, run list/detail, per-step working memory.
- **Web app:** sidebar shell; Settings → company profile; ICP Studio (interpret, edit, save versions, history); Agent Workflow (runs, span tree, model-call card, working-memory panel).
- **Tests:** 57 backend, 13 frontend; ruff and typecheck clean.

## Known gaps

- **Live model check not run yet:** add `NVIDIA_API_KEY` to `.env`, then run `cd backend && uv run python scripts/smoke_nvidia.py`. It confirms the model IDs, the JSON mode, and the embedding dimension (default 2048).
- NeMo Switchyard routing mode is a placeholder until Plan 6 (it currently behaves like fixed routing and says so).
- The worker process and LangGraph arrive in Plan 2.
