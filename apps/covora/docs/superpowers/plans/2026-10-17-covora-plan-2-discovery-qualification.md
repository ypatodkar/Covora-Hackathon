# Covora Plan 2 — Discovery & Qualification: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** From a saved ICP, the user launches a campaign sized from their goal. A background worker then runs a LangGraph pipeline that finds real companies with You.com, gathers facts with sources, scores each company's fit, finds named people, and picks a primary contact and a backup per company. The Prospects page shows every company and person with reasons, evidence labels, and source links, and exports both as CSV.

**Architecture:**
- **Worker:** a separate process (`python -m covora.worker`) claims jobs from a Postgres `job` table.
- **Campaign graph:** the `campaign.run` job runs a LangGraph `StateGraph`: `discover_companies ⇄ score_companies → find_people → select_contacts`. Discovery and scoring repeat in waves until there are enough qualified companies. The graph is checkpointed with `AsyncPostgresSaver` in its own `langgraph` schema, so a failed run resumes where it stopped.
- **Agents:** every model step goes through Plan 1's `run_step`. The step's inputs are sent as a JSON user message.
- **Research:** every web call goes through a `ResearchProvider`. `YouComProvider` adds caching, a budget guard, retries, and a `tool_call` trace row; `MockProvider` serves a fixture web for tests.
- **Guardrails in code:** only companies that appear in results, only people named in sources, only emails found verbatim, and only quoted numbers.

**Tech Stack:** adds `langgraph==1.2.16` and `langgraph-checkpoint-postgres==3.2.0` to Plan 1's stack.

**Spec:** `docs/superpowers/specs/2026-10-17-covora-design.md`. Read §5.2 (campaign sizing), §5.3 (Prospects), §8.1 (campaign pipeline), §9 (discovery and qualification), §16.1 (`tool_call`), §18, and §19.

**Builds on:** Plan 1 (`docs/superpowers/plans/2026-10-17-covora-plan-1-foundation-icp-studio.md`). Its ledger rulings stand:
- Postgres runs on host port **5434**.
- Spans are written on enter.
- Memory failures degrade gracefully (the step continues without memories).
- Test helpers live in `tests/helpers.py`.

## Global Constraints

- **Everything from Plan 1's Global Constraints still applies**, with the Postgres port at 5434.
- **All web research goes through `ResearchProvider`.** Nothing else calls You.com.
- **You.com:**
  - Base URL `https://ydc-index.io/v1`, auth header `X-API-Key`.
  - `POST /search` with body `{"query", "count"}`; results come back in `results.web[]` (`url`, `title`, `description`, `snippets`, `page_age`).
  - `POST /contents` with body `{"urls", "formats": ["markdown"]}`; returns an array of `{url, title, markdown}`.
- **Prices (config):** `YOUCOM_SEARCH_PRICE_USD=0.005` per search and `YOUCOM_CONTENTS_PRICE_USD=0.001` per page.
- **Budget cap:** `YOUCOM_BUDGET_USD` (default 80). A call that would exceed the cap is refused before it is made. A failed call is refunded.
- **Cache:** You.com responses are cached for 14 days. Cache hits cost $0 and are still traced.
- **Never invent data:**
  - **Companies:** created only from search results, keyed by normalized domain.
  - **People:** only if their name appears verbatim in a cited source.
  - **Emails:** only if found verbatim in a source. No pattern guessing.
  - **Numeric facts** (`employee_count`, `revenue_usd`): kept only with a verbatim quote from the cited page.
- **Agent message format:** each `run_step` call sends a system message (the rendered prompt) and one user message: `json.dumps(inputs)` of that step's inputs. This is also how test fakes read the inputs.
- **Model-output schemas** clean free-text values with `covora.text.clean_strings` in a `mode="before"` validator, because Plan 1's live check found stray leading punctuation from structured decoding. The exceptions are `quote`, `source_url`, `linkedin_url`, `email`, and `domain`, which must stay verbatim.
- **Live model facts from Plan 1:**
  - The light tier is `nemotron-3.5-lightning-30b-a3b`.
  - Structured output uses `response_format`.
  - Reasoning is off by default.
  - A Super call takes about 14 s.
  - Concurrency limits: Nano 8, Super 4.
- **Campaign jobs are not auto-retried** (`max_attempts=1`). Retrying is the user's explicit action and resumes from the checkpoint.
- **Campaign statuses:** `draft → queued → running → complete | failed`. Plan 3 adds `awaiting_approval`.
- **CSV exports** escape any cell that starts with `=`, `+`, `-`, `@`, tab, or carriage return by prefixing `'`.
- **Live updates** use polling (TanStack Query `refetchInterval`). The spec's SSE is deferred to Plan 6.

## Review Focus

1. **Web text that begins with `=`, `+`, `-`, or `@`** (company names, quotes, titles) ends up in CSV exports, where it would run as a formula when opened in a spreadsheet. Every such cell must be escaped. Pinned in Task 13: `test_csv_cells_are_formula_escaped`.
2. **You.com failures and budget exhaustion mid-campaign** (429, 5xx, timeouts, missing key, cap reached). Retries happen, failed calls are refunded, and the campaign completes with partial results and a clear `stop_reason` instead of crashing. Pinned in Task 5 `test_retry_then_refund_on_failure` and `test_budget_refused_before_call`, and Task 12 `test_budget_exhaustion_completes_with_partial_results`.
3. **The model returns companies, people, or emails that aren't in the sources.** Validators drop them. Pinned in Task 8 `test_unlisted_company_dropped`, and Task 10 `test_person_not_in_source_dropped` and `test_email_not_in_source_not_recorded`.
4. **Messy domains:** `www.`, uppercase, ports, paths, and directory subdomains like `uk.linkedin.com`. These are normalized, deduped, or blocked. Pinned in Task 7: `test_normalize_and_block_domains`.
5. **A late pipeline step fails, or the worker dies mid-campaign.** Retry resumes from the checkpoint without re-running (and re-paying for) discovery. Pinned in Task 12: `test_retry_resumes_without_rediscovery`.

---

## File Structure

```
backend/
  covora/
    services.py                    # Services + build_services (shared by API and worker)  [moved from api/deps]
    workspace/settings.py          # Goals, SendingSettings, WorkspaceSettings
    jobs/models.py  jobs/queue.py  # Job table; enqueue/claim_next/complete/fail
    worker.py                      # Worker + `python -m covora.worker`
    research/models.py             # ToolCall, SearchCache
    research/provider.py           # SearchResult, PageContent, ResearchProvider, ResearchError, BudgetExceeded
    research/budget.py             # charge/refund/remaining against workspace.youcom_spend_usd
    research/cache.py              # cache_key, get_cached, put_cached
    research/tooltrace.py          # record_tool_call
    research/youcom.py             # YouComProvider
    research/mock.py               # MockProvider (fixture web)
    campaigns/models.py            # Campaign
    campaigns/sizing.py            # CostModel, SizingEstimate, estimate_campaign, measured_cost_model
    campaigns/service.py           # create_campaign, campaign_funnel, latest_run_id
    discovery/domains.py           # normalize_domain, is_blocked
    discovery/criteria.py          # Criterion, icp_criteria, fit_score
    discovery/models.py            # Company, CampaignCompany, Fact
    discovery/schemas.py           # QueryPlan, ExtractedCompanies, ExtractedFacts, FitJudgment
    discovery/validate.py          # validate_companies, validate_facts
    discovery/discover.py          # discover_wave
    discovery/enrich.py            # enrich_and_score
    qualification/models.py        # Contact, Prospect
    qualification/schemas.py       # ExtractedPeople, ContactSelection
    qualification/validate.py      # validate_people, classify_email, validate_selection
    qualification/people.py        # find_people
    qualification/select.py        # select_contacts
    graphs/checkpointer.py         # checkpointer_url, open_checkpointer
    graphs/campaign.py             # CampaignState, build_campaign_graph, route_after_scoring
    graphs/jobs.py                 # run_campaign_job (job handler)
    prompts/{query_generation,company_extraction,fact_extraction,company_fit,people_extraction,contact_selection}.md
    api/routes/settings.py  api/routes/campaigns.py  api/routes/prospects.py  api/routes/exports.py
  migrations/versions/0005_jobs.py  0006_research.py  0007_campaigns.py  0008_discovery.py  0009_qualification.py  0010_langgraph_schema.py
  scripts/smoke_youcom.py
  tests/data/mock_web.json         # fixture web: 6 companies, team pages, a directory page, LinkedIn-style profiles
  tests/fakes.py                   # + ScriptedBackend
frontend/src/
  features/settings/GoalsForm.tsx
  features/campaigns/{LaunchCampaignDialog,Funnel}.tsx
  pages/{Campaigns,CampaignDetail,Prospects}.tsx
  features/prospects/{CompaniesTable,PeopleTable,CompanyDrawer,ContactDrawer,EvidenceBadge}.tsx
```

---

### Task 1: Shared services and workspace settings (goals and sending)

**Files:**
- Create: `backend/covora/services.py`, `backend/covora/workspace/settings.py`, `backend/covora/api/routes/settings.py`
- Modify: `backend/covora/api/deps.py` (re-export `Services`, `get_services`, `get_session`), `backend/covora/api/app.py` (use `build_services`), `backend/covora/config.py`
- Test: `backend/tests/test_workspace_settings.py`

**Interfaces:**
- Produces:
  - **`covora/services.py`:**
    - `@dataclass Services(settings, sessionmaker, gateway: ModelGateway, memory: MemoryStore, research: ResearchProvider | None = None)`. `research` is filled in by Task 5.
    - `build_services(settings, *, backend: ChatBackend | None = None, research: ResearchProvider | None = None) -> tuple[Services, AsyncEngine]`.
  - **`covora/workspace/settings.py`:**
    - `Goals(goal_type: Literal["positive_replies","meetings"]="positive_replies", target: int=10 (ge=1), expected_positive_rate: float=0.01 (gt=0, le=1), meetings_per_positive: float=0.5 (gt=0, le=1))`
    - `SendingSettings(daily_gmail_cap: int=100 (ge=1), first_batch_size: int=10 (ge=1), no_reply_window_minutes: int=10 (ge=1))`
    - `WorkspaceSettings(goals: Goals=Goals(), sending: SendingSettings=SendingSettings())`
    - `get_workspace_settings(ws: Workspace) -> WorkspaceSettings`: validates `ws.settings`, filling in defaults.
    - `update_workspace_settings(session, ws, value: WorkspaceSettings) -> WorkspaceSettings`
  - **Routes:** `GET /api/workspace/settings` → `WorkspaceSettings`; `PUT /api/workspace/settings` → `WorkspaceSettings`.
  - **New `Settings` fields:**
    - `research_provider: Literal["youcom","mock"]="youcom"`
    - `mock_web_path: str | None = None`
    - `youcom_base_url="https://ydc-index.io/v1"`
    - `youcom_search_price_usd=0.005`, `youcom_contents_price_usd=0.001`
    - `youcom_cache_ttl_days=14`, `youcom_timeout_s=30.0`
    - `research_blocklist_domains: list[str]` (default list in Task 7)
    - `min_fit_score=60`, `max_candidates_per_wave=40`, `max_waves=15`, `contact_yield_buffer=1.25`
    - `worker_poll_interval_s=1.0`, `job_stale_after_s=300`
  - Add the new variables to `.env.example`, with `RESEARCH_PROVIDER` explained ("mock" = fixture web for development, labeled synthetic).

- [ ] **Step 1: Write the failing tests**

