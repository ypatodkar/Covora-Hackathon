# Covora Plan 1 — Foundation + ICP Studio: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the platform every Covora agent runs on, and prove it end to end with ICP Studio. The platform pieces are config, Postgres, tracing, the Nemotron model gateway, CoALA memory, and the decision cycle. The proof is that a user types a vibe prompt, Nemotron Super turns it into a structured ICP, the user edits and saves it, and the Agent Workflow page shows the run's spans, model call, routing decision, and working memory.

**Architecture:**
- Python FastAPI backend in `backend/covora`, on PostgreSQL 16 with pgvector, run in Docker.
- Every model call goes through `ModelGateway`, which picks Nano or Super (fixed routing), validates structured output, repairs and falls back, and logs an `llm_call` row plus a trace span.
- Agents run through one helper, `run_step`, which implements the CoALA decision cycle: observe → retrieve memories into working memory → reason via the gateway → learn by writing an episodic memory.
- React + Vite + Tailwind SPA in `frontend/` talks to `/api`.

**Tech Stack:**
- Backend: Python 3.12 (via `uv`), FastAPI, SQLAlchemy 2 (async, psycopg 3), Alembic, Pydantic v2 + pydantic-settings, pgvector, `openai` SDK pointed at NVIDIA's API, pytest + pytest-asyncio.
- Frontend: React 18, Vite, TypeScript, Tailwind CSS v4, React Router v6, TanStack Query v5, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-17-covora-design.md`. Read §3 (decisions), §7 (decision cycle and memory), §9.1 (structured ICP), §15 (gateway), and §16 (observability) before starting.

### Plan series

This is plan 1 of 6. Each plan ends in working, tested software.

| # | Plan | Spec build-order steps |
|---|---|---|
| **1** | **Foundation + ICP Studio (this plan)** | 1, 2, 3 |
| 2 | Discovery & qualification: job queue + worker, LangGraph campaign graph through `select_contacts`, You.com provider + cache + budget, goals & campaign sizing, Prospects UI, company/people CSV exports | 4, 5 |
| 3 | Drafts, approval & sending: templates, drafting, review-queue interrupt, Gmail OAuth (sender + test inbox), onboarding wizard, outreach service, in-app overflow, Gmail token status in health | 6, 7 |
| 4 | Replies & simulation: Gmail poll loop, reply graph, sales team + round-robin handoff, Inbox, reply simulator | 8 |
| 5 | Learning: episodic outcome writes, stats, learning graph, experiments and versions, mock dataset, fast simulation | 9 |
| 6 | Evals, Switchyard & polish: eval suites, Switchyard mode, Routing/Evaluations/Memory tabs, Overview, remaining exports | 10, 11 |

## Global Constraints

- **Python** `>=3.12`, managed by `uv`; the package name is `covora`.
- **Node** 20.
- **Postgres** 16 with pgvector, from Docker image `pgvector/pgvector:pg16`, host port **5433** (5432 is taken by a local Postgres).
- **Ports:** API on `localhost:8000`; frontend dev server on `localhost:5180` (5173 is taken), with `strictPort`.
- **Secrets** live only in `.env` (gitignored). `.env.example` lists every variable with no values. Settings hold secrets as `SecretStr`.
- **Model IDs come from env, never from code literals.** Defaults:
  - `NEMOTRON_NANO_MODEL=nvidia/nemotron-nano-3-30b-a3b`
  - `NEMOTRON_SUPER_MODEL=nvidia/nemotron-3-super-120b-a12b`
  - `NEMOTRON_EMBED_MODEL=nvidia/nemotron-3-embed-1b`
  - `NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1`
- **Every model call goes through `ModelGateway`.** Nothing else imports `openai`, except `covora/gateway/nvidia.py`.
- **Model reasoning text is never stored, logged, or returned by the API.** This covers `<think>` blocks and `reasoning_content`.
- **Redaction:** trace attributes, span errors, stored payloads, and API error messages all pass through `redact()`.
- **API errors** use the shape `{"error": {"code": str, "message": str, "details": object}}`.
- **Schema conventions:** one workspace row (seeded); UUID primary keys; `created_at`/`updated_at` on every table; JSONB for structured blobs.
- **Routing modes:** `fixed` (default), `switchyard`, `baseline_nano`, `baseline_super`. In this plan, `switchyard` behaves like `fixed` and records the reason `switchyard not enabled yet; used fixed` (it is implemented in Plan 6).
- **Sidebar labels, in order:** Overview · ICP Studio · Prospects · Campaigns · Inbox · Agent Workflow · Settings.
- **UI style:** white, minimal, spacious, left sidebar.
- **Docs:** keep `docs/PROGRESS.md` and `docs/DECISIONS.md` current; the last task of every plan updates them.

## Review Focus

These are the inputs and failure modes the spec implies but most likely to bite a real user. Each one has a pinned test in the task named.

1. **Model output wrapped in ```` ```json ```` fences, prefixed by prose, or containing `<think>…</think>`.** It must still parse, and the reasoning must never be stored. Pinned in Task 4: `test_extract_json_handles_fences_prose_and_think`.
2. **NVIDIA unreachable, rate-limited (429), or key missing.** The gateway retries, then falls back, then raises `GatewayError`. The API returns 502 with `model_unavailable`, the run is marked `failed` with a span error, and ICP Studio shows a readable message. Pinned in Task 5 `test_all_attempts_fail_raises_and_logs`, Task 11 `test_parse_returns_502_when_models_unavailable`, and Task 14 `shows model-unavailable error`.
3. **Secrets inside exception text** (e.g. `Authorization: Bearer nvapi-…` in an SDK error). Redacted in `span.error` and in API errors. Pinned in Task 3: `test_span_error_is_redacted`.
4. **Vague or contradictory vibe prompts** ("find some companies"; "5–25 employees, at least 100 employees"). A contradictory range fails validation, which triggers the gateway's repair retry; a vague prompt gives empty lists plus assumptions, and the UI renders the empty sections as editable. Pinned in Task 9 `test_range_min_greater_than_max_rejected` and `test_vague_icp_is_valid`, and Task 14 `renders empty sections as editable`.
5. **First run with nothing in the database** (no company profile, no ICP versions, no runs). Parsing still works with zero memories, and every page shows an empty state instead of crashing. Pinned in Task 8 `test_run_step_with_no_memories`, Task 13 `shows empty profile form`, and Task 15 `shows empty runs state`.

---

## File Structure

```
.gitignore
.env.example
docker-compose.yml
docker/init/01-test-db.sql
README.md
docs/PROGRESS.md
docs/DECISIONS.md
backend/
  pyproject.toml
  alembic.ini
  migrations/env.py
  migrations/versions/            # one migration per task that adds tables
  scripts/smoke_nvidia.py         # live check of models, JSON mode, reasoning, embed dim
  covora/
    config.py                     # Settings
    db/base.py                    # DeclarativeBase + id/timestamp mixin
    db/session.py                 # engine + sessionmaker factories
    workspace/models.py           # Workspace
    workspace/service.py          # ensure_workspace, update_profile
    observability/models.py       # WorkflowRun, Span, LlmCall
    observability/redaction.py    # redact
    observability/tracing.py      # RunContext, start_run, finish_run, span
    gateway/tasks.py              # TaskType, Tier, TASK_TIERS, REASONING_DEFAULT
    gateway/router.py             # RoutingDecision, choose_route, other_tier
    gateway/output.py             # strip_reasoning, extract_json
    gateway/pricing.py            # ModelPrice, estimate_cost
    gateway/backend.py            # ChatBackend protocol, ChatResponse, BackendError
    gateway/nvidia.py             # NvidiaBackend (only importer of openai)
    gateway/gateway.py            # ModelGateway, GatewayResult, RoutingInfo, GatewayError
    memory/models.py              # MemoryItem, MemoryRead, PromptVersion
    memory/store.py               # NewMemory, MemoryQuery, RetrievedMemory, MemoryStore
    memory/prompts.py             # sync_prompts, get_prompt, render_prompt
    agents/step.py                # WorkingMemory, StepResult, run_step
    icp/schemas.py                # StructuredICP and parts
    icp/models.py                 # IcpVersion
    icp/agent.py                  # parse_icp
    icp/service.py                # diff_icp, save_icp_version
    prompts/icp_parsing.md        # procedural memory: the ICP prompt
    api/app.py                    # create_app
    api/deps.py                   # Services, get_services, get_session
    api/errors.py                 # ApiError + handlers
    api/routes/health.py
    api/routes/workspace.py
    api/routes/icp.py
    api/routes/runs.py
  tests/
    conftest.py                   # settings, migrated test DB, cleanup, fixtures
    fakes.py                      # FakeChatBackend, fake_embedding
    test_*.py                     # one file per task area
frontend/
  package.json  vite.config.ts  tsconfig.json  index.html
  src/main.tsx  src/App.tsx  src/styles.css
  src/api/client.ts  src/api/types.ts
  src/components/Layout.tsx  src/components/Sidebar.tsx  src/components/EmptyState.tsx
  src/pages/{Overview,IcpStudio,Prospects,Campaigns,Inbox,AgentWorkflow,RunDetail,Settings}.tsx
  src/features/icp/{IcpEditor,TaggedList,OriginBadge,VersionHistory}.tsx
  src/features/runs/{SpanTree,LlmCallCard,WorkingMemoryPanel}.tsx
  src/test/setup.ts
  src/**/*.test.tsx
```

---

### Task 1: Repo skeleton, settings, docs scaffolding

**Files:**
- Create: `.gitignore`, `.env.example`, `docker-compose.yml`, `docker/init/01-test-db.sql`, `README.md` (replace), `docs/PROGRESS.md`, `docs/DECISIONS.md`
- Create: `backend/pyproject.toml`, `backend/covora/__init__.py`, `backend/covora/config.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces:
  - `Settings` (pydantic-settings, reads `.env` from the repo root), with these fields:
    - `database_url: str = "postgresql+psycopg://covora:covora@localhost:5433/covora"`
    - `nvidia_api_key: SecretStr | None`
    - `nvidia_base_url: str`
    - `nvidia_structured_mode: Literal["guided_json","response_format","none"] = "guided_json"`
    - `nemotron_nano_model: str`, `nemotron_super_model: str`, `nemotron_embed_model: str`
    - `nemotron_embed_dim: int = 2048`
    - `routing_mode: Literal["fixed","switchyard","baseline_nano","baseline_super"] = "fixed"`
    - `nano_timeout_s: float = 60`, `super_timeout_s: float = 180`
    - `nano_concurrency: int = 8`, `super_concurrency: int = 4`
    - `retry_base_delay_s: float = 1.0` (tests set it to 0)
    - `model_prices: dict[str, ModelPriceConfig] = {}` (env `MODEL_PRICES` as JSON: `{"model": {"input_per_m": float, "output_per_m": float}}`)
    - `log_llm_payloads: bool = True`
    - `ydc_api_key: SecretStr | None`, `youcom_budget_usd: float = 80`
    - `google_client_id: str | None`, `google_client_secret: SecretStr | None`, `token_encryption_key: SecretStr | None`
    - `cors_origin: str = "http://localhost:5180"`
  - `Settings` methods:
    - `memory_enabled(agent: str) -> bool`: reads `MEMORY_ENABLED_<AGENT>` from the environment; true unless the value is `false`/`0`.
    - `secret_values() -> list[str]`: the non-empty values of every `SecretStr` field.
  - `get_settings() -> Settings` (cached).

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_config.py`

