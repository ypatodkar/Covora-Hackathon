# Progress

The build is split into six plans; each ends in working, tested software. Plans live in [docs/superpowers/plans/](superpowers/plans/).

| # | Plan | Status |
|---|---|---|
| 1 | Foundation + ICP Studio | Done, verified live |
| 2 | Discovery & qualification | Done, verified live |
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

## Plan 2: what works

- **Launch from ICP Studio** with goal-based sizing: 10 replies at 1% → 1,000 prospects, about $44, shown before anything runs. You can cap it, and the budget is checked.
- **A background worker** runs a checkpointed LangGraph pipeline:
  - find companies in waves (You.com);
  - gather sourced facts;
  - score fit in code from the AI's per-criterion judgments;
  - find named people;
  - pick a primary and a backup.
- **Retry** resumes from the checkpoint without re-paying for discovery. A You.com budget cap stops research cleanly and keeps partial results.
- **Guardrails:** companies must appear in results, people must be named in sources, emails only verbatim, numbers only with quotes.
- **Prospects page:** companies with criteria chips and sourced facts (verified or unverified); people with pick reasons and email status; CSV exports with formula escaping.
- **Live check (2026-10-17):** a 5-prospect campaign on the real web found 34 companies, qualified 7, picked 4 people with source links, and spent about $0.49 (estimate: $0.63). The fixture-web run took under a minute.
- **Tests:** 128 backend, 26 frontend.

## Known gaps

- **Live check (2026-10-17):** the smoke check passes, and interpret → edit → save → interpret works with real models. The second run's working memory shows the user's edit. Super takes about 14 s per ICP with reasoning off.
- NeMo Switchyard routing mode is a placeholder until Plan 6 (it currently behaves like fixed routing and says so).
- A campaign can end with fewer prospects than its target when qualified companies have no findable contact. It doesn't loop back for more companies.
- Live updates poll every few seconds; Server-Sent Events are deferred.
- Public sources rarely print business emails, so most real contacts show "No email".