```python
def test_defaults_match_owner_example():
    s = WorkspaceSettings()
    assert (s.goals.goal_type, s.goals.target, s.goals.expected_positive_rate) == ("positive_replies", 10, 0.01)

async def test_settings_roundtrip(api):
    body = {"goals": {"goal_type": "meetings", "target": 5, "expected_positive_rate": 0.02, "meetings_per_positive": 0.5},
            "sending": {"daily_gmail_cap": 50, "first_batch_size": 10, "no_reply_window_minutes": 10}}
    assert (await api.put("/api/workspace/settings", json=body)).status_code == 200
    assert (await api.get("/api/workspace/settings")).json()["goals"]["goal_type"] == "meetings"

async def test_invalid_rate_rejected(api):
    r = await api.put("/api/workspace/settings", json={"goals": {"expected_positive_rate": 0}})
    assert r.status_code == 422
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `cd backend && uv run pytest tests/test_workspace_settings.py -v`. Expected: FAIL (import error).
- [ ] **Step 3: Implement the services module, settings, and routes.** Move `Services` into `covora/services.py`; `create_app` calls `build_services` in its lifespan. Existing API tests must keep passing.
- [ ] **Step 4: Run the tests and confirm they pass.** Run: `uv run pytest tests/test_workspace_settings.py tests/test_api_core.py tests/test_api_icp_runs.py -v`. Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "feat(settings): add workspace goals/sending settings and shared services"`

---

### Task 2: Job queue

**Files:**
- Create: `backend/covora/jobs/__init__.py`, `backend/covora/jobs/models.py`, `backend/covora/jobs/queue.py`, `backend/migrations/versions/0005_jobs.py`
- Test: `backend/tests/test_job_queue.py`

**Interfaces:**
- Produces:
  - `Job` (table `job`): `kind: str`, `payload: dict` (JSONB), `status` (`queued|running|done|failed`), `attempts: int=0`, `max_attempts: int=3`, `run_after: datetime`, `locked_at`, `locked_by`, `last_error`.
  - `enqueue(session, kind: str, payload: dict, *, run_after: datetime | None = None, max_attempts: int = 3) -> Job` (commits).
  - `claim_next(sessionmaker, worker_id: str, *, stale_after_s: float = 300) -> Job | None`:
    - A single `UPDATE … WHERE id = (SELECT id … FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *`.
    - Claimable jobs: `queued` with `run_after <= now()`, or `running` with `locked_at < now() - stale_after_s`.
    - Claiming sets `running`, `locked_at`, `locked_by`, and `attempts += 1`.
  - `complete(sessionmaker, job_id) -> None`.
  - `fail(sessionmaker, job_id, error: str, *, base_delay_s: float = 5.0) -> Job`:
    - If `attempts < max_attempts`: back to `queued` with `run_after = now + base_delay_s × 2^(attempts-1)`.
    - Otherwise: `failed`.
    - `last_error` is stored redacted.

- [ ] **Step 1: Write the failing tests**

```python
async def test_concurrent_claims_get_different_jobs(session, sessionmaker):
    await enqueue(session, "x", {"n": 1}); await enqueue(session, "x", {"n": 2})
    a, b = await asyncio.gather(claim_next(sessionmaker, "w1"), claim_next(sessionmaker, "w2"))
    assert {a.payload["n"], b.payload["n"]} == {1, 2}

async def test_fail_requeues_with_backoff_then_fails(session, sessionmaker):
    job = await enqueue(session, "x", {}, max_attempts=2)
    await claim_next(sessionmaker, "w"); j = await fail(sessionmaker, job.id, "boom", base_delay_s=0)
    assert j.status == "queued" and j.attempts == 1
    await claim_next(sessionmaker, "w"); j = await fail(sessionmaker, job.id, "boom again", base_delay_s=0)
    assert j.status == "failed" and j.last_error == "boom again"

async def test_future_jobs_not_claimed(session, sessionmaker):
    await enqueue(session, "x", {}, run_after=datetime.now(UTC) + timedelta(hours=1))
    assert await claim_next(sessionmaker, "w") is None

async def test_stale_running_job_reclaimed(session, sessionmaker):
    job = await enqueue(session, "x", {})
    await claim_next(sessionmaker, "w1")
    await set_locked_at(sessionmaker, job.id, datetime.now(UTC) - timedelta(minutes=10))   # helper in tests/helpers.py
    again = await claim_next(sessionmaker, "w2", stale_after_s=300)
    assert again.id == job.id and again.locked_by == "w2"
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_job_queue.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the model, migration, and queue functions.** Register `covora.jobs.models` in `migrations/env.py`.
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 4 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(jobs): add Postgres job queue with skip-locked claims and backoff"`

---

### Task 3: Worker process

**Files:**
- Create: `backend/covora/worker.py`
- Test: `backend/tests/test_worker.py`

**Interfaces:**
- Consumes: `claim_next`, `complete`, `fail`, `Services`, `build_services`.
- Produces:
  - `Handler = Callable[[Job, Services], Awaitable[None]]`.
  - `class Worker(services: Services, handlers: Mapping[str, Handler], *, worker_id: str | None = None, poll_interval_s: float = 1.0)`, with:
    - `run_once() -> bool`: claim one job and run its handler. On success, `complete`. On an exception, `fail` with the redacted `f"{type}: {msg}"`. A job with an unknown kind fails with `"no handler for job kind '<kind>'"`. Returns `True` if a job was processed.
    - `run_forever(stop: asyncio.Event | None = None) -> None`: loops `run_once`, sleeping `poll_interval_s` when idle.
  - `HANDLERS: dict[str, Handler]` registry, filled by Task 12.
  - `main()`: `python -m covora.worker` builds services and runs until SIGINT/SIGTERM. It prints `worker <id> started` and logs each job's kind, id, and outcome.

- [ ] **Step 1: Write the failing tests**

```python
async def test_runs_handler_and_completes(services, session):
    seen = []
    async def handler(job, svc): seen.append(job.payload["n"])
    await enqueue(session, "demo", {"n": 7})
    assert await Worker(services, {"demo": handler}).run_once() is True
    assert seen == [7] and (await get_job(services.sessionmaker, kind="demo")).status == "done"

async def test_handler_error_fails_job_redacted(services, session):
    async def handler(job, svc): raise RuntimeError("bad nvapi-SECRET1234567 call")
    await enqueue(session, "demo", {}, max_attempts=1)
    await Worker(services, {"demo": handler}).run_once()
    job = await get_job(services.sessionmaker, kind="demo")
    assert job.status == "failed" and "nvapi-SECRET1234567" not in job.last_error

async def test_unknown_kind_fails(services, session):
    await enqueue(session, "nope", {}, max_attempts=1)
    await Worker(services, {}).run_once()
    assert "no handler" in (await get_job(services.sessionmaker, kind="nope")).last_error

async def test_idle_returns_false(services):
    assert await Worker(services, {}).run_once() is False
```

  Add a `services` fixture to `conftest.py` (a `Services` built from the test settings, `fake_backend`, and `research=None`) and a `get_job` helper to `tests/helpers.py`.
- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_worker.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `Worker` and `main()`.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 4 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(worker): add job worker loop and entrypoint"`

---

### Task 4: Research core: types, tool-call tracing, cache, budget, mock provider

**Files:**
- Create: `backend/covora/research/{__init__,models,provider,budget,cache,tooltrace,mock}.py`, `backend/migrations/versions/0006_research.py`, `backend/tests/data/mock_web.json`
- Modify: `backend/covora/workspace/models.py` (add `youcom_spend_usd: float = 0`)
- Test: `backend/tests/test_research_core.py`

**Interfaces:**
- Produces:
  - **Tables:**
    - `ToolCall` (table `tool_call`, spec §16.1): `span_id` (FK span), `provider` (`youcom|mock`), `operation` (`search|contents`), `request_summary`, `result_count`, `cache_hit`, `status` (`ok|error|refused`), `latency_ms`, `est_cost_usd`.
    - `SearchCache` (table `search_cache`): `key` (PK, sha256 hex), `endpoint`, `params` (JSONB), `response` (JSONB), `created_at`.
  - **`provider.py`:**
    - `@dataclass SearchResult(url: str, title: str, description: str, snippets: list[str], page_age: str | None = None)`
    - `@dataclass PageContent(url: str, title: str, markdown: str)`
    - `class ResearchError(Exception)` and `class BudgetExceeded(ResearchError)`
    - `class ResearchProvider(Protocol)`, with `search(query: str, *, count: int, ctx: RunContext) -> list[SearchResult]`, `contents(urls: list[str], *, ctx: RunContext) -> list[PageContent]`, and attribute `name: str`
  - **`cache.py`:**
    - `cache_key(endpoint: str, params: dict) -> str` (sha256 of `endpoint` + canonical JSON)
    - `get_cached(sessionmaker, key, *, ttl_days) -> dict | None`
    - `put_cached(sessionmaker, key, endpoint, params, response) -> None` (upsert)
  - **`budget.py`:**
    - `charge(sessionmaker, workspace_id, cost: float, *, cap: float) -> float`: one atomic `UPDATE workspace SET youcom_spend_usd = youcom_spend_usd + :cost WHERE id = :id AND youcom_spend_usd + :cost <= :cap RETURNING youcom_spend_usd`. It raises `BudgetExceeded(f"You.com budget of ${cap:.2f} reached")` when no row is updated, and otherwise returns the new spend.
    - `refund(sessionmaker, workspace_id, cost) -> None`
    - `spend(sessionmaker, workspace_id) -> float`
  - **`tooltrace.py`:** `record_tool_call(ctx, *, span_id, provider, operation, request_summary, result_count, cache_hit, status, latency_ms, est_cost_usd) -> None`
  - **`MockProvider(pages: list[MockPage])`** with `name = "mock"`, and `MockProvider.from_file(path)`. `MockPage` has `{url, title, description, markdown}`.
    - `search`: ranks pages by how many lowercase word tokens they share with the query (title + description + markdown), keeps those with at least one shared token, and returns the top `count`. Each result's snippets are up to 2 sentences from the markdown that contain query tokens.
    - `contents`: returns pages whose URL matches exactly; unknown URLs are skipped.
    - Both open `span(kind="tool")` and record a `tool_call` with provider `mock` and cost 0.
  - **`tests/data/mock_web.json`:** one page list on `.test` domains (never real). It contains:
    - Homepage, about, and team pages for:
      - **Ohio Precision Fabrication** (`ohio-precision.test`): metal fabrication, Dayton, Ohio, "18 employees". Team: "Dana Ruiz — Operations Manager" (`dana.ruiz@ohio-precision.test`), "Mark Ellison — Owner & President", and `info@ohio-precision.test`.
      - **Lakeside Plastics** (`lakeside-plastics.test`): Michigan, "22 employees". Team: "Priya Shah — COO".
      - **Granite Foods Co** (`granite-foods.test`): food manufacturing, "about 40 employees". Team: "Tom Becker — Plant Manager".
      - **BrightPath Software** (`brightpath.test`): a software company, "15 employees". Team: "Ana Lima — CEO".
      - **Midwest Valve Works** (`midwest-valve.test`): Indiana, "12 employees", no team page.
      - **Copperline Machining** (`copperline.test`): Texas, "9 employees". Team: "Luis Ortega — Head of Partnerships".
    - A directory page on `https://www.thomasnet.com/ohio-manufacturers` that mentions Ohio Precision and its domain.
    - A LinkedIn-style profile at `https://www.linkedin.com/in/dana-ruiz-ops`, titled "Dana Ruiz - Operations Manager - Ohio Precision Fabrication | LinkedIn".

- [ ] **Step 1: Write the failing tests**