```python
def test_defaults(monkeypatch):
    s = Settings(_env_file=None)
    assert s.routing_mode == "fixed"
    assert s.nemotron_nano_model == "nvidia/nemotron-nano-3-30b-a3b"
    assert s.nemotron_super_model == "nvidia/nemotron-3-super-120b-a12b"
    assert s.database_url.endswith("@localhost:5433/covora")

def test_secret_not_in_repr(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-abc123secret")
    s = Settings(_env_file=None)
    assert "nvapi-abc123secret" not in repr(s)
    assert s.secret_values() == ["nvapi-abc123secret"]

def test_memory_enabled_flag(monkeypatch):
    monkeypatch.setenv("MEMORY_ENABLED_ICP", "false")
    s = Settings(_env_file=None)
    assert s.memory_enabled("icp") is False
    assert s.memory_enabled("email") is True
```

- [ ] **Step 2: Set up the project and confirm the tests fail.** In `backend/`, write `pyproject.toml` with:
  - `requires-python = ">=3.12"`
  - dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]>=2.0`, `psycopg[binary]>=3.2`, `alembic`, `pydantic>=2`, `pydantic-settings`, `pgvector`, `openai>=1.40`, `httpx`
  - dev group: `pytest`, `pytest-asyncio`, `ruff`
  - `[tool.pytest.ini_options] asyncio_mode = "auto"`, `testpaths = ["tests"]`

  Then run: `cd backend && uv python install 3.12 && uv sync && uv run pytest tests/test_config.py -v`
  Expected: FAIL with `ModuleNotFoundError: covora.config`.

- [ ] **Step 3: Implement `Settings` and `get_settings()` in `backend/covora/config.py`.** Set `env_file` to the repo-root `.env` (two levels up from this file).

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `uv run pytest tests/test_config.py -v`. Expected: 3 passed.

- [ ] **Step 5: Write the repo files**
  - **`.gitignore`:** `.env`, `.venv/`, `__pycache__/`, `node_modules/`, `dist/`, `.pytest_cache/`, `.ruff_cache/`, `*.egg-info/`, `.DS_Store`.
  - **`.env.example`:** every Settings variable, plus `TEST_DATABASE_URL=postgresql+psycopg://covora:covora@localhost:5433/covora_test`, all with empty values or defaults. No real values.
  - **`docker-compose.yml`:** service `db` from image `pgvector/pgvector:pg16`, env `POSTGRES_USER=covora`, `POSTGRES_PASSWORD=covora`, `POSTGRES_DB=covora`, ports `"5433:5432"`, volume `covora_pg`, and `./docker/init` mounted to `/docker-entrypoint-initdb.d`.
  - **`docker/init/01-test-db.sql`:** `CREATE DATABASE covora_test;`
  - **`README.md`:** what Covora is (two sentences from spec §1), prerequisites, setup (`cp .env.example .env`, `docker compose up -d db`, `cd backend && uv sync && uv run alembic upgrade head`, `cd frontend && npm install`), and run commands (`uv run uvicorn covora.api.app:app --reload --port 8000`, `npm run dev`).
  - **`docs/PROGRESS.md`:** the plan-series table, with Plan 1 "in progress".
  - **`docs/DECISIONS.md`:** one line per decision from spec §3, each linking to the spec.

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example docker-compose.yml docker README.md docs/PROGRESS.md docs/DECISIONS.md backend/pyproject.toml backend/uv.lock backend/covora backend/tests/test_config.py
git commit -m "chore: scaffold repo, settings, and docs"
```

---

### Task 2: Database plumbing and the workspace

**Files:**
- Create: `backend/covora/db/base.py`, `backend/covora/db/session.py`, `backend/covora/workspace/models.py`, `backend/covora/workspace/service.py`
- Create: `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_workspace.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_workspace.py`

**Interfaces:**
- Consumes: `Settings`.
- Produces:
  - `Base` (DeclarativeBase) and `IdTimestampMixin`, which supplies `id: UUID` (default uuid4), `created_at`, and `updated_at`, all server-defaulted.
  - `make_engine(url: str) -> AsyncEngine` and `make_sessionmaker(engine) -> async_sessionmaker[AsyncSession]`.
  - `Workspace` ORM, table `workspace`: `name: str`, `website: str | None`, `description: str | None`, `value_props: list[str]` (JSONB, default `[]`), `offering_type: str` (default `"sales_call"`), `settings: dict` (JSONB, default `{}`).
  - `ensure_workspace(session) -> Workspace`: creates the single row with `name="My company"` if none exists; otherwise returns the existing row.
  - `update_profile(session, ws: Workspace, data: WorkspaceProfile) -> Workspace`, where `WorkspaceProfile` is a Pydantic model with `name`, `website`, `description`, `value_props`, and `offering_type: Literal["sales_call","dealer"]`.
  - **Test fixtures** in `tests/conftest.py`:
    - `settings`: `Settings` with `database_url` set to `TEST_DATABASE_URL`, a fake NVIDIA key `nvapi-test-key-000000`, a fake You.com key, and `retry_base_delay_s=0`.
    - `sessionmaker` (session-scoped): runs `alembic upgrade head` programmatically against the test DB once.
    - autouse `clean_db`: after each test, `TRUNCATE` every table except `alembic_version`, with `RESTART IDENTITY CASCADE`.
    - `session`: one `AsyncSession` per test.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_workspace.py`

```python
async def test_ensure_workspace_is_idempotent(session):
    a = await ensure_workspace(session)
    b = await ensure_workspace(session)
    assert a.id == b.id
    assert (await session.execute(select(func.count()).select_from(Workspace))).scalar() == 1

async def test_update_profile(session):
    ws = await ensure_workspace(session)
    ws = await update_profile(session, ws, WorkspaceProfile(
        name="Acme Robotics", website="https://acme.example", description="Cobots for small factories",
        value_props=["Pays back in 9 months"], offering_type="sales_call"))
    assert ws.name == "Acme Robotics" and ws.value_props == ["Pays back in 9 months"]

async def test_vector_extension_installed(session):
    row = (await session.execute(text("select extname from pg_extension where extname='vector'"))).scalar()
    assert row == "vector"
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `docker compose up -d db && cd backend && uv run pytest tests/test_workspace.py -v`. Expected: FAIL (imports missing).

- [ ] **Step 3: Implement the database plumbing**
  - `db/base.py`, `db/session.py`, `workspace/models.py`, `workspace/service.py`.
  - Alembic setup (`alembic init -t async migrations`). `env.py` uses `config.get_main_option("sqlalchemy.url")` when it is set, otherwise `get_settings().database_url`, and imports every models module so autogenerate sees all tables.
  - Migration `0001_workspace` runs `CREATE EXTENSION IF NOT EXISTS vector` and creates `workspace`.

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `uv run pytest tests/test_workspace.py -v`. Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/covora/db backend/covora/workspace backend/alembic.ini backend/migrations backend/tests/conftest.py backend/tests/test_workspace.py
git commit -m "feat(db): add async database plumbing and workspace"
```

---

### Task 3: Tracing and redaction

**Files:**
- Create: `backend/covora/observability/models.py`, `backend/covora/observability/redaction.py`, `backend/covora/observability/tracing.py`
- Create: `backend/migrations/versions/0002_observability.py`
- Test: `backend/tests/test_tracing.py`, `backend/tests/test_redaction.py`

**Interfaces:**
- Consumes: `make_sessionmaker`, `Workspace`.
- Produces:
  - **ORM tables:**
    - `WorkflowRun` (table `workflow_run`): `kind: str` (`icp|campaign|reply|learning|eval`), `workspace_id`, `campaign_id: UUID | None` (no FK yet), `status` (`running|succeeded|failed`), `started_at`, `ended_at`, `error`, `thread_id: str | None`.
    - `Span` (table `span`): `run_id` (FK), `trace_id: str`, `parent_span_id: UUID | None`, `name`, `kind` (`stage|agent|llm|tool|http|db|memory`), `status` (`ok|error`), `started_at`, `duration_ms`, `attributes` (JSONB), `error`.
    - `LlmCall` (table `llm_call`): `span_id` (FK), `task`, `routing_mode`, `requested_model`, `actual_model`, `routing_reason`, `fallback_used: bool`, `fallback_reason`, `prompt_tokens`, `completion_tokens`, `latency_ms`, `est_cost_usd: float | None`, `output_valid: bool`, `retries: int`, `request_payload` (JSONB, nullable), `response_text` (nullable).
  - `redact(value: Any, secrets: Sequence[str]) -> Any`: walks dicts, lists, and strings recursively. It replaces each secret value and each pattern match with `[REDACTED]`. Patterns:
    - `nvapi-[A-Za-z0-9_\-]{8,}`
    - `Bearer\s+[A-Za-z0-9._\-]+`
    - `ya29\.[A-Za-z0-9._\-]+`
    - `1//[A-Za-z0-9._\-]{20,}`
  - `@dataclass RunContext`: `run_id: UUID`, `trace_id: str`, `workspace_id: UUID`, `span_id: UUID | None`, `sessionmaker`, `secrets: list[str]`. Method `child(span_id) -> RunContext`.
  - `start_run(sessionmaker, *, kind: str, workspace_id: UUID, secrets: list[str], campaign_id: UUID | None = None) -> RunContext`.
  - `finish_run(ctx, *, status: Literal["succeeded","failed"], error: str | None = None) -> None`, which redacts `error`.
  - `span(ctx, name: str, kind: SpanKind, attributes: dict | None = None)`, an async context manager. It yields a `SpanHandle` with `.ctx` (the child `RunContext`), `.id`, and `.set(key, value)`.
    - On exit it writes the row: status `ok`, or `error` with the redacted `str(exc)`. Exceptions are re-raised.
    - Attributes are redacted before writing.
    - It writes in its own short session from `ctx.sessionmaker`, so trace rows survive a rolled-back business transaction.

- [ ] **Step 1: Write the failing tests**

```python
# test_redaction.py
def test_redacts_secret_values_and_patterns():
    out = redact({"msg": "key nvapi-AAAA1111BBBB and Bearer ya29.tok", "list": ["s3cret"]}, ["s3cret"])
    assert "nvapi-" not in out["msg"] and "ya29." not in out["msg"] and out["list"] == ["[REDACTED]"]

# test_tracing.py
async def test_nested_spans_record_parents(sessionmaker, workspace):
    ctx = await start_run(sessionmaker, kind="icp", workspace_id=workspace.id, secrets=[])
    async with span(ctx, "outer", "agent") as outer:
        async with span(outer.ctx, "inner", "llm") as inner:
            inner.set("model", "nano")
    rows = await fetch_spans(sessionmaker, ctx.run_id)          # helper in conftest
    inner_row = next(r for r in rows if r.name == "inner")
    assert inner_row.parent_span_id == outer.id and inner_row.attributes["model"] == "nano"

async def test_span_error_is_redacted(sessionmaker, workspace):
    ctx = await start_run(sessionmaker, kind="icp", workspace_id=workspace.id, secrets=["nvapi-test-key-000000"])
    with pytest.raises(RuntimeError):
        async with span(ctx, "call", "llm"):
            raise RuntimeError("401 Authorization: Bearer nvapi-test-key-000000")
    row = (await fetch_spans(sessionmaker, ctx.run_id))[0]
    assert row.status == "error" and "nvapi-test-key-000000" not in row.error

async def test_finish_run_failed(sessionmaker, workspace):
    ctx = await start_run(sessionmaker, kind="icp", workspace_id=workspace.id, secrets=[])
    await finish_run(ctx, status="failed", error="boom")
    run = await get_run(sessionmaker, ctx.run_id)                 # helper in conftest
    assert run.status == "failed" and run.ended_at is not None
```

  Add a `workspace` fixture (`ensure_workspace`) and the helpers `fetch_spans` and `get_run` to `conftest.py`.

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_tracing.py tests/test_redaction.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement the models, migration `0002_observability`, `redact`, and the tracing functions** with the signatures above. Set `trace_id` to `uuid4().hex`.

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `uv run pytest tests/test_tracing.py tests/test_redaction.py -v`. Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/covora/observability backend/migrations/versions backend/tests
git commit -m "feat(observability): add runs, spans, llm_call tables and redaction"
```

---

### Task 4: Gateway building blocks: tasks, routing, output parsing, pricing

**Files:**
- Create: `backend/covora/gateway/tasks.py`, `router.py`, `output.py`, `pricing.py`
- Test: `backend/tests/test_gateway_parts.py`

**Interfaces:**
- Produces:
  - `TaskType(StrEnum)` with exactly these values:
    - Nano tasks: `query_generation`, `company_extraction`, `fact_extraction`, `people_extraction`, `email_draft`, `handoff_reply_draft`, `reply_classification`, `sim_reply_writing`, `routing_judge`.
    - Super tasks: `icp_parsing`, `company_fit`, `contact_selection`, `reply_reclassification`, `learning_analysis`, `eval_judge`.
    - Plus `embedding`.
  - `Tier(StrEnum)`: `nano`, `super`.
  - `TASK_TIERS: dict[TaskType, Tier]`, matching spec §15.2 (`embedding` is excluded).
  - `REASONING_DEFAULT: dict[Tier, bool] = {Tier.nano: False, Tier.super: True}`.
  - `@dataclass(frozen=True) ModelIds(nano: str, super: str)` and `ModelIds.for_tier(tier) -> str`.
  - `@dataclass(frozen=True) RoutingDecision(tier: Tier, model: str, mode: str, reason: str)`.
  - `choose_route(task: TaskType, mode: str, models: ModelIds) -> RoutingDecision`. Reason strings, exactly:
    - `fixed`: `"fixed: <task> → <tier>"`
    - `baseline_nano`: `"baseline: all tasks → nano"`
    - `baseline_super`: `"baseline: all tasks → super"`
    - `switchyard`: the fixed tier with reason `"switchyard not enabled yet; used fixed"`
  - `other_tier(tier: Tier) -> Tier`.
  - `strip_reasoning(text: str) -> str`: removes every `<think>…</think>` block, plus an unterminated leading `<think>` up to the first blank line after it closes or to the end of text, then trims whitespace.
  - `extract_json(text: str) -> str`: calls `strip_reasoning`, then returns the first balanced top-level JSON object or array. It handles ```` ```json ```` fences and leading or trailing prose, and raises `ValueError("no JSON found")` when there is none.
  - `@dataclass ModelPrice(input_per_m: float, output_per_m: float)` and `estimate_cost(model: str, prompt_tokens: int, completion_tokens: int, prices: Mapping[str, ModelPrice]) -> float | None` (returns `None` when the model is unpriced).

- [ ] **Step 1: Write the failing tests**

```python
def test_fixed_routing_uses_task_tier():
    m = ModelIds(nano="N", super="S")
    d = choose_route(TaskType.icp_parsing, "fixed", m)
    assert (d.tier, d.model, d.reason) == (Tier.super, "S", "fixed: icp_parsing → super")

def test_baselines_override_tier():
    m = ModelIds(nano="N", super="S")
    assert choose_route(TaskType.icp_parsing, "baseline_nano", m).model == "N"
    assert choose_route(TaskType.email_draft, "baseline_super", m).model == "S"

def test_switchyard_falls_back_to_fixed_for_now():
    d = choose_route(TaskType.email_draft, "switchyard", ModelIds("N", "S"))
    assert d.model == "N" and d.reason == "switchyard not enabled yet; used fixed"

def test_every_non_embedding_task_has_a_tier():
    assert set(TASK_TIERS) == set(TaskType) - {TaskType.embedding}

def test_extract_json_handles_fences_prose_and_think():
    raw = '<think>secret plan</think>\nSure! Here it is:\n```json\n{"a": {"b": [1, 2]}}\n```\nHope that helps.'
    assert json.loads(extract_json(raw)) == {"a": {"b": [1, 2]}}
    assert "secret plan" not in strip_reasoning(raw)

def test_extract_json_raises_without_json():
    with pytest.raises(ValueError):
        extract_json("no json here")

def test_estimate_cost():
    prices = {"S": ModelPrice(input_per_m=1.0, output_per_m=2.0)}
    assert estimate_cost("S", 1_000_000, 500_000, prices) == pytest.approx(2.0)
    assert estimate_cost("unknown", 10, 10, prices) is None
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_gateway_parts.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement the four modules.** In `extract_json`, find the matching brace by scanning with a depth counter that respects JSON strings and escapes.

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `uv run pytest tests/test_gateway_parts.py -v`. Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/covora/gateway backend/tests/test_gateway_parts.py
git commit -m "feat(gateway): add task tiers, routing decisions, output parsing, pricing"
```

---

### Task 5: ModelGateway (validation, repair, fallback, logging, embeddings)

**Files:**
- Create: `backend/covora/gateway/backend.py`, `backend/covora/gateway/gateway.py`, `backend/tests/fakes.py`
- Test: `backend/tests/test_gateway.py`

**Interfaces:**
- Consumes: Task 3 tracing (`span`, `RunContext`, `LlmCall`) and all of Task 4.
- Produces:
  - `@dataclass ChatResponse(text: str, prompt_tokens: int, completion_tokens: int, model: str)`.
  - `class BackendError(Exception)`, with `status: int | None` and `retryable: bool`. It is retryable for 429, ≥500, timeouts, and connection errors.
  - `class ChatBackend(Protocol)`, with two methods:
    - `chat(*, model, messages: list[dict], json_schema: dict | None, reasoning: bool, timeout_s: float) -> ChatResponse`
    - `embed(*, model, texts: list[str], input_type: Literal["query","passage"], timeout_s: float) -> list[list[float]]`
  - `@dataclass RoutingInfo(mode, decision_reason, requested_model, actual_model, fallback_used: bool, fallback_reason: str | None)`.
  - `@dataclass GatewayResult[T](output: T, text: str, model: str, prompt_tokens: int, completion_tokens: int, latency_ms: int, est_cost_usd: float | None, retries: int, routing: RoutingInfo, llm_call_id: UUID)`.
  - `class GatewayError(Exception)`.
  - `class ModelGateway(backend: ChatBackend, settings: Settings)`, with two methods:
    - `complete(task: TaskType, messages: list[dict], *, schema: type[T] | None, ctx: RunContext, reasoning: bool | None = None) -> GatewayResult[T]`
    - `embed(texts: list[str], *, ctx: RunContext, input_type: Literal["query","passage"]) -> list[list[float]]`
  - In `tests/fakes.py`:
    - `FakeChatBackend`, with `queue(model: str, *items: str | Exception)` and `.calls: list[dict]`. Its embed calls use `fake_embedding`.
    - `fake_embedding(text: str, dim: int) -> list[float]`: a deterministic hashed bag of words, L2-normalized, so shared words give higher cosine similarity.
    - Constants `NANO` and `SUPER` (the default model IDs), `MSGS = [{"role": "user", "content": "x"}]`, and the Pydantic test model `Answer(value: int)`.
  - Add to `conftest.py`:
    - fixtures `fake_backend`, `gateway` (`ModelGateway(fake_backend, settings)`), and `ctx` (`start_run(kind="icp")` for the seeded workspace);
    - helper `latest_llm_call(sessionmaker) -> LlmCall`.
- **`complete` behavior** (spec §15.4), for one call:
  1. Choose the route with `choose_route(task, settings.routing_mode, ModelIds(...))`. Reasoning defaults to `REASONING_DEFAULT[tier]`.
  2. Each tier's attempt runs inside that tier's semaphore (`nano_concurrency` / `super_concurrency`) with that tier's timeout.
  3. Transport errors with `retryable=True` are retried up to 3 times, sleeping `retry_base_delay_s` × 1, 2, 4, each plus up to 25% jitter.
  4. When `schema` is set: pass `schema.model_json_schema()` as `json_schema`, then run `extract_json` and `schema.model_validate_json`.
     - If that fails, make **one repair call** on the same model, appending the assistant's stripped text and the user message `"Your previous reply was not valid JSON for the required schema. Error: <error>. Reply with only the corrected JSON."`
  5. If the primary tier still fails (invalid after repair, a non-retryable error, or retries exhausted), run the same procedure **once** on `other_tier`. Set `fallback_used=True` and record the failure as `fallback_reason`, redacted.
  6. If both tiers fail, raise `GatewayError` after logging.
- **Logging:**
  - One `span(kind="llm", name=f"llm:{task}")` per call.
  - One `LlmCall` row per call, with tokens summed across all attempts and `retries` = number of extra backend calls.
  - `request_payload` and `response_text` are stored only when `log_llm_payloads` is set. Both are redacted, and `response_text` is stored after `strip_reasoning`.
- **`embed` behavior:** batches of 32 inputs. Routing mode does not apply. It writes an `LlmCall` with `task="embedding"` and `routing_mode="n/a"`.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_gateway.py`. In these tests, `backend` is the `fake_backend` fixture.

```python
async def test_valid_output(gateway, backend, ctx):
    backend.queue(settings.nemotron_super_model, '{"value": 3}')
    r = await gateway.complete(TaskType.icp_parsing, [{"role": "user", "content": "x"}], schema=Answer, ctx=ctx)
    assert r.output.value == 3 and r.retries == 0 and r.routing.fallback_used is False