```python
async def test_charge_is_atomic_and_capped(sessionmaker, workspace):
    assert await charge(sessionmaker, workspace.id, 0.5, cap=1.0) == pytest.approx(0.5)
    with pytest.raises(BudgetExceeded):
        await charge(sessionmaker, workspace.id, 0.6, cap=1.0)
    await refund(sessionmaker, workspace.id, 0.5)
    assert await spend(sessionmaker, workspace.id) == pytest.approx(0.0)

async def test_cache_roundtrip_and_ttl(sessionmaker):
    key = cache_key("search", {"query": "a", "count": 5})
    await put_cached(sessionmaker, key, "search", {"query": "a"}, {"ok": 1})
    assert await get_cached(sessionmaker, key, ttl_days=14) == {"ok": 1}
    assert await get_cached(sessionmaker, key, ttl_days=0) is None

async def test_mock_search_ranks_and_traces(mock_research, ctx, sessionmaker):
    results = await mock_research.search("metal fabrication Ohio", count=3, ctx=ctx)
    assert results[0].url.startswith("https://ohio-precision.test")
    assert (await latest_tool_call(sessionmaker)).provider == "mock"     # helper in tests/helpers.py

async def test_mock_contents_skips_unknown(mock_research, ctx):
    pages = await mock_research.contents(["https://ohio-precision.test/team", "https://nope.test/"], ctx=ctx)
    assert [p.url for p in pages] == ["https://ohio-precision.test/team"]
```

  Add a `mock_research` fixture to `conftest.py`: `MockProvider.from_file(tests/data/mock_web.json)`.
- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_research_core.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the research core.**
  - Migration `0006_research` creates `tool_call`, `search_cache`, and the `workspace.youcom_spend_usd` column (`Float`, default 0, not null).
  - Register `covora.research.models` in `env.py`.
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 4 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(research): add provider types, cache, budget guard, tool tracing, mock web"`

---

### Task 5: You.com provider and live smoke check

**Files:**
- Create: `backend/covora/research/youcom.py`, `backend/scripts/smoke_youcom.py`
- Modify: `backend/covora/services.py` (`build_services` picks `YouComProvider` or `MockProvider` from `settings.research_provider`)
- Test: `backend/tests/test_youcom.py`

**Interfaces:**
- Consumes: Task 4's whole research core, plus `span` and `Settings`.
- Produces: `YouComProvider(settings, sessionmaker, http_client: httpx.AsyncClient | None = None)` with `name = "youcom"`.
  - **Search flow:**
    1. Check the cache (`cache_key("search", {"query", "count"})`). On a hit, return it and trace with `cache_hit=True` and cost 0.
    2. Otherwise `charge(price)`, then `POST {base}/search` with JSON `{"query", "count"}` and the `X-API-Key` header.
    3. Retry on 429, ≥500, timeouts, and connection errors: 3 times, waiting `retry_base_delay_s × 1, 2, 4`.
    4. On final failure, `refund` and raise `ResearchError`.
    5. On success: parse `results.web[]` (missing `snippets` → `[]`), store it in the cache, and trace it.
  - **Contents flow:**
    1. Each URL is cached on its own.
    2. Only uncached URLs are fetched, in one `POST {base}/contents` with `{"urls": [...], "formats": ["markdown"]}`.
    3. Charge `price × uncached count` up front.
    4. Response items missing `markdown` are skipped.
  - **Missing key:** raise `ResearchError("YDC_API_KEY is not set")` without making a call or charging.
  - **Budget warning:** once spend is ≥ 80% of the cap, span attribute `budget_warning=True`.
  - **Tracing:** every call runs inside `span(ctx, f"youcom.{operation}", "tool", {"query" | "urls": ...})` and records a `tool_call`. `request_summary` is the query text, or the URL list joined by spaces.
- `scripts/smoke_youcom.py` does one search, `"metal fabrication companies Dayton Ohio"` with count 5, and one contents call on the first result. It prints:
  - `OK search n=<k>`
  - `OK contents chars=<n>`
  - `site-operator: honored|ignored`: the result of searching `site:linkedin.com/in operations manager manufacturing Ohio`, checking whether every result URL is on linkedin.com.
  - total spend.

  It exits non-zero on failure. Estimated cost: about $0.016.

- [ ] **Step 1: Write the failing tests.** Use an `httpx.MockTransport` that counts calls.

```python
async def test_search_parses_and_caches(youcom_with, ctx, sessionmaker):
    provider, calls = youcom_with(lambda req: httpx.Response(200, json=SEARCH_OK))   # fixture returns (provider, call list)
    first = await provider.search("metal fab", count=5, ctx=ctx)
    second = await provider.search("metal fab", count=5, ctx=ctx)
    assert first[0].url == "https://ohio-precision.test/" and second == first and len(calls) == 1
    assert (await latest_tool_call(sessionmaker)).cache_hit is True

async def test_retry_then_refund_on_failure(youcom_with, ctx, sessionmaker, workspace):
    provider, calls = youcom_with(lambda req: httpx.Response(503))
    with pytest.raises(ResearchError):
        await provider.search("x", count=5, ctx=ctx)
    assert len(calls) == 4 and await spend(sessionmaker, workspace.id) == 0

async def test_budget_refused_before_call(youcom_with, ctx, settings):
    provider, calls = youcom_with(lambda req: httpx.Response(200, json=SEARCH_OK), budget_usd=0.001)
    with pytest.raises(BudgetExceeded):
        await provider.search("x", count=5, ctx=ctx)
    assert calls == []

async def test_contents_fetches_only_uncached(youcom_with, ctx):
    provider, calls = youcom_with(lambda req: httpx.Response(200, json=[{"url": u, "title": "t", "markdown": "m"} for u in json.loads(req.content)["urls"]]))
    await provider.contents(["https://a.test/"], ctx=ctx)
    await provider.contents(["https://a.test/", "https://b.test/"], ctx=ctx)
    assert json.loads(calls[1].content)["urls"] == ["https://b.test/"]

async def test_missing_key_raises_without_call(settings, sessionmaker, ctx):
    provider = YouComProvider(settings.model_copy(update={"ydc_api_key": None}), sessionmaker)
    with pytest.raises(ResearchError, match="YDC_API_KEY"):
        await provider.search("x", count=5, ctx=ctx)
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_youcom.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `YouComProvider`, the smoke script, and provider selection in `build_services`.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 5 passed.
- [ ] **Step 5: Run the live smoke check.** This needs `YDC_API_KEY`; without it, defer and ledger, as in Plan 1 Task 6.
  - Run: `uv run python scripts/smoke_youcom.py`. Expected: `OK search`, `OK contents`, and a `site-operator:` line.
  - Record the `site-operator` result in `docs/DECISIONS.md`. Task 10's people queries use `site:linkedin.com/in` only if it's honored.
- [ ] **Step 6: Commit.** `git commit -m "feat(research): add You.com provider with cache, budget, retries, and smoke check"`

---

### Task 6: Campaigns and sizing

**Files:**
- Create: `backend/covora/campaigns/{__init__,models,sizing,service}.py`, `backend/covora/api/routes/campaigns.py` (estimate/create/list/get only in this task), `backend/migrations/versions/0007_campaigns.py`
- Test: `backend/tests/test_sizing.py`, `backend/tests/test_campaigns_api.py`

**Interfaces:**
- Consumes: `Goals`, `get_workspace_settings`, `IcpVersion`, `spend`, `ToolCall`, `LlmCall`, `Span`, `WorkflowRun`.
- Produces:
  - **`Campaign` (table `campaign`):**
    - Identity and lineage: `workspace_id`, `name`, `icp_version_id` (FK), `version: int=1`, `root_campaign_id: UUID | None`, `parent_campaign_id: UUID | None`, `experiment_id: UUID | None`.
    - Snapshots: `config_snapshot` (JSONB: `{"icp": <structured>, "icp_version": n}`), `goal` (JSONB, a `Goals` dump).
    - Sizing: `target_prospects: int`.
    - Progress: `status` (`draft|queued|running|complete|failed`), `progress` (JSONB: `{"used_queries": [], "waves": 0, "stop_reason": null}`), `last_error`.
  - **`@dataclass(frozen=True) CostModel`:** `searches_per_prospect: float = 8.0`, `pages_per_prospect: float = 4.0`, `model_calls_per_prospect: float = 6.0`, `source: Literal["default","measured"] = "default"`.
  - **`@dataclass SizingEstimate`:** `rate_used`, `prospects_needed`, `prospects_planned`, `companies_needed`, `est_searches`, `est_pages`, `est_youcom_usd`, `est_model_calls`, `gmail_emails`, `in_app_emails`, `budget_remaining_usd`, `fits_budget`, `max_affordable_prospects`, `cost_model_source`.
  - **`estimate_campaign(goals: Goals, *, prospect_limit: int | None, cost: CostModel, search_price: float, page_price: float, budget_remaining: float, daily_gmail_cap: int) -> SizingEstimate`:**
    - `rate_used` is `expected_positive_rate` for a replies goal, or `expected_positive_rate × meetings_per_positive` for a meetings goal.
    - `prospects_needed = ⌈target ÷ rate_used⌉`.
    - `prospects_planned = min(prospects_needed, prospect_limit)` when a limit is set.
    - `companies_needed = prospects_planned` (one primary per company).
    - `est_searches = ⌈planned × searches_per_prospect⌉`; `est_pages` likewise.
    - `est_youcom_usd = searches × search_price + pages × page_price`, rounded to cents.
    - `est_model_calls = ⌈planned × model_calls_per_prospect⌉`.
    - `gmail_emails = min(planned, daily_gmail_cap)` and `in_app_emails = planned − gmail_emails`.
    - `max_affordable_prospects = ⌊budget_remaining ÷ per-prospect cost⌋`.
    - `fits_budget = est_youcom_usd ≤ budget_remaining`.
  - **`measured_cost_model(session, workspace_id) -> CostModel | None`:** across `complete` campaigns, non-cache `tool_call` searches, contents pages, and `llm_call`s, each divided by primary prospects (joined via `span → workflow_run.campaign_id`). Returns `None` when there are no complete campaigns or no prospects. Plan 2 creates no prospects until Task 11, so test it there.
  - **`create_campaign(session, *, workspace_id, icp_version_id, name, goals, prospect_limit) -> Campaign`:** status `draft`, `target_prospects = estimate.prospects_planned`.
  - **`campaign_funnel(session, campaign_id) -> dict`:** keys `candidates`, `qualified`, `rejected`, `with_contacts`, `prospects`, `no_contact`. All are 0 until Tasks 8–11 add rows; the counts query those tables when they exist.
  - **`latest_run_id(session, campaign_id) -> UUID | None`.**
  - **Routes:**
    - `POST /api/campaigns/estimate`, body `{goal_type, target, expected_positive_rate, meetings_per_positive, prospect_limit?}` → `SizingEstimate`.
    - `POST /api/campaigns`, body `{icp_version_id, name, goals, prospect_limit?}` → `CampaignOut`.
    - `GET /api/campaigns` → `CampaignOut[]`.
    - `GET /api/campaigns/{id}` → `CampaignOut`.
    - `CampaignOut` is `{id, name, status, icp_version_id, goal, target_prospects, progress, last_error, created_at, funnel, latest_run_id}`.

- [ ] **Step 1: Write the failing tests**

```python
def _est(**goal):
    return estimate_campaign(Goals(**goal), prospect_limit=None, cost=CostModel(), search_price=0.005,
                             page_price=0.001, budget_remaining=80.0, daily_gmail_cap=100)