async def test_repair_retry_same_model(gateway, backend, ctx):
    backend.queue(SUPER, "not json", '{"value": 4}')
    r = await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    assert r.output.value == 4 and r.retries == 1 and r.model == SUPER
    assert "not valid JSON" in backend.calls[1]["messages"][-1]["content"]

async def test_fallback_to_other_tier(gateway, backend, ctx):
    backend.queue(SUPER, "bad", "still bad")
    backend.queue(NANO, '{"value": 5}')
    r = await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    assert r.model == NANO and r.routing.fallback_used and r.routing.actual_model == NANO

async def test_retryable_transport_error_is_retried(gateway, backend, ctx):
    backend.queue(SUPER, BackendError("429", status=429, retryable=True), '{"value": 1}')
    r = await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    assert r.output.value == 1 and r.model == SUPER

async def test_all_attempts_fail_raises_and_logs(gateway, backend, ctx, sessionmaker):
    backend.queue(SUPER, *[BackendError("503", status=503, retryable=True)] * 4)
    backend.queue(NANO, *[BackendError("503", status=503, retryable=True)] * 4)
    with pytest.raises(GatewayError):
        await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    call = await latest_llm_call(sessionmaker)                   # helper in conftest
    assert call.output_valid is False and call.fallback_used is True

async def test_reasoning_never_stored(gateway, backend, ctx, sessionmaker):
    backend.queue(SUPER, '<think>internal chain</think>{"value": 2}')
    await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    call = await latest_llm_call(sessionmaker)
    assert "internal chain" not in (call.response_text or "")

async def test_llm_call_row_fields(gateway, backend, ctx, sessionmaker):
    backend.queue(SUPER, '{"value": 3}')
    await gateway.complete(TaskType.icp_parsing, MSGS, schema=Answer, ctx=ctx)
    call = await latest_llm_call(sessionmaker)
    assert call.task == "icp_parsing" and call.routing_mode == "fixed"
    assert call.routing_reason == "fixed: icp_parsing → super" and call.requested_model == SUPER

async def test_embed_logs_call(gateway, ctx, sessionmaker):
    vecs = await gateway.embed(["a b", "c d"], ctx=ctx, input_type="passage")
    assert len(vecs) == 2 and len(vecs[0]) == settings.nemotron_embed_dim
    assert (await latest_llm_call(sessionmaker)).task == "embedding"
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_gateway.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement `backend.py`, `gateway.py`, and `tests/fakes.py`** with the interfaces and behavior above.

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `uv run pytest tests/test_gateway.py -v`. Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/covora/gateway backend/tests
git commit -m "feat(gateway): add ModelGateway with repair, fallback, logging, embeddings"
```

---

### Task 6: NVIDIA backend and live smoke check

**Files:**
- Create: `backend/covora/gateway/nvidia.py`, `backend/scripts/smoke_nvidia.py`
- Test: `backend/tests/test_nvidia_backend.py`

**Interfaces:**
- Consumes: `ChatBackend`, `ChatResponse`, `BackendError`, `Settings`.
- Produces: `NvidiaBackend(settings)`, which implements `ChatBackend` using `openai.AsyncOpenAI(base_url=settings.nvidia_base_url, api_key=...)`.
  - **Structured output:** depends on `nvidia_structured_mode`.
    - `guided_json`: `extra_body={"nvext": {"guided_json": schema}}`.
    - `response_format`: `response_format={"type": "json_schema", "json_schema": {"name": "output", "schema": schema}}`.
    - `none`: nothing; rely on the prompt plus validation.
  - **Reasoning:** `extra_body["chat_template_kwargs"] = {"enable_thinking": reasoning}`.
  - **Response text:** use `message.content`, and ignore any `reasoning_content` field.
  - **Errors:** map `openai.RateLimitError`, `APITimeoutError`, `APIConnectionError`, and `InternalServerError` to `BackendError(retryable=True)`, and other `APIStatusError` to `retryable=False`, keeping the status.
  - **Embeddings:** `client.embeddings.create(model, input=texts, extra_body={"input_type": input_type, "truncate": "END"})`.
- `scripts/smoke_nvidia.py`: exits 0 only if every check passes. It prints one line per check:
  - `OK models` (the three configured IDs are in `GET /models`)
  - `OK nano-json`
  - `OK super-json` (with reasoning on; checks that no reasoning text remains after `strip_reasoning`)
  - `OK embed dim=<n>`
  - `OK structured-mode=<mode>`

  If a structured mode fails, it tries the others and prints which one works.

- [ ] **Step 1: Write the failing test.** Stub the HTTP layer with an `httpx.MockTransport` passed to `AsyncOpenAI(http_client=...)`.
  - Fixture `nvidia_with_transport(handler)` builds `NvidiaBackend(settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))`.
  - `CHAT_OK` is a minimal OpenAI chat-completion JSON with `content='{"ok": true}'` and usage.
  - `CHAT_WITH_REASONING_CONTENT` is the same, plus `"reasoning_content": "hidden"` on the message.

```python
async def test_maps_429_to_retryable(nvidia_with_transport):
    backend = nvidia_with_transport(lambda req: httpx.Response(429, json={"error": "slow down"}))
    with pytest.raises(BackendError) as e:
        await backend.chat(model="m", messages=[{"role": "user", "content": "hi"}], json_schema=None, reasoning=False, timeout_s=5)
    assert e.value.retryable and e.value.status == 429

async def test_sends_guided_json_and_thinking_flag(nvidia_with_transport):
    seen = {}
    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json=CHAT_OK)                 # minimal OpenAI chat response fixture
    backend = nvidia_with_transport(handler)
    await backend.chat(model="m", messages=MSGS, json_schema={"type": "object"}, reasoning=True, timeout_s=5)
    assert seen["nvext"]["guided_json"] == {"type": "object"}
    assert seen["chat_template_kwargs"] == {"enable_thinking": True}

async def test_ignores_reasoning_content(nvidia_with_transport):
    backend = nvidia_with_transport(lambda req: httpx.Response(200, json=CHAT_WITH_REASONING_CONTENT))
    r = await backend.chat(model="m", messages=MSGS, json_schema=None, reasoning=True, timeout_s=5)
    assert r.text == '{"ok": true}'
```

- [ ] **Step 2: Run the test and confirm it fails.** Run: `uv run pytest tests/test_nvidia_backend.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement `NvidiaBackend` and `scripts/smoke_nvidia.py`.** `NvidiaBackend` accepts an optional `http_client` for tests.

- [ ] **Step 4: Run the test and confirm it passes.** Run: `uv run pytest tests/test_nvidia_backend.py -v`. Expected: 3 passed.

- [ ] **Step 5: Run the live smoke check.** This needs a real `NVIDIA_API_KEY` in `.env`; if it is missing, stop and ask the user to add it.
  - Run: `uv run python scripts/smoke_nvidia.py`
  - Expected: five `OK` lines.
  - If the printed embed dimension is not 2048, set `NEMOTRON_EMBED_DIM` in `.env` and `.env.example` before Task 7.
  - If a structured mode other than `guided_json` is the one that works, set `NVIDIA_STRUCTURED_MODE`.
  - Record both results in `docs/DECISIONS.md`.

- [ ] **Step 6: Commit**

```bash
git add backend/covora/gateway/nvidia.py backend/scripts/smoke_nvidia.py backend/tests/test_nvidia_backend.py docs/DECISIONS.md .env.example
git commit -m "feat(gateway): add NVIDIA backend and live smoke check"
```

---

### Task 7: Memory store and prompt registry (CoALA long-term + procedural memory)

**Files:**
- Create: `backend/covora/memory/models.py`, `backend/covora/memory/store.py`, `backend/covora/memory/prompts.py`
- Create: `backend/migrations/versions/0003_memory.py`
- Test: `backend/tests/test_memory_store.py`, `backend/tests/test_prompts.py`

**Interfaces:**
- Consumes: `ModelGateway.embed`, `RunContext`, `span`, `Workspace`.
- Produces:
  - **ORM tables** (spec §18, Memory):
    - `MemoryItem` (table `memory_item`): `workspace_id`, `kind`, `subtype`, `source`, `summary`, `payload`, `source_refs`, `outcome`, `evidence_level`, `superseded_by`, and `embedding: Vector(settings.nemotron_embed_dim)`. The migration reads `NEMOTRON_EMBED_DIM` from env (default 2048). Add **no ANN index**: pgvector's HNSW limit is 2000 dims, and at this scale an exact scan is fine.
    - `MemoryRead` (table `memory_read`): `span_id` (FK), `memory_item_id` (FK), `reason`, `rank`.
    - `PromptVersion` (table `prompt_version`): `name`, `version`, `body`, `active`, with `unique(name, version)`.
  - **Types:**
    - `Source = Literal["research","gmail_sim","in_app_sim","mock_sim"]`
    - `Scope = Literal["real","mock"]`, where `real` → `{research, gmail_sim, in_app_sim}` and `mock` → `{mock_sim}`
    - `EvidenceLevel = Literal["evidence","signal","assumption"]`
  - `@dataclass NewMemory(kind: Literal["episodic","semantic"], subtype: str, source: Source, summary: str, payload: dict, source_refs: list[dict], evidence_level: EvidenceLevel | None = None)`.
  - `@dataclass MemoryQuery(kind: Literal["episodic","semantic"], subtypes: list[str], scope: Scope, text: str, reason: str, filters: dict = {}, k: int = 5)`. Here `filters` is matched with JSONB containment on `payload` (`payload @> filters`).
  - `@dataclass RetrievedMemory(item: MemoryItem, score: float, rank: int, reason: str)`.
  - `class MemoryStore(sessionmaker, gateway)`, with these methods:
    - `write(mem: NewMemory, ctx) -> UUID`: embeds `summary` with `input_type="passage"` and writes inside `span(kind="memory", name=f"memory.write:{subtype}")`. It raises `ValueError` if `subtype == "insight"` and `evidence_level` is not in `{"evidence","signal"}`, and `ValueError` if `kind == "episodic"` and `subtype == "insight"`.
    - `attach_outcome(item_id: UUID, outcome: dict, ctx) -> None`: sets `outcome` once. Calling it again raises `ValueError`, because episodic memory is append-only.
    - `supersede(old_id: UUID, new_id: UUID, ctx) -> None`.
    - `retrieve(q: MemoryQuery, ctx) -> list[RetrievedMemory]`: filters on `workspace_id = ctx.workspace_id`, kind, `subtype IN`, `source IN scope`, `superseded_by IS NULL`, the payload filters, and (for insights) `evidence_level IN ('evidence','signal')`. It orders by cosine distance to `embed([q.text], input_type="query")`, limits to `k`, and sets `score = 1 - distance` and `rank` from 1.
    - `record_reads(span_id: UUID, retrieved: list[RetrievedMemory]) -> None`.
  - **Prompt registry:**
    - `PROMPTS_DIR = covora/prompts`.
    - `sync_prompts(session) -> None`: for each `*.md` there, if the body differs from the active version, inserts `version + 1`, marks it active, and deactivates the older one.
    - `get_prompt(session, name: str) -> PromptVersion`.
    - `render_prompt(body: str, **values) -> str`: uses `string.Template.substitute`, so it raises `KeyError` on a missing value.

- [ ] **Step 1: Write the failing tests.** Add a `memory` fixture (`MemoryStore(sessionmaker, gateway)`) to `conftest.py`, so embeddings come from `fake_embedding`. Add a `tmp_prompts_dir` fixture that monkeypatches `covora.memory.prompts.PROMPTS_DIR` to `tmp_path`.

```python
async def test_retrieve_ranks_by_similarity(memory, ctx):
    await memory.write(NewMemory("episodic", "outreach_episode", "gmail_sim", "operations manager short email interested", {}, []), ctx)
    await memory.write(NewMemory("episodic", "outreach_episode", "gmail_sim", "finance director long email ignored", {}, []), ctx)
    got = await memory.retrieve(MemoryQuery("episodic", ["outreach_episode"], "real", "operations manager", "similar episodes"), ctx)
    assert got[0].item.summary.startswith("operations manager") and got[0].rank == 1

async def test_scope_isolation(memory, ctx):
    await memory.write(NewMemory("episodic", "outreach_episode", "mock_sim", "ops manager mock", {}, []), ctx)
    got = await memory.retrieve(MemoryQuery("episodic", ["outreach_episode"], "real", "ops manager", "r"), ctx)
    assert got == []

async def test_superseded_excluded(memory, ctx):
    old = await memory.write(NewMemory("semantic", "insight", "mock_sim", "short emails win", {"dimension": "style"}, [], "signal"), ctx)
    new = await memory.write(NewMemory("semantic", "insight", "mock_sim", "short emails win strongly", {"dimension": "style"}, [], "evidence"), ctx)
    await memory.supersede(old, new, ctx)
    got = await memory.retrieve(MemoryQuery("semantic", ["insight"], "mock", "short emails", "r"), ctx)
    assert [g.item.id for g in got] == [new]

async def test_assumption_insight_rejected(memory, ctx):
    with pytest.raises(ValueError):
        await memory.write(NewMemory("semantic", "insight", "research", "maybe X", {}, [], "assumption"), ctx)

async def test_outcome_is_append_only(memory, ctx):
    mid = await memory.write(NewMemory("episodic", "selection_episode", "research", "picked COO", {}, []), ctx)
    await memory.attach_outcome(mid, {"label": "interested"}, ctx)
    with pytest.raises(ValueError):
        await memory.attach_outcome(mid, {"label": "not_interested"}, ctx)

async def test_payload_filters(memory, ctx):
    await memory.write(NewMemory("semantic", "insight", "research", "segment A good", {"dimension": "segment"}, [], "signal"), ctx)
    await memory.write(NewMemory("semantic", "insight", "research", "style B good", {"dimension": "style"}, [], "signal"), ctx)
    got = await memory.retrieve(MemoryQuery("semantic", ["insight"], "real", "good", "r", filters={"dimension": "segment"}), ctx)
    assert [g.item.summary for g in got] == ["segment A good"]

# test_prompts.py
async def test_sync_creates_new_version_on_change(session, tmp_prompts_dir):   # fixture points PROMPTS_DIR at tmp
    (tmp_prompts_dir / "x.md").write_text("v1 $a"); await sync_prompts(session)
    (tmp_prompts_dir / "x.md").write_text("v2 $a"); await sync_prompts(session)
    p = await get_prompt(session, "x")
    assert (p.version, p.body) == (2, "v2 $a")

def test_render_prompt_missing_value_raises():
    with pytest.raises(KeyError):
        render_prompt("hello $name")
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_memory_store.py tests/test_prompts.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement the models, migration `0003_memory`, `store.py`, and `prompts.py`.** For similarity, use pgvector's `cosine_distance` comparator on `MemoryItem.embedding`.

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `uv run pytest tests/test_memory_store.py tests/test_prompts.py -v`. Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/covora/memory backend/migrations/versions backend/tests
git commit -m "feat(memory): add CoALA memory store with scope isolation and prompt registry"
```

---

### Task 8: The decision cycle (`run_step`)

**Files:**
- Create: `backend/covora/agents/__init__.py`, `backend/covora/agents/step.py`
- Test: `backend/tests/test_run_step.py`

**Interfaces:**
- Consumes: `ModelGateway`, `MemoryStore`, `MemoryQuery`, `RetrievedMemory`, `NewMemory`, `span`, `Settings.memory_enabled`.
- Produces:
  - `@dataclass WorkingMemory(agent: str, goal: str, inputs: dict, memories: list[RetrievedMemory], constraints: list[str])`, with:
    - `render_memories() -> str`: one line per memory, grouped under headings `Past experience (episodic)` and `Known facts and insights (semantic)`. Each line is `[mem:<id8>] <summary>`. A semantic insight with `evidence_level == "signal"` gets the suffix ` (tentative)`. If the list is empty, it returns `"(no relevant memories)"`.
    - `manifest() -> list[dict]`: `[{"id", "kind", "subtype", "reason", "rank", "score"}]`.
  - `@dataclass StepResult[T](output: T, working_memory: WorkingMemory, gateway: GatewayResult[T], episode_id: UUID | None, span_id: UUID)`.
  - `run_step(...) -> StepResult[T]`, with these parameters:
    - `ctx: RunContext`, `gateway: ModelGateway`, `memory: MemoryStore`, `settings: Settings`
    - `agent: str`, `task: TaskType`, `goal: str`, `inputs: dict`
    - `queries: list[MemoryQuery]`
    - `build_messages: Callable[[WorkingMemory], list[dict]]`
    - `schema: type[T]`
    - `episode: Callable[[T, WorkingMemory], NewMemory | None] | None = None`
    - `budgets: dict[str, int] = {"episodic": 800, "semantic": 800}`, approximate tokens per memory kind
- **Behavior** (spec §7.1):
  1. Opens `span(kind="agent", name=f"{agent}:{task}")`.
  2. **Observe:** the given `inputs`.
  3. **Retrieve:** only if `settings.memory_enabled(agent)`. Run every query, then trim per kind by budget, keeping the highest score first and counting tokens as `ceil(len(summary) / 4)`.
  4. `record_reads(span.id, kept)`, and set span attributes `working_memory` (the manifest) and `memory_enabled`.
  5. **Reason:** `gateway.complete(task, build_messages(wm), schema=schema, ctx=span.ctx)`.
  6. **Learn:** if `episode` returns a `NewMemory`, write it and return its ID.

- [ ] **Step 1: Write the failing tests.** Add a `step_env` fixture to `conftest.py` that exposes:
  - `.backend`, `.memory`, `.ctx`, `.sessionmaker`;
  - `.kwargs(**overrides)`, which returns run_step's `ctx`, `gateway`, `memory`, and `settings`, plus `goal="test"`, `inputs={}`, merged with the overrides.

  Also add the helper `count_memory_reads(sessionmaker, span_id) -> int`.

```python
async def test_cycle_order_and_manifest(step_env):
    await step_env.memory.write(NewMemory("episodic", "icp_edit", "research", "user widened size to 10-50", {}, []), step_env.ctx)
    step_env.backend.queue(SUPER, '{"value": 1}')
    seen = {}
    def build(wm):
        seen["mem"] = wm.render_memories()
        return [{"role": "user", "content": "go"}]
    r = await run_step(**step_env.kwargs(agent="icp", task=TaskType.icp_parsing,
        queries=[MemoryQuery("episodic", ["icp_edit"], "real", "size", "past ICP corrections")],
        build_messages=build, schema=Answer))
    assert "user widened size" in seen["mem"]
    assert r.working_memory.manifest()[0]["reason"] == "past ICP corrections"
    assert await count_memory_reads(step_env.sessionmaker, r.span_id) == 1

async def test_run_step_with_no_memories(step_env):
    step_env.backend.queue(SUPER, '{"value": 1}')
    r = await run_step(**step_env.kwargs(agent="icp", task=TaskType.icp_parsing,
        queries=[MemoryQuery("semantic", ["insight"], "real", "x", "insights")],
        build_messages=lambda wm: [{"role": "user", "content": wm.render_memories()}], schema=Answer))
    assert r.output.value == 1 and r.working_memory.memories == []
    assert "(no relevant memories)" in step_env.backend.calls[0]["messages"][0]["content"]

async def test_memory_disabled_skips_retrieval(step_env, monkeypatch):
    monkeypatch.setenv("MEMORY_ENABLED_ICP", "false")
    await step_env.memory.write(NewMemory("episodic", "icp_edit", "research", "something", {}, []), step_env.ctx)
    step_env.backend.queue(SUPER, '{"value": 1}')
    r = await run_step(**step_env.kwargs(agent="icp", task=TaskType.icp_parsing,
        queries=[MemoryQuery("episodic", ["icp_edit"], "real", "something", "r")],
        build_messages=lambda wm: [{"role": "user", "content": "go"}], schema=Answer))
    assert r.working_memory.memories == []

async def test_budget_trims_lowest_scores(step_env):
    for i in range(10):
        await step_env.memory.write(NewMemory("episodic", "icp_edit", "research", f"edit number {i} " + "x" * 400, {}, []), step_env.ctx)
    step_env.backend.queue(SUPER, '{"value": 1}')
    r = await run_step(**step_env.kwargs(agent="icp", task=TaskType.icp_parsing,
        queries=[MemoryQuery("episodic", ["icp_edit"], "real", "edit", "r", k=10)],
        build_messages=lambda wm: [{"role": "user", "content": "go"}], schema=Answer, budgets={"episodic": 250, "semantic": 0}))
    assert len(r.working_memory.memories) == 2

async def test_episode_written(step_env):
    step_env.backend.queue(SUPER, '{"value": 7}')
    r = await run_step(**step_env.kwargs(agent="icp", task=TaskType.icp_parsing, queries=[],
        build_messages=lambda wm: [{"role": "user", "content": "go"}], schema=Answer,
        episode=lambda out, wm: NewMemory("episodic", "selection_episode", "research", f"chose {out.value}", {}, [])))
    assert r.episode_id is not None
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_run_step.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement `WorkingMemory`, `StepResult`, and `run_step` in `agents/step.py`.**

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `uv run pytest tests/test_run_step.py -v`. Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/covora/agents backend/tests/test_run_step.py
git commit -m "feat(agents): add CoALA decision cycle run_step with working memory budgets"
```

---

### Task 9: ICP schemas, ICP planning agent, and ICP versions

**Files:**
- Create: `backend/covora/icp/schemas.py`, `models.py`, `agent.py`, `service.py`, `backend/covora/prompts/icp_parsing.md`
- Create: `backend/migrations/versions/0004_icp.py`
- Test: `backend/tests/test_icp_schemas.py`, `backend/tests/test_icp_agent.py`, `backend/tests/test_icp_service.py`