def test_owner_example_ten_replies_at_one_percent():
    e = _est(goal_type="positive_replies", target=10, expected_positive_rate=0.01)
    assert (e.prospects_needed, e.est_searches, e.est_pages, e.est_youcom_usd) == (1000, 8000, 4000, 44.0)
    assert (e.gmail_emails, e.in_app_emails, e.fits_budget, e.max_affordable_prospects) == (100, 900, True, 1818)

def test_meetings_goal_uses_meeting_rate():
    assert _est(goal_type="meetings", target=10, expected_positive_rate=0.01, meetings_per_positive=0.5).prospects_needed == 2000

def test_prospect_limit_caps_plan():
    e = estimate_campaign(Goals(), prospect_limit=20, cost=CostModel(), search_price=0.005, page_price=0.001,
                          budget_remaining=80.0, daily_gmail_cap=100)
    assert (e.prospects_planned, e.est_youcom_usd) == (20, 0.88)

def test_over_budget_flagged():
    e = estimate_campaign(Goals(target=50), prospect_limit=None, cost=CostModel(), search_price=0.005,
                          page_price=0.001, budget_remaining=80.0, daily_gmail_cap=100)
    assert e.fits_budget is False

# test_campaigns_api.py
async def test_estimate_and_create(api, saved_icp):          # fixture: a saved IcpVersion id via the API
    est = (await api.post("/api/campaigns/estimate", json={"goal_type": "positive_replies", "target": 10,
            "expected_positive_rate": 0.01, "meetings_per_positive": 0.5, "prospect_limit": 20})).json()
    assert est["prospects_planned"] == 20
    c = (await api.post("/api/campaigns", json={"icp_version_id": saved_icp, "name": "Ohio fab",
         "goals": {"goal_type": "positive_replies", "target": 10, "expected_positive_rate": 0.01,
                   "meetings_per_positive": 0.5}, "prospect_limit": 20})).json()
    assert c["status"] == "draft" and c["target_prospects"] == 20 and c["funnel"]["prospects"] == 0
    assert (await api.get("/api/campaigns")).json()[0]["id"] == c["id"]

async def test_create_with_unknown_icp_404(api):
    r = await api.post("/api/campaigns", json={"icp_version_id": str(uuid4()), "name": "x", "goals": {}})
    assert r.status_code == 404
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_sizing.py tests/test_campaigns_api.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the model, migration `0007`, sizing, service, and routes.** For the estimate route, budget remaining is `youcom_budget_usd − spend`, and the cost model is `measured_cost_model(...) or CostModel()`.
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 6 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(campaigns): add campaign model, goal-based sizing, and campaign API"`

---

### Task 7: Domains, ICP criteria, and the fit score (pure code)

**Files:**
- Create: `backend/covora/discovery/{__init__,domains,criteria}.py`
- Modify: `backend/covora/config.py` (default `research_blocklist_domains`)
- Test: `backend/tests/test_domains_criteria.py`

**Interfaces:**
- Consumes: `StructuredICP`.
- Produces:
  - `normalize_domain(value: str) -> str | None`: accepts a URL or a bare domain. Returns the lowercase hostname with `www.` stripped and any port removed. Returns `None` when there's no dot or for IP addresses.
  - `is_blocked(domain: str, blocklist: Sequence[str]) -> bool`: true when the domain equals a blocklisted domain or ends with `"." + blocked`.
  - **Default blocklist:** `linkedin.com facebook.com instagram.com x.com twitter.com youtube.com wikipedia.org yelp.com bbb.org indeed.com glassdoor.com zoominfo.com crunchbase.com dnb.com bloomberg.com manta.com yellowpages.com thomasnet.com google.com amazon.com reddit.com`.
  - `@dataclass(frozen=True) Criterion(name: str, description: str, hard: bool, stated: bool, kind: Literal["include","exclude"])`.
  - `icp_criteria(icp: StructuredICP) -> list[Criterion]`, in this order:
    1. `industry` (hard), if there are industries
    2. `location` (hard), if there are locations
    3. `employee_range` (soft), if set
    4. `revenue_range` (soft), if set
    5. `other:<i>` (soft), one per other criterion
    6. `exclusion:<i>` (kind `exclude`), one per exclusion

    `stated` comes from the tagged origin. For a list, it's true if any item was stated.
  - `fit_score(criteria: list[Criterion], statuses: Mapping[str, Literal["met","not_met","unknown"]]) -> int`:
    - Each include criterion has weight 2 if hard, 1 if soft, and score 1 for met, 0.5 for unknown, 0 for not_met.
    - `score = round(100 × Σ w·s ÷ Σ w)`.
    - Any hard `not_met` caps the score at 20. Any stated soft `not_met` caps it at 50.
    - Any exclusion with status `met` (the excluded condition applies) gives 0.
    - A criterion missing from `statuses` counts as unknown. With no include criteria, the score is 50.
  - Qualified means `score ≥ settings.min_fit_score` (60).

- [ ] **Step 1: Write the failing tests**

```python
def test_normalize_and_block_domains():
    assert normalize_domain("https://WWW.Ohio-Precision.test:443/about?x=1") == "ohio-precision.test"
    assert normalize_domain("ohio-precision.test") == "ohio-precision.test"
    assert normalize_domain("localhost") is None and normalize_domain("http://10.0.0.1/") is None
    assert is_blocked("uk.linkedin.com", ["linkedin.com"]) and not is_blocked("notlinkedin.com", ["linkedin.com"])

def test_criteria_from_example_icp():
    names = [c.name for c in icp_criteria(StructuredICP.model_validate(EXAMPLE_ICP))]
    assert names == ["industry", "location", "employee_range", "revenue_range"]

def test_fit_score_rules():
    cs = icp_criteria(StructuredICP.model_validate(EXAMPLE_ICP))
    assert fit_score(cs, {"industry": "met", "location": "met"}) == 83          # employee/revenue unknown
    assert fit_score(cs, {"industry": "not_met", "location": "met", "employee_range": "met", "revenue_range": "met"}) == 20
    assert fit_score(cs, {"industry": "met", "location": "met", "employee_range": "not_met", "revenue_range": "met"}) == 50
    assert fit_score(cs, {k: "met" for k in ["industry", "location", "employee_range", "revenue_range"]}) == 100

def test_exclusion_met_zeroes_score():
    icp = StructuredICP.model_validate({**EXAMPLE_ICP, "exclusions": [{"value": "government contractors", "origin": "stated"}]})
    cs = icp_criteria(icp)
    assert fit_score(cs, {"industry": "met", "location": "met", "exclusion:0": "met"}) == 0
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_domains_criteria.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `domains.py` and `criteria.py`.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 4 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(discovery): add domain normalization, ICP criteria, and fit score"`

---

### Task 8: Discovering companies (query generation, extraction, validation, waves)

**Files:**
- Create: `backend/covora/discovery/{models,schemas,validate,discover}.py`, `backend/covora/prompts/{query_generation,company_extraction}.md`, `backend/migrations/versions/0008_discovery.py`
- Modify: `backend/tests/fakes.py` (add `ScriptedBackend`)
- Test: `backend/tests/test_discover.py`