**Interfaces:**
- Consumes: `run_step`, `MemoryStore`, `MemoryQuery`, `NewMemory`, `get_prompt`, `render_prompt`, `Workspace`.
- Produces:
  - **Schemas** (spec §9.1):
    - `Origin = Literal["stated","inferred"]`
    - `Tagged[T](BaseModel, Generic[T])`: `value: T`, `origin: Origin`
    - `Range`: `min: int | None`, `max: int | None`. The validator raises `ValueError("min must be ≤ max")` when both are set and `min > max`.
    - `Location`: `country: str`, `regions: list[str] = []`
    - `SizeBand`: `employees: Range`, `primary_titles: list[str]`, `secondary_titles: list[str]`, `origin: Origin`
    - `BuyerMap`: `target_functions: list[Tagged[str]]`, `by_company_size: list[SizeBand]`, `skip_titles: list[Tagged[str]]`
    - `StructuredICP`:
      - `summary: str`
      - `industries: list[Tagged[str]]`, `locations: list[Tagged[Location]]`
      - `employee_range: Tagged[Range] | None`, `revenue_range_usd: Tagged[Range] | None`
      - `other_criteria: list[Tagged[str]]`, `exclusions: list[Tagged[str]]`
      - `buyer_map: BuyerMap`
      - `assumptions: list[str]`, `search_queries: list[str]`
  - `IcpVersion` (table `icp_version`): `workspace_id`, `version: int` (`unique(workspace_id, version)`), `prompt_text`, `structured` (JSONB), `parent_id: UUID | None`, `created_by` (`user|agent`).
  - `parse_icp(prompt_text: str, *, ctx, gateway, memory, settings, session) -> StepResult[StructuredICP]`, implemented with `run_step`:
    - `agent="icp"`, `task=TaskType.icp_parsing`
    - `goal="Turn the user's description of ideal customers into a structured ICP with a buyer map"`
    - `inputs={"prompt_text", "company_profile"}`, where the company profile is name, description, value props, and offering type from `Workspace`.
    - Queries:
      - `MemoryQuery("episodic", ["icp_edit"], "real", prompt_text, "past ICP corrections by the user", k=5)`
      - `MemoryQuery("semantic", ["insight"], "real", prompt_text, "segment insights", filters={"dimension": "segment"}, k=3)`
    - Messages: system = `render_prompt(icp_parsing.body, company_profile=..., memories=wm.render_memories())`; user = `prompt_text`.
  - `@dataclass FieldChange(path: str, before: Any, after: Any)`.
  - `diff_icp(draft: StructuredICP, final: StructuredICP) -> list[FieldChange]`: compares at the path level, e.g. `employee_range`, `industries`, `buyer_map.target_functions`.
  - `save_icp_version(session, *, workspace_id, prompt_text, structured: StructuredICP, draft: StructuredICP | None, parent_id: UUID | None, created_by: Literal["user","agent"], memory: MemoryStore, ctx) -> IcpVersion`. It:
    - assigns the next version number;
    - forces `origin="stated"` on every `Tagged` value the user changed relative to `draft`;
    - writes an episodic `icp_edit` memory when the diff is non-empty. The summary is built in code (e.g. `"User changed employee_range 5–25 → 10–50; removed industries 'retail'"`), with `payload={"changes": [...]}`, `source="research"`, and `source_refs=[{"table": "icp_version", "id": <new id>}]`.
- **`icp_parsing.md` content requirements** (wording is the builder's):
  - Placeholders `$company_profile` and `$memories`.
  - Instructs the model to:
    - mark every value `stated` only when the user's words say it, and `inferred` otherwise;
    - never invent numbers the user didn't give, and list any interpretation in `assumptions`;
    - produce a size-dependent buyer map;
    - produce 5–10 search queries;
    - honor past user corrections shown in memories.

- [ ] **Step 1: Write the failing tests**

```python
# test_icp_schemas.py
def test_range_min_greater_than_max_rejected():
    with pytest.raises(ValidationError):
        Range(min=100, max=25)

def test_vague_icp_is_valid():
    icp = StructuredICP.model_validate(VAGUE_ICP_JSON)   # empty industries/locations, ranges None, assumptions non-empty
    assert icp.industries == [] and icp.employee_range is None and icp.assumptions

# test_icp_agent.py
async def test_parse_icp_uses_profile_and_returns_structured(icp_env):   # workspace with profile + fake backend
    icp_env.backend.queue(SUPER, json.dumps(EXAMPLE_ICP))                  # spec §9.1 example
    r = await parse_icp("Find US manufacturers with 5–25 employees", **icp_env.kwargs())
    assert r.output.employee_range.value.max == 25 and r.output.employee_range.origin == "stated"
    system = icp_env.backend.calls[0]["messages"][0]["content"]
    assert "Acme Robotics" in system and "(no relevant memories)" in system

async def test_parse_icp_sees_past_corrections(icp_env):
    await icp_env.memory.write(NewMemory("episodic", "icp_edit", "research", "User changed employee_range 5–25 → 10–50", {}, []), icp_env.ctx)
    icp_env.backend.queue(SUPER, json.dumps(EXAMPLE_ICP))
    r = await parse_icp("Find US manufacturers", **icp_env.kwargs())
    assert "10–50" in icp_env.backend.calls[0]["messages"][0]["content"]
    assert r.working_memory.manifest()[0]["subtype"] == "icp_edit"

# test_icp_service.py
async def test_edit_marks_stated_and_writes_episode(icp_env, session):
    draft = StructuredICP.model_validate(EXAMPLE_ICP_WITH_INFERRED_SIZE)
    final = draft.model_copy(deep=True); final.employee_range.value = Range(min=10, max=50)
    v = await save_icp_version(session, workspace_id=icp_env.ws.id, prompt_text="p", structured=final, draft=draft,
                               parent_id=None, created_by="user", memory=icp_env.memory, ctx=icp_env.ctx)
    assert v.version == 1 and v.structured["employee_range"]["origin"] == "stated"
    mems = await icp_env.memory.retrieve(MemoryQuery("episodic", ["icp_edit"], "real", "employee_range", "r"), icp_env.ctx)
    assert "10–50" in mems[0].item.summary

async def test_no_episode_when_unchanged(icp_env, session):
    draft = StructuredICP.model_validate(EXAMPLE_ICP)
    await save_icp_version(session, workspace_id=icp_env.ws.id, prompt_text="p", structured=draft, draft=draft,
                           parent_id=None, created_by="user", memory=icp_env.memory, ctx=icp_env.ctx)
    assert await icp_env.memory.retrieve(MemoryQuery("episodic", ["icp_edit"], "real", "x", "r"), icp_env.ctx) == []

async def test_versions_increment(icp_env, session):
    a = await save_icp_version(session, **icp_env.save_kwargs())
    b = await save_icp_version(session, **icp_env.save_kwargs(parent_id=a.id))
    assert (a.version, b.version, b.parent_id) == (1, 2, a.id)
```

  Put `EXAMPLE_ICP`, `EXAMPLE_ICP_WITH_INFERRED_SIZE`, and `VAGUE_ICP_JSON` in `tests/fixtures_icp.py`. `EXAMPLE_ICP` is the spec §9.1 example with `search_queries` filled in.

  Add an `icp_env` fixture to `conftest.py` that exposes:
  - `.ws` (the workspace, with profile name "Acme Robotics"), `.backend`, `.memory`, `.ctx`;
  - `.kwargs()`: parse_icp's keyword arguments;
  - `.save_kwargs(**overrides)`: `save_icp_version` defaults (`prompt_text="p"`, `structured=EXAMPLE_ICP`, `draft=None`, `parent_id=None`, `created_by="user"`).

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_icp_schemas.py tests/test_icp_agent.py tests/test_icp_service.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement the schemas, model, migration `0004_icp`, agent, service, and prompt file.**

- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/covora/icp backend/covora/prompts backend/migrations/versions backend/tests
git commit -m "feat(icp): add ICP planning agent, versions, and correction memory"
```

---

### Task 10: API app: errors, health, workspace

**Files:**
- Create: `backend/covora/api/__init__.py`, `app.py`, `deps.py`, `errors.py`, `routes/__init__.py`, `routes/health.py`, `routes/workspace.py`
- Test: `backend/tests/test_api_core.py`

**Interfaces:**
- Consumes: `Settings`, `make_engine`, `make_sessionmaker`, `ModelGateway`, `NvidiaBackend`, `MemoryStore`, `sync_prompts`, `ensure_workspace`, `update_profile`, `WorkspaceProfile`, `GatewayError`, `redact`.
- Produces:
  - `create_app(settings: Settings | None = None, *, backend: ChatBackend | None = None) -> FastAPI` and a module-level `app = create_app()`.
    - Lifespan: build the engine and sessionmaker, `sync_prompts`, `ensure_workspace`, then store a `Services` object on `app.state`.
    - CORS allows `settings.cors_origin`.
    - Every route is under `/api`.
  - `@dataclass Services(settings, sessionmaker, gateway: ModelGateway, memory: MemoryStore)`. Dependencies: `get_services(request) -> Services` and `get_session(...) -> AsyncIterator[AsyncSession]`.
  - `class ApiError(Exception)(code: str, message: str, status: int = 400, details: dict | None = None)`.
  - **Handlers:**
    - `ApiError` → its own code and status.
    - `RequestValidationError` → 422 `validation_error`, with `details.errors`.
    - `GatewayError` → 502 `model_unavailable`, message `"The AI models are unavailable right now. Please try again."`
    - Any other exception → 500 `internal_error`, message `"Something went wrong."`. The redacted exception text is logged server-side only.
  - `GET /api/health` → `{"status": "ok" | "degraded", "checks": {"database": bool, "nvidia_key": bool, "youcom_key": bool}}`. The status is `degraded` if any check is false.
  - `GET /api/workspace` → `WorkspaceOut`: `id` plus the `WorkspaceProfile` fields.
  - `PUT /api/workspace` with a `WorkspaceProfile` body → `WorkspaceOut`.

- [ ] **Step 1: Write the failing tests.** Use an `api` fixture: `httpx.AsyncClient(transport=ASGITransport(app=create_app(settings, backend=fake_backend)))` inside `LifespanManager`; add `asgi-lifespan` to the dev group.

```python
async def test_health_reports_checks(api):
    r = await api.get("/api/health")
    assert r.status_code == 200 and r.json()["checks"]["database"] is True and r.json()["checks"]["nvidia_key"] is True

async def test_workspace_roundtrip(api):
    body = {"name": "Acme Robotics", "website": None, "description": "Cobots", "value_props": [], "offering_type": "dealer"}
    assert (await api.put("/api/workspace", json=body)).status_code == 200
    assert (await api.get("/api/workspace")).json()["offering_type"] == "dealer"

async def test_validation_error_shape(api):
    r = await api.put("/api/workspace", json={"name": "x", "offering_type": "b2c"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_api_core.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement the app, dependencies, error handlers, and both routers.**

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `uv run pytest tests/test_api_core.py -v`. Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/covora/api backend/tests/test_api_core.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(api): add app factory, error shape, health and workspace routes"
```

---

### Task 11: API: ICP and runs routes

**Files:**
- Create: `backend/covora/api/routes/icp.py`, `backend/covora/api/routes/runs.py`
- Modify: `backend/covora/api/app.py` (include the routers)
- Test: `backend/tests/test_api_icp_runs.py`

**Interfaces:**
- Consumes: `parse_icp`, `save_icp_version`, `IcpVersion`, `StructuredICP`, `start_run`, `finish_run`, `WorkflowRun`, `Span`, `LlmCall`, `MemoryRead`, `MemoryItem`.
- Produces:
  - **`POST /api/icp/parse`**, body `{"prompt_text": str}` (1–4000 characters).
    - Wraps `parse_icp` in a `workflow_run` with `kind="icp"`, finishing it `succeeded` or `failed`.
    - Returns `{"draft": StructuredICP, "run_id": UUID, "working_memory": [manifest...]}`.
    - On `GatewayError`, the run is finished `failed` and the error handler returns 502.
  - **`POST /api/icps`**, body `{"prompt_text", "structured": StructuredICP, "draft": StructuredICP | null, "parent_id": UUID | null}`.
    - Calls `save_icp_version(created_by="user")` inside a `workflow_run` with `kind="icp"`.
    - Returns `IcpVersionOut {id, version, prompt_text, structured, parent_id, created_by, created_at}`.
  - **`GET /api/icps`** → `IcpVersionOut[]`, newest first. **`GET /api/icps/{id}`** → `IcpVersionOut`, or 404 `not_found`.
  - **`GET /api/runs?kind=&limit=50`** → a list of `RunSummary {id, kind, status, started_at, ended_at, duration_ms, error, llm_calls, prompt_tokens, completion_tokens, est_cost_usd}`, newest first.
  - **`GET /api/runs/{id}`** → `RunDetail {run: RunSummary, spans: SpanOut[], llm_calls: LlmCallOut[]}`.
    - `SpanOut` is `{id, parent_span_id, name, kind, status, started_at, duration_ms, attributes, error}`.
    - `LlmCallOut` is every `llm_call` column except `request_payload`. `response_text` is included only when `log_llm_payloads` is set.
  - **`GET /api/runs/{id}/spans/{span_id}/memory`** → `WorkingMemoryItem[] {memory_item_id, kind, subtype, source, summary, evidence_level, reason, rank}`, ordered by rank.

- [ ] **Step 1: Write the failing tests**

```python
async def test_parse_then_save_then_list(api, fake_backend):
    fake_backend.queue(SUPER, json.dumps(EXAMPLE_ICP))
    parsed = (await api.post("/api/icp/parse", json={"prompt_text": "US manufacturers 5–25 employees"})).json()
    saved = (await api.post("/api/icps", json={"prompt_text": "US manufacturers 5–25 employees",
             "structured": parsed["draft"], "draft": parsed["draft"], "parent_id": None})).json()
    assert saved["version"] == 1
    assert (await api.get("/api/icps")).json()[0]["id"] == saved["id"]

async def test_parse_returns_502_when_models_unavailable(api, fake_backend):
    for m in (SUPER, NANO):
        fake_backend.queue(m, *[BackendError("503", status=503, retryable=True)] * 4)
    r = await api.post("/api/icp/parse", json={"prompt_text": "anything"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "model_unavailable"
    runs = (await api.get("/api/runs?kind=icp")).json()
    assert runs[0]["status"] == "failed"

async def test_run_detail_has_spans_llm_calls_and_memory(api, fake_backend):
    fake_backend.queue(SUPER, json.dumps(EXAMPLE_ICP))
    run_id = (await api.post("/api/icp/parse", json={"prompt_text": "x"})).json()["run_id"]
    d = (await api.get(f"/api/runs/{run_id}")).json()
    assert {s["kind"] for s in d["spans"]} >= {"agent", "llm"}
    call = d["llm_calls"][0]
    assert call["routing_reason"] == "fixed: icp_parsing → super" and "request_payload" not in call
    agent_span = next(s for s in d["spans"] if s["kind"] == "agent")
    assert (await api.get(f"/api/runs/{run_id}/spans/{agent_span['id']}/memory")).status_code == 200

async def test_unknown_icp_404(api):
    r = await api.get(f"/api/icps/{uuid4()}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_api_icp_runs.py -v`. Expected: FAIL.

- [ ] **Step 3: Implement both routers and include them in `create_app`.**

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `uv run pytest tests/test_api_icp_runs.py -v`. Expected: 4 passed.

- [ ] **Step 5: Run the whole backend suite.** Run: `uv run pytest -v`. Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/covora/api backend/tests/test_api_icp_runs.py
git commit -m "feat(api): add ICP parse/save/list and run inspection routes"
```

---

### Task 12: Frontend shell, sidebar, API client

**Files:**
- Create: the `frontend/` project via `npm create vite@latest frontend -- --template react-ts`, then add the files below.
- Create: `frontend/src/styles.css`, `src/api/client.ts`, `src/api/types.ts`, `src/components/Layout.tsx`, `src/components/Sidebar.tsx`, `src/components/EmptyState.tsx`, and `src/pages/{Overview,IcpStudio,Prospects,Campaigns,Inbox,AgentWorkflow,RunDetail,Settings}.tsx` (placeholders)
- Create: `frontend/src/test/setup.ts`
- Modify: `frontend/vite.config.ts`, `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/package.json`
- Test: `frontend/src/components/Sidebar.test.tsx`, `frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: the API error shape and the backend schemas from Tasks 10–11.
- Produces:
  - **Routes:** `/` Overview, `/icp` ICP Studio, `/prospects`, `/campaigns`, `/inbox`, `/workflow` Agent Workflow, `/workflow/runs/:runId` RunDetail, `/settings`. All are rendered inside `<Layout>`, which has the sidebar on the left and content on the right.
  - `<Sidebar>`: the seven labels from Global Constraints, in order, as `NavLink`s with an active style.
  - `<EmptyState title: string, body?: string, action?: ReactNode>`.
  - **API client:**
    - `class ApiError extends Error { code: string; details: unknown; status: number }`.
    - `apiFetch<T>(path: string, init?: RequestInit) -> Promise<T>`: prefixes `/api`, sends and expects JSON, and throws `ApiError` with the parsed error shape on any non-2xx response. A non-JSON error body becomes code `network_error`.
  - `src/api/types.ts`: TS types mirroring `WorkspaceOut`, `StructuredICP` (with `Tagged<T>`), `IcpVersionOut`, `RunSummary`, `RunDetail`, `SpanOut`, `LlmCallOut`, and `WorkingMemoryItem`.
  - **Config:**
    - Vite dev server `port: 5180`, `strictPort: true`, with proxy `/api` → `http://localhost:8000`.
    - Tailwind v4 via `@tailwindcss/vite`, with `@import "tailwindcss"` in `styles.css`.
    - TanStack Query `QueryClientProvider` in `main.tsx`.
    - Vitest with environment `jsdom` and setup file `src/test/setup.ts` (jest-dom).
    - npm scripts `test` → `vitest run` and `typecheck` → `tsc -b --noEmit`.
  - **Visual baseline:**
    - Body `bg-white text-slate-900`.
    - Sidebar `w-60 border-r border-slate-200 bg-white` with the "Covora" wordmark on top.
    - Content `max-w-6xl px-8 py-8`.
    - Accent color `indigo-600`, used sparingly.
    - Placeholder pages render their title plus `<EmptyState title="Nothing here yet" body="This page arrives in a later plan." />`.

- [ ] **Step 1: Create the project and add dependencies.** Run:
  `npm create vite@latest frontend -- --template react-ts && cd frontend && npm install && npm install react-router-dom@6 @tanstack/react-query@5 && npm install -D tailwindcss @tailwindcss/vite vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event`

- [ ] **Step 2: Write the failing tests**

```tsx
// Sidebar.test.tsx
it("shows the seven sections in order", () => {
  render(<MemoryRouter><Sidebar /></MemoryRouter>);
  expect(screen.getAllByRole("link").map((a) => a.textContent)).toEqual(
    ["Overview", "ICP Studio", "Prospects", "Campaigns", "Inbox", "Agent Workflow", "Settings"]);
});
it("marks the current section active", () => {
  render(<MemoryRouter initialEntries={["/icp"]}><Sidebar /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "ICP Studio" })).toHaveAttribute("aria-current", "page");
});

// client.test.ts
it("throws ApiError with the server's code", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
    JSON.stringify({ error: { code: "model_unavailable", message: "down", details: {} } }), { status: 502 })));
  await expect(apiFetch("/icp/parse", { method: "POST" })).rejects.toMatchObject({ code: "model_unavailable", status: 502 });
});
```

- [ ] **Step 3: Run the tests and confirm they fail.** Run: `npm test`. Expected: FAIL.

- [ ] **Step 4: Implement the layout, sidebar, routes, client, types, and config** as described above.

- [ ] **Step 5: Run the tests and the typecheck, and confirm they pass.** Run: `npm test && npm run typecheck`. Expected: 3 passed; no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(web): add React shell with sidebar, routes, and API client"
```

---

### Task 13: Settings: company profile

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`
- Create: `frontend/src/features/settings/CompanyProfileForm.tsx`
- Test: `frontend/src/features/settings/CompanyProfileForm.test.tsx`

**Interfaces:**
- Consumes: `GET` and `PUT /api/workspace`, `apiFetch`, `WorkspaceOut`.
- Produces: `<CompanyProfileForm>`, with:
  - fields: Company name, Website, What you sell (description textarea), Proof points (one per line → `value_props`), and Offering type (radio: "Needs a sales call" = `sales_call`, "Bulk product for dealers" = `dealer`);
  - a **Save** button that calls `PUT` and shows "Saved" on success, or the API error message.

  The Settings page renders this form under the heading "Company".

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows empty profile form", async () => {
  mockFetch({ "GET /api/workspace": { id: "w", name: "My company", website: null, description: null, value_props: [], offering_type: "sales_call" } });
  renderWithQuery(<CompanyProfileForm />);
  expect(await screen.findByLabelText("Company name")).toHaveValue("My company");
  expect(screen.getByLabelText("What you sell")).toHaveValue("");
});
it("saves proof points one per line", async () => {
  const calls = mockFetch({ "GET /api/workspace": WS, "PUT /api/workspace": WS });
  renderWithQuery(<CompanyProfileForm />);
  await userEvent.type(await screen.findByLabelText("Proof points"), "Fast payback{enter}Made in USA");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(calls.body("PUT /api/workspace").value_props).toEqual(["Fast payback", "Made in USA"]);
  expect(await screen.findByText("Saved")).toBeInTheDocument();
});
```

  Add two test helpers to `src/test/utils.tsx`:
  - `mockFetch(routes)` maps `"METHOD /path"` keys to either a JSON body (status 200) or `{status, body}`. It returns `calls`, where `calls.body(key)` gives the last parsed request body.
  - `renderWithQuery(ui, {route?, path?})` wraps the UI in a fresh `QueryClientProvider` and a `MemoryRouter` (with `initialEntries=[route]`). When `path` is given, it also wraps the UI in `<Routes><Route path={path} element={ui}/></Routes>`.

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `npm test -- CompanyProfileForm`. Expected: FAIL.

- [ ] **Step 3: Implement the form** with TanStack Query (`useQuery` + `useMutation`).

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `npm test -- CompanyProfileForm`. Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(web): add company profile settings"
```

---

### Task 14: ICP Studio

**Files:**
- Modify: `frontend/src/pages/IcpStudio.tsx`
- Create: `frontend/src/features/icp/IcpEditor.tsx`, `TaggedList.tsx`, `OriginBadge.tsx`, `VersionHistory.tsx`
- Test: `frontend/src/features/icp/IcpStudio.test.tsx`

**Interfaces:**
- Consumes: `POST /api/icp/parse`, `POST /api/icps`, `GET /api/icps`, `StructuredICP`, `IcpVersionOut`.
- Produces:
  - **`<IcpStudio>`** page, laid out as:
    - a "Describe your ideal customers" textarea and an **Interpret** button (shows "Interpreting…" while pending);
    - on success, `<IcpEditor value={draft} onChange>` plus a **Save version** button;
    - a right-hand `<VersionHistory>` listing `v<n> · <date> · <summary>`. Clicking an entry loads it into the editor as the new parent.
    - **Errors:** for `model_unavailable`, an inline alert with the API message and a **Try again** button.
  - **`<IcpEditor>`** has sections: Summary; Industries; Locations; Company size (employees min/max); Revenue (USD min/max); Other criteria; Exclusions; Buyer map (target functions, size bands with primary and secondary titles, skip titles); Assumptions (read-only list); Search queries (read-only list).
    - Every `Tagged` value shows an `<OriginBadge origin>`: "You said" (slate) for `stated`, "Inferred" (amber, with an amber left border on the row) for `inferred`.
    - Editing a value sets its origin to `stated` in local state.
    - Empty lists render "None yet" with an **Add** control.
  - **Save** posts `{prompt_text, structured, draft, parent_id}`, then refreshes the version history and shows "Saved as v<n>".

- [ ] **Step 1: Write the failing tests**

```tsx
it("interprets a prompt and highlights inferred fields", async () => {
  mockFetch({ "GET /api/icps": [], "POST /api/icp/parse": { draft: EXAMPLE_ICP_WITH_INFERRED_SIZE, run_id: "r1", working_memory: [] } });
  renderWithQuery(<IcpStudio />);
  await userEvent.type(screen.getByLabelText("Describe your ideal customers"), "US manufacturers");
  await userEvent.click(screen.getByRole("button", { name: "Interpret" }));
  expect(await screen.findAllByText("Inferred")).not.toHaveLength(0);
});
it("editing a field marks it as stated and saves", async () => {
  const calls = mockFetch({ "GET /api/icps": [], "POST /api/icp/parse": PARSED, "POST /api/icps": { ...VERSION, version: 1 } });
  renderWithQuery(<IcpStudio />);
  await interpret("US manufacturers");                            // helper: type + click Interpret
  const max = screen.getByLabelText("Employees max");
  await userEvent.clear(max); await userEvent.type(max, "50");
  await userEvent.click(screen.getByRole("button", { name: "Save version" }));
  expect(calls.body("POST /api/icps").structured.employee_range).toEqual({ value: { min: 5, max: 50 }, origin: "stated" });
  expect(await screen.findByText("Saved as v1")).toBeInTheDocument();
});
it("renders empty sections as editable", async () => {
  mockFetch({ "GET /api/icps": [], "POST /api/icp/parse": { draft: VAGUE_ICP, run_id: "r", working_memory: [] } });
  renderWithQuery(<IcpStudio />);
  await interpret("find some companies");
  expect(screen.getAllByText("None yet").length).toBeGreaterThan(0);
  expect(screen.getAllByRole("button", { name: "Add" }).length).toBeGreaterThan(0);
});
it("shows model-unavailable error", async () => {
  mockFetch({ "GET /api/icps": [], "POST /api/icp/parse": { status: 502, body: { error: { code: "model_unavailable", message: "The AI models are unavailable right now. Please try again.", details: {} } } } });
  renderWithQuery(<IcpStudio />);
  await interpret("x");
  expect(await screen.findByRole("alert")).toHaveTextContent("unavailable");
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});
```

  Copy the ICP fixtures from the backend as TS constants in `src/test/fixtures.ts`.

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `npm test -- IcpStudio`. Expected: FAIL.

- [ ] **Step 3: Implement the page and its components** as described above.

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `npm test -- IcpStudio`. Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(web): add ICP Studio with origin badges and version history"
```

---

### Task 15: Agent Workflow: runs list and run detail

**Files:**
- Modify: `frontend/src/pages/AgentWorkflow.tsx`, `frontend/src/pages/RunDetail.tsx`
- Create: `frontend/src/features/runs/SpanTree.tsx`, `LlmCallCard.tsx`, `WorkingMemoryPanel.tsx`
- Test: `frontend/src/features/runs/runs.test.tsx`

**Interfaces:**
- Consumes: `GET /api/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/spans/{span_id}/memory`, `RunSummary`, `RunDetail`, `SpanOut`, `LlmCallOut`, `WorkingMemoryItem`.
- Produces:
  - **`<AgentWorkflow>`:** a table of runs with columns Kind, Status (badge), Started, Duration, Model calls, Tokens, Est. cost. Each row links to `/workflow/runs/:id`.
    - Empty state: "No agent runs yet", body "Interpret an ICP in ICP Studio to see your first run."
    - Refetches every 3 s while any run is `running`.
  - **`<RunDetail>`:** a header (kind, status, duration, error if any) and `<SpanTree spans>`.
  - **`<SpanTree>`:** spans indented by parent, each showing name, kind badge, duration, and an error badge with the error text when present.
    - Selecting an `llm` span shows its `<LlmCallCard>`.
    - Selecting an `agent` span shows its `<WorkingMemoryPanel>`.
  - **`<LlmCallCard call>`:** Task, Routing mode, Requested model, Actual model, Routing reason, Fallback (`Yes — <reason>` or `No`), Tokens in/out, Latency, Est. cost (`$0.0000` or `—` when null), and Retries.
  - **`<WorkingMemoryPanel runId spanId>`:** fetches the memory endpoint and lists `rank · kind/subtype · summary · reason`, with an evidence badge for insights. When the list is empty: "This step had no relevant memories."

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows empty runs state", async () => {
  mockFetch({ "GET /api/runs": [] });
  renderWithQuery(<AgentWorkflow />, { route: "/workflow" });
  expect(await screen.findByText("No agent runs yet")).toBeInTheDocument();
});
it("nests spans and shows the routing decision", async () => {
  mockFetch({ "GET /api/runs/r1": RUN_DETAIL, "GET /api/runs/r1/spans/s-agent/memory": [] });   // agent span → llm span
  renderWithQuery(<RunDetail />, { route: "/workflow/runs/r1", path: "/workflow/runs/:runId" });
  await userEvent.click(await screen.findByText("llm:icp_parsing"));
  expect(screen.getByText("fixed: icp_parsing → super")).toBeInTheDocument();
  expect(screen.getByText("nvidia/nemotron-3-super-120b-a12b")).toBeInTheDocument();
});
it("shows working memory for an agent step", async () => {
  mockFetch({ "GET /api/runs/r1": RUN_DETAIL, "GET /api/runs/r1/spans/s-agent/memory": [
    { memory_item_id: "m1", kind: "episodic", subtype: "icp_edit", source: "research", summary: "User changed employee_range 5–25 → 10–50", evidence_level: null, reason: "past ICP corrections by the user", rank: 1 }] });
  renderWithQuery(<RunDetail />, { route: "/workflow/runs/r1", path: "/workflow/runs/:runId" });
  await userEvent.click(await screen.findByText("icp:icp_parsing"));
  expect(await screen.findByText(/10–50/)).toBeInTheDocument();
});
it("shows a failed span's error", async () => {
  mockFetch({ "GET /api/runs/r2": FAILED_RUN_DETAIL });
  renderWithQuery(<RunDetail />, { route: "/workflow/runs/r2", path: "/workflow/runs/:runId" });
  expect(await screen.findByText(/503/)).toBeInTheDocument();
});
```

  Add two fixtures to `src/test/fixtures.ts`:
  - `RUN_DETAIL`: an ICP run whose agent span `s-agent`, named `icp:icp_parsing`, has a child llm span `s-llm`, named `llm:icp_parsing`. Its one `llm_call` has the fixed routing reason and the Super model.
  - `FAILED_RUN_DETAIL`: a failed run with one llm span whose `error` is `"503 Service Unavailable"`.

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `npm test -- runs`. Expected: FAIL.

- [ ] **Step 3: Implement the pages and components** as described above.

- [ ] **Step 4: Run the tests and confirm they pass.** Run: `npm test -- runs`. Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(web): add Agent Workflow runs list, span tree, routing and memory panels"
```

---

### Task 16: End-to-end verification and docs

**Files:**
- Modify: `README.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`

- [ ] **Step 1: Run every automated check.** Run: `cd backend && uv run ruff check . && uv run pytest -v && cd ../frontend && npm test && npm run typecheck`. Expected: all pass, and no ruff errors.

- [ ] **Step 2: Run a live end-to-end check.** This needs `NVIDIA_API_KEY` in `.env`.
  1. Run `docker compose up -d db`, `cd backend && uv run alembic upgrade head && uv run uvicorn covora.api.app:app --port 8000`, and in another shell `cd frontend && npm run dev`.
  2. In the browser at `http://localhost:5180`:
     - In Settings, save a company profile.
     - In ICP Studio, interpret the spec's example prompt (*"Find manufacturing companies in the US with 5–25 employees and $5M–$20M in annual revenue. Target people responsible for operations or business partnerships."*).
     - Edit one inferred field and save.
     - Interpret the same prompt again.
  3. Expected:
     - The first interpretation shows "You said" on the size and revenue ranges.
     - Agent Workflow lists the runs.
     - The second run's agent span shows a working-memory item with the earlier `icp_edit`.
     - Its LLM call card shows `nvidia/nemotron-3-super-120b-a12b`, the routing reason, tokens, and latency.
     - No reasoning text appears anywhere.

- [ ] **Step 3: Update the docs**
  - **`docs/PROGRESS.md`:** Plan 1 done; a list of what works; known gaps (Switchyard deferred to Plan 6; worker and LangGraph arrive in Plan 2).
  - **`docs/DECISIONS.md`:** add the structured-output mode and embedding dimension confirmed in Task 6, the ports (5433, 5180), and the choice of an exact vector scan (no ANN index).
  - **`README.md`:** confirm the setup steps match what was actually run.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/PROGRESS.md docs/DECISIONS.md
git commit -m "docs: record Plan 1 progress and decisions"
```