**Interfaces:**
- Consumes: `run_step`, `ResearchProvider`, `normalize_domain`, `is_blocked`, `Campaign`, `get_prompt`, `render_prompt`.
- Produces:
  - **Tables:**
    - `Company` (table `company`): `workspace_id`, `name`, `domain` (`unique(workspace_id, domain)`), `synthetic: bool` (true when found through `MockProvider`).
    - `CampaignCompany` (table `campaign_company`): `campaign_id`, `company_id` (`unique(campaign_id, company_id)`), `wave: int`, `source_url`, `status` (`candidate|qualified|rejected|needs_review|contact_selected|no_contact`), `criteria` (JSONB), `fit_score: int | None`, `confidence: str | None`, `reason: str | None`, `rank: int | None`.
    - `Fact` (table `fact`, spec §9.3) is created in this migration and used from Task 9: `company_id`, `contact_id: UUID | None`, `field`, `value` (JSONB), `source_url`, `quote`, `label` (`verified|unverified|unknown`), `retrieved_at`.
  - **Schemas:**
    - `QueryPlan(queries: list[str])`, 1–10 items, each 3–200 characters.
    - `ExtractedCompany(name: str, domain: str, source_url: str)` and `ExtractedCompanies(companies: list[ExtractedCompany])`.
  - **`validate_companies(extracted: list[ExtractedCompany], results: list[SearchResult], blocklist) -> list[ExtractedCompany]`:**
    - Normalize the domain, then drop it if it's invalid or blocked.
    - Keep a company only if its domain is the host of a result URL or appears in a result's title, description, or snippets.
    - If `source_url` isn't one of the result URLs, replace it with the first result that mentions the domain.
    - Dedupe by domain.
  - **`discover_wave(campaign_id: UUID, *, wave: int, ctx: RunContext, services: Services) -> WaveResult`** returns `WaveResult(queries: list[str], result_count: int, new_company_ids: list[UUID])`:
    1. **Queries:** in wave 1, use the ICP snapshot's `search_queries` that aren't already in `progress.used_queries`. Otherwise (or if none are left), generate them with `run_step(agent="discovery", task=query_generation, queries=[])`, with inputs `{icp, used_queries, wave}`.
    2. **Search:** each query with `count=20`. A `ResearchError` on one query is recorded on the stage span and skipped. `BudgetExceeded` is re-raised.
    3. **Extract:** batches of 25 results go through `run_step(agent="discovery", task=company_extraction)` with inputs `{icp_summary, results: [{url, title, description, snippets}]}`, then `validate_companies`.
    4. **Store:** upsert `company` rows by domain, setting `synthetic` from `services.research.name == "mock"`. Skip companies already linked to this campaign. Insert `campaign_company` rows with status `candidate` and this wave number, up to `settings.max_candidates_per_wave` new ones.
    5. Append the queries to `progress.used_queries`.
  - **`ScriptedBackend(dim, handlers: dict[str, Callable[[dict], dict]])`** in `tests/fakes.py`: finds the handler by `json_schema["title"]` (the Pydantic class name), calls it with the parsed JSON user message, and returns `json.dumps(result)`. It records calls like `FakeChatBackend`. An unknown title raises `AssertionError`. Test helpers on it:
    - `inputs_for(title) -> list[dict]`: the parsed user messages sent for that schema.
    - `override(title, fn)`: replaces that schema's handler.
    - `fail_next(title, times: int)`: the next `times` calls for that schema raise `BackendError(retryable=False)`.
  - **Prompt requirements** (wording is the builder's; placeholder `$memories` in both):
    - `query_generation.md`: specific, varied web queries that would surface company websites; never repeat `used_queries`.
    - `company_extraction.md`: return only real companies whose own website domain appears in the results; skip directories, news sites, and marketplaces.

- [ ] **Step 1: Write the failing tests.** Use `ScriptedBackend` plus `mock_research`. In the fake `company_extraction` handler, every result whose host ends in `.test` becomes `{name: <title before " |" or " -">, domain: <host>, source_url}`, and it also returns one invented company, `{"name": "Ghost Corp", "domain": "ghost.test", ...}`.

```python
async def test_wave_one_uses_icp_queries_and_creates_candidates(discovery_env):   # campaign from EXAMPLE_ICP
    r = await discover_wave(discovery_env.campaign_id, wave=1, ctx=discovery_env.ctx, services=discovery_env.services)
    assert r.queries == EXAMPLE_ICP["search_queries"]
    domains = await candidate_domains(discovery_env)                                # helper
    assert "ohio-precision.test" in domains and "thomasnet.com" not in domains

async def test_unlisted_company_dropped(discovery_env):
    await discover_wave(discovery_env.campaign_id, wave=1, ctx=discovery_env.ctx, services=discovery_env.services)
    assert "ghost.test" not in await candidate_domains(discovery_env)

async def test_wave_two_generates_new_queries(discovery_env):
    await discover_wave(discovery_env.campaign_id, wave=1, ctx=discovery_env.ctx, services=discovery_env.services)
    r = await discover_wave(discovery_env.campaign_id, wave=2, ctx=discovery_env.ctx, services=discovery_env.services)
    assert r.queries and not set(r.queries) & set(EXAMPLE_ICP["search_queries"])
    sent = discovery_env.backend.inputs_for("QueryPlan")[0]                          # ScriptedBackend helper
    assert set(sent["used_queries"]) >= set(EXAMPLE_ICP["search_queries"])

async def test_rerun_does_not_duplicate_candidates(discovery_env):
    for wave in (1, 2):
        await discover_wave(discovery_env.campaign_id, wave=wave, ctx=discovery_env.ctx, services=discovery_env.services)
    domains = await candidate_domains(discovery_env)
    assert len(domains) == len(set(domains))
```

  Add a `discovery_env` fixture to `conftest.py`. It provides a workspace, an `IcpVersion` from `EXAMPLE_ICP`, a `Campaign` with `target_prospects=3`, `Services` with a `ScriptedBackend` (standard fake handlers defined in `tests/fake_handlers.py`) and `mock_research`, and a `campaign` run ctx.
- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_discover.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the models, migration `0008`, schemas, validation, `discover_wave`, and the two prompts.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 4 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(discovery): find candidate companies in waves with validated extraction"`

---

### Task 9: Enrichment, facts, and fit scoring

**Files:**
- Create: `backend/covora/discovery/enrich.py`, `backend/covora/prompts/{fact_extraction,company_fit}.md`
- Modify: `backend/covora/discovery/schemas.py`, `backend/covora/discovery/validate.py`
- Test: `backend/tests/test_enrich.py`

**Interfaces:**
- Consumes: `Fact`, `CampaignCompany`, `icp_criteria`, `fit_score`, `run_step`, `MemoryQuery`.
- Produces:
  - **Schemas:**
    - `ExtractedFact(field: Literal["employee_count","revenue_usd","industry","location","description","founded_year","recent_event"], value: str, source_url: str, quote: str, label: Literal["verified","unverified"])` and `ExtractedFacts(facts: list[ExtractedFact])`.
    - `CriterionJudgment(criterion: str, status: Literal["met","not_met","unknown"], fact_ids: list[str])` and `FitJudgment(criteria: list[CriterionJudgment], confidence: Literal["high","medium","low"], reason: str (≤ 400 chars))`.
  - **`validate_facts(extracted, pages: Mapping[str, str]) -> list[ExtractedFact]`:**
    - Drop a fact if its `source_url` isn't in `pages`.
    - `verified` requires a non-empty quote that appears verbatim in that page's text, after collapsing whitespace and lowercasing. Otherwise it's downgraded to `unverified`.
    - `employee_count` and `revenue_usd` are kept **only** when verified.
  - **`enrich_and_score(campaign_id: UUID, company_ids: list[UUID], *, ctx, services) -> list[UUID]`** returns the IDs that qualified. For each company, with at most 4 running concurrently:
    1. **Reuse fresh facts:** if the company has facts retrieved within the last 30 days, skip fetching.
    2. **Otherwise gather:** run one search, `"<name>" <domain> employees`, with count 5, and one `contents` call for `https://<domain>/` and `https://<domain>/about`. The page texts are the contents' markdown plus each search result's title, description, and snippets (keyed by URL).
    3. **Extract:** `run_step(agent="enrichment", task=fact_extraction)` with inputs `{company, pages: [{url, text}]}`, then `validate_facts`, then insert `fact` rows with `retrieved_at=now`.
    4. **Judge:** `run_step(agent="fit", task=company_fit)` with inputs `{criteria: [{name, description, hard, stated, kind}], facts: [{id, field, value, label, source_url}], offering}`. Memory query: `MemoryQuery("semantic", ["insight"], "real", <icp summary>, "segment insights", filters={"dimension": "segment"}, k=3)`.
       - **Validate the judgment:** keep only statuses for known criterion names, and only `fact_ids` that belong to this company.
    5. **Score and store:** `fit_score(...)`. Update `campaign_company` with `criteria` (`[{name, status, fact_ids}]`), `fit_score`, `confidence`, `reason`, and status `qualified` (score ≥ `min_fit_score`) or `rejected`.
    - A `ResearchError` for one company sets its status to `needs_review`, with the reason "Couldn't gather facts: <error>". `BudgetExceeded` is re-raised.
    - After all companies, recompute `rank` (by fit score, descending) for the qualified companies in the campaign.
    - **Idempotent:** companies whose `campaign_company.status` is no longer `candidate` are skipped, so a resumed node doesn't re-score them.
  - **Prompt requirements:**
    - `fact_extraction.md`: quote exact text; label inferred values `unverified`; never estimate revenue or headcount.
    - `company_fit.md` (with `$memories`): judge each criterion from the facts only; anything without evidence is `unknown`; for exclusion criteria, `met` means the excluded condition applies; give a one-to-two-sentence reason that cites facts.

- [ ] **Step 1: Write the failing tests.** The standard fake handlers already know how to build facts and judgments.
  - The fake `fact_extraction` handler pulls "N employees" with an exact quote, the industry and location from the homepage, and one deliberately unquoted `revenue_usd`.
  - The fake `company_fit` handler judges the industry from the facts (manufacturing / fabrication / machining / plastics → met, software → not_met), the location, and the size against `employee_range`.

```python
async def test_scores_and_qualifies(enrich_env):          # discovery_env after wave 1
    qualified = await enrich_and_score(enrich_env.campaign_id, enrich_env.candidate_ids, ctx=enrich_env.ctx, services=enrich_env.services)
    rows = await campaign_companies_by_domain(enrich_env)   # helper → {domain: CampaignCompany}
    assert rows["ohio-precision.test"].status == "qualified" and rows["ohio-precision.test"].fit_score >= 60
    assert rows["brightpath.test"].status == "rejected"          # software: hard not_met → ≤20
    assert rows["granite-foods.test"].status == "rejected"       # 40 employees vs stated 5–25 → ≤50
    assert len(qualified) == sum(r.status == "qualified" for r in rows.values())

async def test_unquoted_revenue_dropped_and_quotes_verified(enrich_env):
    await enrich_and_score(enrich_env.campaign_id, enrich_env.candidate_ids, ctx=enrich_env.ctx, services=enrich_env.services)
    facts = await facts_for(enrich_env, "ohio-precision.test")
    assert not [f for f in facts if f.field == "revenue_usd"]
    emp = next(f for f in facts if f.field == "employee_count")
    assert emp.label == "verified" and "18 employees" in emp.quote

async def test_fresh_facts_are_reused(enrich_env, sessionmaker):
    await enrich_and_score(enrich_env.campaign_id, enrich_env.candidate_ids[:1], ctx=enrich_env.ctx, services=enrich_env.services)
    before = await count_tool_calls(sessionmaker)
    await enrich_and_score(enrich_env.campaign_id, enrich_env.candidate_ids[:1], ctx=enrich_env.ctx, services=enrich_env.services)
    assert await count_tool_calls(sessionmaker) == before

async def test_judgment_with_foreign_fact_ids_is_cleaned(enrich_env):
    enrich_env.backend.override("FitJudgment", lambda inp: {"criteria": [{"criterion": "industry", "status": "met", "fact_ids": ["not-a-fact"]},
        {"criterion": "made_up", "status": "met", "fact_ids": []}], "confidence": "low", "reason": "r"})
    await enrich_and_score(enrich_env.campaign_id, enrich_env.candidate_ids[:1], ctx=enrich_env.ctx, services=enrich_env.services)
    row = (await campaign_companies_by_domain(enrich_env)).popitem()[1]
    assert [c["name"] for c in row.criteria] == ["industry", "location", "employee_range", "revenue_range"]
    assert row.criteria[0]["fact_ids"] == []
```

  Add `count_tool_calls(sessionmaker, operation: str | None = None) -> int` to `tests/helpers.py` (non-cache and cache calls both count).
- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_enrich.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the schemas, `validate_facts`, `enrich_and_score`, and the two prompts.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 4 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(discovery): enrich companies with sourced facts and score ICP fit"`

---

### Task 10: Finding people and email status

**Files:**
- Create: `backend/covora/qualification/{__init__,models,schemas,validate,people}.py`, `backend/covora/prompts/people_extraction.md`, `backend/migrations/versions/0009_qualification.py`
- Test: `backend/tests/test_people.py`

**Interfaces:**
- Consumes: `CampaignCompany`, `Company`, `Fact`, `ResearchProvider`, `run_step`.
- Produces:
  - **Tables:**
    - `Contact` (table `contact`): `company_id`, `full_name`, `name_key` (lowercased, whitespace-collapsed; `unique(company_id, name_key)`), `title`, `function`, `seniority`, `linkedin_url`, `source_urls` (JSONB list), `email`, `email_status` (`verified|unverified|missing`), `email_source_url`, `synthetic`.
    - `Prospect` (table `prospect`, used by Task 11): `campaign_id`, `company_id`, `contact_id`, `short_id` (8 hex characters, unique), `role` (`primary|backup`), `pick_reason`, `confidence`, `status` (`selected`), `assigned_rep_id: UUID | None`, `meeting_booked_at`, `meeting_synthetic: bool`.
  - **Schemas:**
    - `ExtractedPerson(full_name: str, title: str, function: Literal["executive","operations","partnerships","sales","marketing","finance","engineering","hr","other"], seniority: Literal["owner","c_level","vp","director","manager","individual"], source_url: str, email: str | None = None, linkedin_url: str | None = None)`
    - `ExtractedPeople(people: list[ExtractedPerson])`
  - **`validate_people(extracted, sources: Mapping[str, str], *, linkedin_urls: set[str]) -> list[ExtractedPerson]`:**
    - Drop a person if their `source_url` isn't in `sources`, or their normalized `full_name` doesn't appear in that source's normalized text, or their title is empty.
    - `linkedin_url` is kept only if it's in `linkedin_urls` (search-result URLs containing `linkedin.com/in/`).
    - Dedupe by `name_key`.
  - **`classify_email(email: str | None, full_name: str, text: str) -> tuple[str | None, str]`** returns `(email, status)`:
    - `(None, "missing")` if the email is absent or doesn't appear verbatim (case-insensitive) in `text`.
    - `"unverified"` if the local part is generic (`info sales contact hello admin support office team enquiries inquiries`).
    - `"verified"` if the local part contains the person's first or last name (a token of 3+ characters) and the name appears in the same text.
    - `"unverified"` otherwise.
  - **`find_people(campaign_id, company_ids: list[UUID], *, ctx, services) -> dict[UUID, int]`** returns the number of contacts per company. For each company, with at most 4 running concurrently:
    1. **Searches:** `"<name>" <target functions joined by " OR "> linkedin`, plus `"<name>" leadership team`, each with count 10. If Task 5 recorded `site-operator: honored`, the first query becomes `site:linkedin.com/in "<name>" <functions>` instead.
    2. **Pages:** `contents` for `https://<domain>/team` and `https://<domain>/about`, skipping any already cached.
    3. **Sources:** the URL→text map is each search result's title, description, and snippets, plus each page's markdown.
    4. **Extract:** `run_step(agent="people", task=people_extraction)` with inputs `{company, target_functions, sources: [{url, text}]}`, then `validate_people`, then `classify_email` against the source text. Upsert `contact` rows, merging `source_urls`.
    - A `ResearchError` for one company leaves its count at 0, with the error on its span. `BudgetExceeded` is re-raised.
    - **Idempotent:** a company that already has contacts is skipped. Its existing count is returned without new searches.
  - **Prompt requirement:** `people_extraction.md`: list only people explicitly named in the sources, with their title exactly as written; include an email only if it's printed in the sources; never guess an address.

- [ ] **Step 1: Write the failing tests.** The fake `people_extraction` handler parses `Name — Title` lines and emails from the sources. It also adds one invented person ("Zed Phantom", COO) and an invented email for Mark Ellison (`mark@ohio-precision.test`).

```python
async def test_finds_named_people_with_sources(people_env):     # enrich_env after scoring
    counts = await find_people(people_env.campaign_id, people_env.qualified_ids, ctx=people_env.ctx, services=people_env.services)
    contacts = await contacts_by_name(people_env, "ohio-precision.test")
    assert {"Dana Ruiz", "Mark Ellison"} <= set(contacts) and counts[people_env.company_id("ohio-precision.test")] >= 2

async def test_person_not_in_source_dropped(people_env):
    await find_people(people_env.campaign_id, people_env.qualified_ids, ctx=people_env.ctx, services=people_env.services)
    assert "Zed Phantom" not in await contacts_by_name(people_env, "ohio-precision.test")

async def test_email_not_in_source_not_recorded(people_env):
    await find_people(people_env.campaign_id, people_env.qualified_ids, ctx=people_env.ctx, services=people_env.services)
    c = await contacts_by_name(people_env, "ohio-precision.test")
    assert (c["Mark Ellison"].email, c["Mark Ellison"].email_status) == (None, "missing")
    assert (c["Dana Ruiz"].email, c["Dana Ruiz"].email_status) == ("dana.ruiz@ohio-precision.test", "verified")

def test_classify_email_rules():
    text = "Dana Ruiz, Operations. dana.ruiz@x.test · info@x.test"
    assert classify_email("info@x.test", "Dana Ruiz", text) == ("info@x.test", "unverified")
    assert classify_email("dana.ruiz@x.test", "Dana Ruiz", text) == ("dana.ruiz@x.test", "verified")
    assert classify_email("dr@x.test", "Dana Ruiz", text) == (None, "missing")
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_people.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the models, migration `0009`, schemas, validation, `find_people`, and the prompt.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 4 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(qualification): find named people with sourced emails"`

---

### Task 11: Picking the contact (selection, validation, selection episodes)

**Files:**
- Create: `backend/covora/qualification/select.py`, `backend/covora/prompts/contact_selection.md`
- Modify: `backend/covora/qualification/schemas.py`, `backend/covora/qualification/validate.py`
- Test: `backend/tests/test_select.py`, plus `test_measured_cost_model` in `backend/tests/test_sizing.py`

**Interfaces:**
- Consumes: `Contact`, `Prospect`, `CampaignCompany`, `Fact`, `run_step`, `NewMemory`, `MemoryQuery`.
- Produces:
  - **Schemas:**
    - `Pick(contact_id: str, reason: str (≤ 300), confidence: Literal["high","medium","low"])`
    - `ContactSelection(primary: Pick | None, backup: Pick | None, no_suitable_contact: bool)`
  - **`validate_selection(sel: ContactSelection, candidate_ids: set[str], suppressed_emails: set[str], emails: Mapping[str, str | None]) -> ContactSelection`:**
    - Picks must be among the candidates and not suppressed. The backup must differ from the primary.
    - A `no_suitable_contact` with picks is normalized to having no picks.
    - It raises `ValueError` if the primary is invalid. The caller retries once, then marks the company `needs_review`.
    - Suppression comes from Plan 3's table. Pass an empty set until then.
  - **`select_contacts(campaign_id, company_ids, *, ctx, services) -> int`** returns the number of prospects created. For each company that has contacts, with at most 4 running concurrently:
    1. **Pick:** `run_step(agent="selection", task=contact_selection)` with inputs `{company: {name, domain, employee_count_fact}, offering, buyer_map, candidates: [{id, full_name, title, function, seniority, email_status}]}`.
    2. **Memory queries:**
       - `MemoryQuery("episodic", ["selection_episode"], "real", "<titles> at <size> <industry>", "past picks at similar companies", k=5)`
       - `MemoryQuery("semantic", ["insight"], "real", "<titles>", "title insights", filters={"dimension": "title"}, k=3)`
    3. **Episode:** `NewMemory("episodic", "selection_episode", source, summary=f"Picked {title} ({seniority}) at a {size}-person {industry} company in {location}", payload={"campaign_id", "company_id", "contact_id", "title", "function", "seniority"}, source_refs=[{"table": "prospect", "id": ...}])`. The `source` is `research`, or `mock_sim` when the company is synthetic.
    4. **Store:** prospects for the primary (`role=primary`) and the backup. The company's status becomes `contact_selected`, or `no_contact` with the reason "No suitable contact found" (also used when there are no candidates).
    - **Idempotent:** companies already `contact_selected`, `no_contact`, or `needs_review` are skipped. `prospect` has `unique(campaign_id, contact_id)`.
    - **Errors:** a `GatewayError` (models unavailable) propagates, so the node fails and the user can Retry. Only an invalid pick is handled locally (retry once, then `needs_review`).
  - **Prompt requirement:** `contact_selection.md` (with `$memories`): pick the person who owns the problem and can buy, given the company's size; use the backup for a second-best person; mark `no_suitable_contact` rather than force a weak pick.

- [ ] **Step 1: Write the failing tests.** The fake `contact_selection` handler picks the first candidate whose function is in the buyer map's target functions or who is an owner or C-level, and the next such candidate as backup. A per-test override returns an unknown ID.

```python
async def test_primary_and_backup_created(select_env):       # people_env after find_people
    n = await select_contacts(select_env.campaign_id, select_env.qualified_ids, ctx=select_env.ctx, services=select_env.services)
    prospects = await prospects_by_domain(select_env)
    roles = {p.role for p in prospects["ohio-precision.test"]}
    assert roles == {"primary", "backup"} and n >= 3

async def test_company_without_people_marked_no_contact(select_env):
    await select_contacts(select_env.campaign_id, select_env.qualified_ids, ctx=select_env.ctx, services=select_env.services)
    rows = await campaign_companies_by_domain(select_env)
    assert rows["midwest-valve.test"].status == "no_contact"

async def test_invented_pick_retried_then_needs_review(select_env):
    select_env.backend.override("ContactSelection", lambda inp: {"primary": {"contact_id": "nope", "reason": "r", "confidence": "low"},
                                                                 "backup": None, "no_suitable_contact": False})
    await select_contacts(select_env.campaign_id, select_env.qualified_ids[:1], ctx=select_env.ctx, services=select_env.services)
    row = (await campaign_companies_by_domain(select_env))[select_env.domain_of(select_env.qualified_ids[0])]
    assert row.status == "needs_review"
    assert len(select_env.backend.inputs_for("ContactSelection")) == 2

async def test_selection_episode_written(select_env, memory):
    await select_contacts(select_env.campaign_id, select_env.qualified_ids, ctx=select_env.ctx, services=select_env.services)
    eps = await memory.retrieve(MemoryQuery("episodic", ["selection_episode"], "mock", "Operations Manager", "r", k=10), select_env.ctx)
    assert any("Operations Manager" in e.item.summary for e in eps)       # mock companies → mock_sim scope
```

  Add `test_measured_cost_model` to `test_sizing.py`: once a `complete` campaign has 3 primaries, 24 non-cache searches, and 12 pages, the measured cost model gives `searches_per_prospect == 8.0` and `source == "measured"`.
- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_select.py tests/test_sizing.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the schemas, `validate_selection`, `select_contacts`, and the prompt.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "feat(qualification): pick primary and backup contacts with selection memory"`

---

### Task 12: The campaign graph, its job, and run/retry

**Files:**
- Create: `backend/covora/graphs/{__init__,checkpointer,campaign,jobs}.py`, `backend/migrations/versions/0010_langgraph_schema.py`
- Modify: `backend/covora/worker.py` (register `campaign.run`), `backend/covora/api/routes/campaigns.py` (add run/retry), `backend/pyproject.toml` (`langgraph==1.2.16`, `langgraph-checkpoint-postgres==3.2.0`)
- Test: `backend/tests/test_campaign_graph.py`

**Interfaces:**
- Consumes: `discover_wave`, `enrich_and_score`, `find_people`, `select_contacts`, `BudgetExceeded`, `enqueue`, `start_run`, `finish_run`, `span`, `Campaign`, `CampaignCompany`.
- Produces:
  - **Migration `0010`:** `CREATE SCHEMA IF NOT EXISTS langgraph` (downgrade: `DROP SCHEMA langgraph CASCADE`).
  - **`checkpointer.py`:**
    - `checkpointer_url(database_url: str) -> str`: replaces `postgresql+psycopg://` with `postgresql://` and appends `options=-csearch_path%3Dlanggraph` (using `&` if a query string is already present).
    - `open_checkpointer(settings) -> AsyncContextManager[AsyncPostgresSaver]`: `AsyncPostgresSaver.from_conn_string(...)`, then `await setup()`.
  - **`CampaignState(TypedDict)`:** `campaign_id: str`, `wave: int`, `stop_reason: str | None`.
  - **`build_campaign_graph(services, checkpointer)`** returns the compiled graph:
    - Nodes: `discover_companies`, `score_companies`, `find_people`, `select_contacts`.
    - Edges: `START → discover_companies → score_companies →(route_after_scoring)→ discover_companies | find_people → select_contacts → END`.
    - Each node reads `run_id` and `trace_id` from `config["configurable"]` (never from state, so a resumed run traces into the new run) and wraps its work in `span(kind="stage", name=<node>)`.
    - A wave's new company IDs are read from `campaign_company.wave`, not carried in state.
  - **`route_after_scoring(state, *, qualified: int, target_companies: int, max_waves: int, new_last_wave: int, new_prev_wave: int | None) -> Literal["discover_companies","find_people"]`**, a pure function. It returns `find_people` when any of these holds:
    - `qualified ≥ target_companies` (where `target_companies = ⌈target_prospects × contact_yield_buffer⌉`)
    - `state.wave ≥ max_waves`
    - `stop_reason` is set (budget)
    - the last two waves added 0 new companies

    Otherwise it returns `discover_companies`. The node sets `stop_reason` to one of `enough_qualified | max_waves | budget | no_new_companies` and stores it in `campaign.progress.stop_reason`.
  - **Budget handling:** `BudgetExceeded` inside `discover_companies` or `score_companies` sets `stop_reason="budget"` and continues to `find_people`. Inside `find_people` or `select_contacts`, it stops new research calls and finishes with the data already gathered.
  - **`run_campaign_job(job: Job, services: Services) -> None`**, for job kind `campaign.run` with payload `{campaign_id, resume: bool}`:
    1. `start_run(kind="campaign", campaign_id=...)`. Set `workflow_run.thread_id = f"campaign-{campaign_id}"` and the campaign's status to `running`.
    2. Invoke `graph.ainvoke(None if resume else {"campaign_id", "wave": 0, "stop_reason": None}, {"configurable": {"thread_id", "run_id", "trace_id"}})`.
    3. On success: `finish_run(succeeded)`, campaign `complete`.
    4. On an exception: `finish_run(failed)`, campaign `failed` with the redacted `last_error`, then re-raise so the job is marked failed.
  - **Routes:**
    - `POST /api/campaigns/{id}/run`: allowed only from `draft`. Enqueues `campaign.run` with `{resume: false}` and `max_attempts=1`, sets status `queued`, and returns `CampaignOut`. From any other status it returns 409 `invalid_state`.
    - `POST /api/campaigns/{id}/retry`: allowed only from `failed`. Enqueues the job with `{resume: true}` and sets status `queued`.

- [ ] **Step 1: Write the failing tests.** Each test runs the job directly with `run_campaign_job(Job(...), services)`, using `ScriptedBackend` and `mock_research`.

```python
def test_route_rules():
    s = {"campaign_id": "c", "wave": 1, "stop_reason": None}
    assert route_after_scoring(s, qualified=4, target_companies=4, max_waves=15, new_last_wave=3, new_prev_wave=None) == "find_people"
    assert route_after_scoring(s, qualified=1, target_companies=4, max_waves=15, new_last_wave=3, new_prev_wave=None) == "discover_companies"
    assert route_after_scoring({**s, "wave": 15}, qualified=1, target_companies=4, max_waves=15, new_last_wave=3, new_prev_wave=2) == "find_people"
    assert route_after_scoring({**s, "wave": 3}, qualified=1, target_companies=4, max_waves=15, new_last_wave=0, new_prev_wave=0) == "find_people"

async def test_full_pipeline_creates_prospects(graph_env):        # campaign target_prospects=3, mock web
    await run_campaign_job(graph_env.job(resume=False), graph_env.services)
    c = await graph_env.campaign()
    assert c.status == "complete" and c.progress["stop_reason"] in {"enough_qualified", "no_new_companies"}
    assert (await graph_env.funnel())["prospects"] >= 3
    kinds = await stage_span_names(graph_env)                     # helper: names of kind="stage" spans for the run
    assert {"discover_companies", "score_companies", "find_people", "select_contacts"} <= set(kinds)

async def test_retry_resumes_without_rediscovery(graph_env, sessionmaker):
    graph_env.backend.fail_next("ContactSelection", times=2)       # Super then the Nano fallback both fail → GatewayError → node fails
    with pytest.raises(Exception):
        await run_campaign_job(graph_env.job(resume=False), graph_env.services)
    assert (await graph_env.campaign()).status == "failed"
    searches_before = await count_tool_calls(sessionmaker, operation="search")
    await run_campaign_job(graph_env.job(resume=True), graph_env.services)
    assert (await graph_env.campaign()).status == "complete"
    assert await count_tool_calls(sessionmaker, operation="search") == searches_before    # people searches were checkpointed before select

async def test_budget_exhaustion_completes_with_partial_results(graph_env):
    await graph_env.set_budget(spent=79.99, cap=80.0)               # first paid call refused; mock provider charges a test price
    await run_campaign_job(graph_env.job(resume=False), graph_env.services)
    c = await graph_env.campaign()
    assert c.status == "complete" and c.progress["stop_reason"] == "budget"

async def test_run_and_retry_endpoints_guard_state(api, draft_campaign_id):
    assert (await api.post(f"/api/campaigns/{draft_campaign_id}/run")).json()["status"] == "queued"
    assert (await api.post(f"/api/campaigns/{draft_campaign_id}/run")).status_code == 409
    assert (await api.post(f"/api/campaigns/{draft_campaign_id}/retry")).status_code == 409
```

  For the budget test, `MockProvider` accepts an optional `price_per_call` and `budget` hook so that `charge` is exercised. Wire it as `MockProvider(pages, charge_with=(sessionmaker, cap, price))`, used only in tests.
- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv sync && uv run pytest tests/test_campaign_graph.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the checkpointer, graph, router, job handler, worker registration, and endpoints.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 5 passed. Then run the full suite with `uv run pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit.** `git commit -m "feat(graphs): add checkpointed LangGraph campaign pipeline with run/retry"`

---

### Task 13: Prospects API and CSV exports

**Files:**
- Create: `backend/covora/api/routes/prospects.py`, `backend/covora/api/routes/exports.py`, `backend/covora/exports.py`
- Test: `backend/tests/test_prospects_api.py`

**Interfaces:**
- Consumes: `CampaignCompany`, `Company`, `Fact`, `Contact`, `Prospect`.
- Produces:
  - **`GET /api/campaigns/{id}/companies`** → `CompanyRow[]`, ordered by status (qualified first) and then fit score descending. Each row is `{company_id, name, domain, status, fit_score, confidence, reason, wave, criteria, synthetic, facts_summary: {employee_count?, industry?, location?}}`.
  - **`GET /api/campaigns/{id}/prospects`** → `ProspectRow[]`: `{prospect_id, short_id, role, status, confidence, pick_reason, company: {id, name, domain}, contact: {id, full_name, title, function, seniority, email, email_status, linkedin_url, source_urls}, synthetic}`.
  - **`GET /api/companies/{id}`** → `{company, facts: [{field, value, label, source_url, quote, retrieved_at}], contacts: [...], campaigns: [{campaign_id, status, fit_score, reason, criteria}]}`.
  - **`GET /api/contacts/{id}`** → `{contact, company, prospects: [...]}`.
  - **`csv_safe(value) -> str`**: stringifies, and prefixes `'` when the value starts with any of `= + - @ \t \r`.
  - **`GET /api/exports/companies.csv?campaign_id=`** and **`GET /api/exports/prospects.csv?campaign_id=`**: `text/csv` with `Content-Disposition: attachment; filename="<kind>-<campaign short>.csv"`.
    - Companies columns: `company,domain,status,fit_score,confidence,reason,wave,industry,location,employee_count,synthetic`.
    - Prospects columns: `company,domain,contact,title,role,confidence,pick_reason,email,email_status,linkedin_url,source_urls,synthetic`.
  - An unknown ID returns 404 `not_found`.

- [ ] **Step 1: Write the failing tests.** The `completed_campaign` fixture runs `graph_env`'s full pipeline.

```python
async def test_companies_and_prospects_lists(api, completed_campaign):
    companies = (await api.get(f"/api/campaigns/{completed_campaign}/companies")).json()
    scores = [c["fit_score"] for c in companies if c["status"] == "qualified"]
    assert companies[0]["status"] == "qualified" and scores == sorted(scores, reverse=True)
    prospects = (await api.get(f"/api/campaigns/{completed_campaign}/prospects")).json()
    assert {p["role"] for p in prospects} >= {"primary"} and all(p["contact"]["full_name"] for p in prospects)

async def test_company_detail_has_labeled_facts(api, completed_campaign):
    cid = next(c["company_id"] for c in (await api.get(f"/api/campaigns/{completed_campaign}/companies")).json()
               if c["domain"] == "ohio-precision.test")
    detail = (await api.get(f"/api/companies/{cid}")).json()
    assert any(f["field"] == "employee_count" and f["label"] == "verified" and f["source_url"] for f in detail["facts"])

def test_csv_cells_are_formula_escaped():
    assert csv_safe("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert csv_safe("+1 555") == "'+1 555" and csv_safe("@me") == "'@me" and csv_safe("Acme") == "Acme"

async def test_prospects_csv_export(api, completed_campaign):
    r = await api.get(f"/api/exports/prospects.csv?campaign_id={completed_campaign}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0].startswith("company,domain,contact,title,role")
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `uv run pytest tests/test_prospects_api.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the routes and `exports.py`.** Include the routers in `create_app`.
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 4 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(api): add prospects, company/contact detail, and CSV exports"`

---

### Task 14: Settings: goals and sending

**Files:**
- Create: `frontend/src/features/settings/GoalsForm.tsx`
- Modify: `frontend/src/pages/Settings.tsx`, `frontend/src/api/types.ts`
- Test: `frontend/src/features/settings/GoalsForm.test.tsx`

**Interfaces:**
- Consumes: `GET` and `PUT /api/workspace/settings`.
- Produces:
  - **Types:** TS `Goals`, `SendingSettings`, and `WorkspaceSettings`, mirroring the backend.
  - **`<GoalsForm>`, under a "Goals & sending" card on Settings.** Fields:
    - Goal (radio: "Positive replies" | "Meetings")
    - Target (number)
    - Expected positive reply rate (%) — percentage in the UI, fraction in the API (1 ↔ 0.01)
    - Meetings per positive reply (%) — shown only for the meetings goal
    - Daily Gmail limit
    - First batch to review
  - **Save** shows "Saved" or the API error.

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows rates as percentages and saves fractions", async () => {
  const calls = mockFetch({ "GET /api/workspace/settings": SETTINGS, "PUT /api/workspace/settings": SETTINGS });
  renderWithQuery(<GoalsForm />);
  const rate = await screen.findByLabelText("Expected positive reply rate (%)");
  expect(rate).toHaveValue(1);
  await userEvent.clear(rate); await userEvent.type(rate, "2");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Saved")).toBeInTheDocument();
  expect((calls.body("PUT /api/workspace/settings").goals as { expected_positive_rate: number }).expected_positive_rate).toBeCloseTo(0.02);
});
it("shows meetings rate only for meetings goal", async () => {
  mockFetch({ "GET /api/workspace/settings": SETTINGS });
  renderWithQuery(<GoalsForm />);
  expect(await screen.findByLabelText("Target")).toBeInTheDocument();
  expect(screen.queryByLabelText("Meetings per positive reply (%)")).toBeNull();
  await userEvent.click(screen.getByLabelText("Meetings"));
  expect(screen.getByLabelText("Meetings per positive reply (%)")).toBeInTheDocument();
});
```

  `SETTINGS` in `src/test/fixtures.ts` holds the backend defaults.
- [ ] **Step 2: Run the tests and confirm they fail.** Run: `cd frontend && npm test -- GoalsForm`. Expected: FAIL.
- [ ] **Step 3: Implement `GoalsForm` and add it to Settings.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 2 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(web): add goals and sending settings"`

---

### Task 15: Launching a campaign (from ICP Studio)

**Files:**
- Create: `frontend/src/features/campaigns/LaunchCampaignDialog.tsx`
- Modify: `frontend/src/pages/IcpStudio.tsx` (a **Launch campaign** button, enabled once a version is saved or loaded), `frontend/src/api/types.ts`, `frontend/src/App.tsx` (route `/campaigns/:campaignId`)
- Test: `frontend/src/features/campaigns/LaunchCampaignDialog.test.tsx`

**Interfaces:**
- Consumes: `GET /api/workspace/settings`, `POST /api/campaigns/estimate`, `POST /api/campaigns`, `POST /api/campaigns/{id}/run`.
- Produces: `<LaunchCampaignDialog icpVersion={IcpVersionOut} onClose={() => void} />`, a modal `role="dialog"` titled "Launch campaign".
  - **Fields:**
    - Name (defaults to the ICP summary, trimmed to 60 characters)
    - Goal type and target (prefilled from workspace settings)
    - Expected positive reply rate (%)
    - Meetings per positive reply (%) — meetings goal only
    - "Find up to" prospects (defaults to blank, meaning "all needed")
  - **Estimate panel:** re-fetched 400 ms after the last change (debounced). It shows:
    - "You need about **{prospects_needed}** prospects"
    - "This campaign will find **{prospects_planned}**"
    - "≈ **{est_searches}** searches · **${est_youcom_usd}** of You.com credit · **{est_model_calls}** model calls"
    - "**{gmail_emails}** via Gmail, **{in_app_emails}** delivered in-app"
    - "${budget_remaining_usd} left"
  - **Over budget:** when `fits_budget` is false, an amber alert reads "This is more than your remaining budget — at most {max_affordable_prospects} prospects fit." The **Launch** button stays disabled until "Find up to" ≤ `max_affordable_prospects`.
  - **Launch:** create the campaign, call run, then navigate to `/campaigns/{id}`.
  - **Observed reply rate:** the spec's "observed rate with its 95% range" needs outreach results, so it's added in Plan 5. Until then the dialog shows assumptions only, labeled "Based on your expected rate".

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows the owner's example estimate", async () => {
  mockFetch({ "GET /api/workspace/settings": SETTINGS, "POST /api/campaigns/estimate": ESTIMATE_1000 });
  renderWithQuery(<LaunchCampaignDialog icpVersion={VERSION} onClose={() => {}} />);
  expect(await screen.findByText(/1,000/)).toBeInTheDocument();
  expect(screen.getByText(/\$44\.00/)).toBeInTheDocument();
  expect(screen.getByText(/100 via Gmail, 900 delivered in-app/)).toBeInTheDocument();
});
it("blocks launch when over budget until capped", async () => {
  mockFetch({ "GET /api/workspace/settings": SETTINGS, "POST /api/campaigns/estimate": { ...ESTIMATE_1000, fits_budget: false, max_affordable_prospects: 300 } });
  renderWithQuery(<LaunchCampaignDialog icpVersion={VERSION} onClose={() => {}} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("at most 300 prospects");
  expect(screen.getByRole("button", { name: "Launch" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Find up to"), "200");
  expect(screen.getByRole("button", { name: "Launch" })).toBeEnabled();
});
it("creates, runs, and navigates", async () => {
  const calls = mockFetch({ "GET /api/workspace/settings": SETTINGS, "POST /api/campaigns/estimate": ESTIMATE_1000,
    "POST /api/campaigns": CAMPAIGN_DRAFT, "POST /api/campaigns/c1/run": { ...CAMPAIGN_DRAFT, status: "queued" } });
  renderWithQuery(<><LaunchCampaignDialog icpVersion={VERSION} onClose={() => {}} /><LocationProbe /></>);
  await userEvent.click(await screen.findByRole("button", { name: "Launch" }));
  expect(await screen.findByTestId("location")).toHaveTextContent("/campaigns/c1");
  expect(calls.body("POST /api/campaigns").icp_version_id).toBe("v1");
});
```

  Add `ESTIMATE_1000`, `CAMPAIGN_DRAFT`, and `LocationProbe` (renders `useLocation().pathname` in `data-testid="location"`) to the test files.
- [ ] **Step 2: Run the tests and confirm they fail.** Run: `npm test -- LaunchCampaignDialog`. Expected: FAIL.
- [ ] **Step 3: Implement the dialog and the ICP Studio button.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 3 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(web): launch campaigns from ICP Studio with goal-based sizing"`

---

### Task 16: Campaigns list and campaign detail

**Files:**
- Create: `frontend/src/pages/CampaignDetail.tsx`, `frontend/src/features/campaigns/Funnel.tsx`
- Modify: `frontend/src/pages/Campaigns.tsx`, `frontend/src/App.tsx`
- Test: `frontend/src/features/campaigns/campaigns.test.tsx`

**Interfaces:**
- Consumes: `GET /api/campaigns`, `GET /api/campaigns/{id}`, `POST /api/campaigns/{id}/retry`.
- Produces:
  - **`<Campaigns>`:** a table with Name (links to the detail page), Status badge, "Prospects" (`funnel.prospects` / `target_prospects`), and Created.
    - Empty state: "No campaigns yet", body "Save an ICP in ICP Studio, then launch a campaign."
  - **`<CampaignDetail>`:**
    - Header: name, status badge, and a stop-reason line ("Stopped: found enough qualified companies" / "Stopped: You.com budget reached" / "Stopped: no new companies found" / "Stopped: reached the wave limit").
    - `<Funnel funnel>`: steps Companies found → Qualified → With contacts → Prospects picked, with counts. The "Rejected" and "No contact" counts appear beside the steps.
    - Links: "View agent run" (`/workflow/runs/{latest_run_id}`) and "View prospects" (`/prospects?campaign={id}`).
    - When `failed`: an error box with `last_error` and a **Retry** button.
    - Polls every 3 s while the status is `queued` or `running`.

- [ ] **Step 1: Write the failing tests**

```tsx
it("lists campaigns or shows empty state", async () => {
  mockFetch({ "GET /api/campaigns": [] });
  renderWithQuery(<Campaigns />, { route: "/campaigns" });
  expect(await screen.findByText("No campaigns yet")).toBeInTheDocument();
});
it("shows funnel and stop reason", async () => {
  mockFetch({ "GET /api/campaigns/c1": CAMPAIGN_COMPLETE });
  renderWithQuery(<CampaignDetail />, { route: "/campaigns/c1", path: "/campaigns/:campaignId" });
  expect(await screen.findByText("Stopped: found enough qualified companies")).toBeInTheDocument();
  expect(screen.getByText("Prospects picked")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View prospects" })).toHaveAttribute("href", "/prospects?campaign=c1");
});
it("retries a failed campaign", async () => {
  const calls = mockFetch({ "GET /api/campaigns/c2": CAMPAIGN_FAILED, "POST /api/campaigns/c2/retry": { ...CAMPAIGN_FAILED, status: "queued" } });
  renderWithQuery(<CampaignDetail />, { route: "/campaigns/c2", path: "/campaigns/:campaignId" });
  await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
  expect(calls.fn).toHaveBeenCalledWith("/api/campaigns/c2/retry", expect.objectContaining({ method: "POST" }));
});
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `npm test -- campaigns`. Expected: FAIL.
- [ ] **Step 3: Implement the pages, the funnel, and the route.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 3 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(web): add campaigns list and campaign detail with funnel and retry"`

---

### Task 17: Prospects page

**Files:**
- Modify: `frontend/src/pages/Prospects.tsx`, `frontend/src/api/types.ts`
- Create: `frontend/src/features/prospects/{CompaniesTable,PeopleTable,CompanyDrawer,ContactDrawer,EvidenceBadge}.tsx`
- Test: `frontend/src/features/prospects/prospects.test.tsx`

**Interfaces:**
- Consumes: `GET /api/campaigns`, `GET /api/campaigns/{id}/companies`, `GET /api/campaigns/{id}/prospects`, `GET /api/companies/{id}`, `GET /api/contacts/{id}`, and the CSV export URLs.
- Produces:
  - **`<Prospects>`:**
    - A campaign selector, defaulting to `?campaign=` or the newest campaign.
    - Tabs **Companies** | **People**.
    - **Export CSV** links (plain `<a href="/api/exports/…csv?campaign_id=…">`).
    - Empty state when there are no campaigns.
    - A "Synthetic (mock web)" badge on rows where `synthetic` is set.
  - **`<CompaniesTable>`:** columns Company (name and domain), Fit (score and confidence), Status, Why (reason), and Criteria (one chip per criterion: met = green, not_met = red, unknown = slate). Clicking a row opens `<CompanyDrawer>`.
  - **`<CompanyDrawer>`** (`role="dialog"`):
    - Facts, each with an `<EvidenceBadge label>` ("Verified" = green, "Unverified" = amber, "Unknown" = slate), the value, the quote in italics, and a source link (`target="_blank" rel="noreferrer"`).
    - The contacts found.
  - **`<PeopleTable>`:** columns Name, Title, Company, Role (Primary/Backup), Why picked, Confidence, Email (address plus a status badge: "Verified" / "Unverified" / "No email"). Clicking a row opens `<ContactDrawer>`, which shows the sources.

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows companies with criteria chips and opens facts", async () => {
  mockFetch({ "GET /api/campaigns": [CAMPAIGN_COMPLETE], "GET /api/campaigns/c1/companies": COMPANIES,
              "GET /api/companies/co1": COMPANY_DETAIL });
  renderWithQuery(<Prospects />, { route: "/prospects?campaign=c1" });
  await userEvent.click(await screen.findByText("Ohio Precision Fabrication"));
  const drawer = await screen.findByRole("dialog");
  expect(within(drawer).getByText("Verified")).toBeInTheDocument();
  expect(within(drawer).getByRole("link", { name: /ohio-precision\.test/ })).toHaveAttribute("target", "_blank");
});
it("shows people with email status", async () => {
  mockFetch({ "GET /api/campaigns": [CAMPAIGN_COMPLETE], "GET /api/campaigns/c1/companies": COMPANIES,
              "GET /api/campaigns/c1/prospects": PROSPECTS });
  renderWithQuery(<Prospects />, { route: "/prospects?campaign=c1" });
  await userEvent.click(await screen.findByRole("tab", { name: "People" }));
  expect(await screen.findByText("Dana Ruiz")).toBeInTheDocument();
  expect(screen.getByText("No email")).toBeInTheDocument();
});
it("links CSV exports for the selected campaign", async () => {
  mockFetch({ "GET /api/campaigns": [CAMPAIGN_COMPLETE], "GET /api/campaigns/c1/companies": COMPANIES });
  renderWithQuery(<Prospects />, { route: "/prospects?campaign=c1" });
  expect(await screen.findByRole("link", { name: "Export companies CSV" })).toHaveAttribute("href", "/api/exports/companies.csv?campaign_id=c1");
});
```

- [ ] **Step 2: Run the tests and confirm they fail.** Run: `npm test -- prospects`. Expected: FAIL.
- [ ] **Step 3: Implement the page and its components.**
- [ ] **Step 4: Run the tests and confirm they pass.** Run the same command. Expected: 3 passed.
- [ ] **Step 5: Commit.** `git commit -m "feat(web): add Prospects page with evidence, drawers, and CSV export"`

---

### Task 18: End-to-end verification and docs

**Files:**
- Modify: `README.md` (worker run command, `RESEARCH_PROVIDER`), `docs/PROGRESS.md`, `docs/DECISIONS.md`

- [ ] **Step 1: Run every automated check.** Run: `cd backend && uv run ruff check . && uv run pytest -q && cd ../frontend && npm test && npm run typecheck && npm run build`. Expected: all pass.
- [ ] **Step 2: Run a live check with the mock web.** This needs `NVIDIA_API_KEY`; without it, run up to "parse → 502" as in Plan 1, and ledger the gap.
  1. Set `RESEARCH_PROVIDER=mock` and `MOCK_WEB_PATH=backend/tests/data/mock_web.json`.
  2. Start the API, the worker (`uv run python -m covora.worker`), and the web app.
  3. In the browser:
     - Save a profile and an ICP version from the spec's example prompt.
     - Launch a campaign with "Find up to" set to 3.
     - Watch the campaign reach `complete`.
     - Open Prospects.
  4. Expected:
     - Companies show fit scores and criteria chips.
     - Ohio Precision's facts show "Verified" with quotes.
     - People show Dana Ruiz as primary with a verified email.
     - The CSV downloads.
     - Agent Workflow shows the four stage spans and the tool calls.
- [ ] **Step 3: Run a live check with You.com.** This needs `YDC_API_KEY` and `NVIDIA_API_KEY`; otherwise, defer and ledger it.
  - Set `RESEARCH_PROVIDER=youcom`, and launch a campaign with "Find up to" set to 5, which costs about $0.22.
  - Expected: real companies with source links, every person traceable to a source, and spend shown in the estimate's "left" figure.
- [ ] **Step 4: Update the docs.**
  - `README.md`: the worker command and the `RESEARCH_PROVIDER` toggle.
  - `docs/PROGRESS.md`: Plan 2 done, with what works and the known gaps.
  - `docs/DECISIONS.md`: the stricter fit rules, the `langgraph` checkpoint schema, polling instead of SSE, campaign jobs not auto-retried, the `site-operator` result, and the mock web as a dev toggle labeled synthetic.
- [ ] **Step 5: Commit.** `git commit -m "docs: record Plan 2 progress and decisions"`
